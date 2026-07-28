#!/usr/bin/env python3
"""Deterministically generate Python and TypeScript types from JSON Schemas.

Generated output lives under:
  packages/contracts/generated/python/
  packages/contracts/generated/typescript/

Do not edit generated files by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = ROOT / "packages" / "contracts"
SCHEMA_DIR = CONTRACTS_DIR / "schemas"
GENERATED_PYTHON = CONTRACTS_DIR / "generated" / "python"
GENERATED_TYPESCRIPT = CONTRACTS_DIR / "generated" / "typescript"

GENERATED_NOTICE_PY = (
    "# This file is GENERATED from packages/contracts/schemas.\n"
    "# Do not edit manually. Re-run: make generate-contract-types\n"
)
GENERATED_NOTICE_TS = (
    "/* This file is GENERATED from packages/contracts/schemas.\n"
    " * Do not edit manually. Re-run: make generate-contract-types\n"
    " */\n"
)

# Top-level public contracts that apps import.
PUBLIC_SCHEMA_STEMS = [
    "project.v1",
    "user-turn.v1",
    "turn-route.v1",
    "workflow-run.v1",
    "artifact.v1",
    "artifact-envelope.v1",
    "project-brief.v1",
    "requirement-set.v1",
    "functional-architecture.v1",
    "next-action.v1",
    "validation-issue.v1",
    "open-question.v1",
    "vera-response.v1",
    "project-initialization-result.v1",
    "actor-reference.v1",
    "quantity.v1",
    "evidence-reference.v1",
    "approval-record.v1",
    "artifact-status.v1",
    "open-question-reference.v1",
]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _iter_schema_files() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("**/*.schema.json"))


def _load_schemas_by_id() -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in _iter_schema_files():
        data = _load_json(path)
        schema_id = data.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise ValueError(f"Schema missing $id: {path}")
        schemas[schema_id] = data
    return schemas


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _resolve_pointer(root: Any, fragment: str) -> Any:
    node = root
    parts = [p for p in fragment.split("/") if p]
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"Unresolved JSON pointer: #{fragment}")
        node = node[part]
    return node


def _resolve_ref(
    ref: str,
    store: dict[str, dict[str, Any]],
    stack: list[str],
    local_root: dict[str, Any] | None,
) -> Any:
    if "#" in ref:
        base, fragment = ref.split("#", 1)
    else:
        base, fragment = ref, ""

    if not base:
        if local_root is None:
            raise ValueError(f"Local $ref without document root: {ref}")
        target = _resolve_pointer(local_root, fragment) if fragment else local_root
        return _bundle_node(_deep_copy(target), store, stack, local_root)

    if base not in store:
        raise KeyError(f"Unresolved $ref base: {base}")
    if base in stack:
        # Keep cyclic refs as $ref stubs to avoid infinite expansion.
        return {"$ref": ref}

    document = store[base]
    target = _resolve_pointer(document, fragment) if fragment else document
    return _bundle_node(_deep_copy(target), store, stack + [base], document)


def _bundle_node(
    node: Any,
    store: dict[str, dict[str, Any]],
    stack: list[str],
    local_root: dict[str, Any] | None,
) -> Any:
    if isinstance(node, list):
        return [_bundle_node(item, store, stack, local_root) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node and isinstance(node["$ref"], str) and len(node) == 1:
        return _resolve_ref(node["$ref"], store, stack, local_root)

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "$ref" and isinstance(value, str):
            # Mixed $ref + siblings: expand ref and merge siblings on top.
            expanded = _resolve_ref(value, store, stack, local_root)
            if isinstance(expanded, dict):
                out.update(expanded)
            else:
                out[key] = value
            continue
        out[key] = _bundle_node(value, store, stack, local_root)
    return out


def _bundle_schema(schema: dict[str, Any], store: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema_id = schema.get("$id")
    stack = [schema_id] if isinstance(schema_id, str) else []
    root = _deep_copy(schema)
    bundled_any = _bundle_node(root, store, stack, root)
    if not isinstance(bundled_any, dict):
        raise TypeError("Bundled schema must be an object")
    bundled: dict[str, Any] = bundled_any
    # Keep identity metadata; drop external $id to avoid remote fetch hints.
    bundled.pop("$schema", None)
    if "title" not in bundled and isinstance(schema.get("title"), str):
        bundled["title"] = schema["title"]
    return bundled


def _schema_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".schema.json"):
        return name[: -len(".schema.json")]
    return path.stem


def _normalize_python_source(source: str) -> str:
    # Strip volatile timestamps/comments from datamodel-codegen.
    lines = []
    for line in source.splitlines():
        if line.startswith("#   timestamp:"):
            continue
        if line.startswith("# generated by datamodel-codegen"):
            continue
        if line.startswith("#   filename:"):
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines).strip() + "\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    return GENERATED_NOTICE_PY + text


def _normalize_ts_source(source: str) -> str:
    text = source.strip() + "\n"
    # Drop generator banner if present.
    text = re.sub(r"^/\*[\s\S]*?\*/\s*", "", text, count=1)
    return GENERATED_NOTICE_TS + text.strip() + "\n"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    completed = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"  {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _find_datamodel_codegen() -> list[str]:
    exe = shutil.which("datamodel-codegen")
    if exe:
        return [exe]
    # Fallback to module invocation (covers --user installs off PATH).
    return [sys.executable, "-m", "datamodel_code_generator"]


def _generate_python(bundled_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear previous generated modules (keep directory).
    for path in out_dir.glob("*.py"):
        path.unlink()

    init_exports: list[str] = []
    codegen = _find_datamodel_codegen()

    for schema_path in sorted(bundled_dir.glob("*.schema.json")):
        stem = _schema_stem(schema_path)
        module_name = stem.replace(".", "_").replace("-", "_")
        target = out_dir / f"{module_name}.py"
        tmp_out = out_dir / f".{module_name}.tmp.py"
        cmd = [
            *codegen,
            "--input",
            str(schema_path),
            "--input-file-type",
            "jsonschema",
            "--output",
            str(tmp_out),
            "--output-model-type",
            "typing.TypedDict",
            "--target-python-version",
            "3.11",
            "--use-standard-collections",
            "--use-union-operator",
            "--disable-timestamp",
            "--strict-nullable",
            "--collapse-root-models",
            "--class-name",
            _class_name_for_stem(stem),
        ]
        _run(cmd)
        raw = tmp_out.read_text(encoding="utf-8")
        tmp_out.unlink(missing_ok=True)
        target.write_text(_normalize_python_source(raw), encoding="utf-8")
        init_exports.append(module_name)

    init_lines = [
        GENERATED_NOTICE_PY.rstrip(),
        '"""Generated Nexus contract TypedDict modules."""',
        "",
    ]
    for module_name in init_exports:
        init_lines.append(f"from .{module_name} import *  # noqa: F403")
    init_lines.append("")
    init_lines.append("__all__ = [")
    for module_name in init_exports:
        init_lines.append(f'    "{module_name}",')
    init_lines.append("]")
    init_lines.append("")
    (out_dir / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")


def _class_name_for_stem(stem: str) -> str:
    # project-initialization-result.v1 -> ProjectInitializationResultV1
    base, _, version = stem.partition(".v")
    parts = [p for p in re.split(r"[-_]", base) if p]
    name = "".join(p[:1].upper() + p[1:] for p in parts)
    if version:
        name = f"{name}V{version.replace('.', '_')}"
    return name


def _generate_typescript(bundled_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in out_dir.glob("*.ts"):
        path.unlink()

    # Install/use json-schema-to-typescript via npx for reproducibility.
    compile_script = """
const fs = require('fs');
const path = require('path');
const { compile } = require('json-schema-to-typescript');

async function main() {
  const inputDir = process.argv[2];
  const outputDir = process.argv[3];
  const files = fs.readdirSync(inputDir).filter((f) => f.endsWith('.schema.json')).sort();
  const exports = [];
  for (const file of files) {
    const schemaPath = path.join(inputDir, file);
    const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
    const stem = file.replace(/\\.schema\\.json$/, '');
    const typeName = stem
      .split('.')[0]
      .split('-')
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join('') + (stem.includes('.v') ? 'V' + stem.split('.v')[1].replace(/\\./g, '_') : '');
    const ts = await compile(schema, typeName, {
      bannerComment: '',
      cwd: inputDir,
      declareExternallyReferenced: true,
      enableConstEnums: false,
      unreachableDefinitions: false,
      unknownAny: false,
      style: { singleQuote: true, semi: true },
    });
    const outName = stem.replace(/\\./g, '_') + '.ts';
    fs.writeFileSync(path.join(outputDir, outName), ts, 'utf8');
    exports.push(outName.replace(/\\.ts$/, ''));
  }
  const indexLines = [
    "export type { ProjectInitializationResult, Artifact }"
      + " from './project-initialization-result_v1';",
    "export type { Project } from './project_v1';",
    "export type { UserTurn } from './user-turn_v1';",
    "export type { TurnRoute } from './turn-route_v1';",
    "export type { WorkflowRun } from './workflow-run_v1';",
    "export type { VeraResponse } from './vera-response_v1';",
    "export type { OpenQuestion } from './open-question_v1';",
    "export type { ValidationIssue } from './validation-issue_v1';",
    "export type { ProjectBriefContent } from './project-brief_v1';",
    "export type { RequirementSetContent } from './requirement-set_v1';",
    "export type { FunctionalArchitectureContent } from './functional-architecture_v1';",
    "export type { NextActionContent } from './next-action_v1';",
    "export type { ArtifactEnvelope } from './artifact-envelope_v1';",
    "export type { ArtifactStatus } from './artifact-status_v1';",
  ];
  const index = indexLines.join('\\n') + '\\n';
  fs.writeFileSync(path.join(outputDir, 'index.ts'), index, 'utf8');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""
    with tempfile.TemporaryDirectory(prefix="nexus-ts-codegen-") as tmp:
        tmp_path = Path(tmp)
        script_path = tmp_path / "generate_ts.js"
        script_path.write_text(compile_script, encoding="utf-8")
        pkg = {
            "name": "nexus-contracts-ts-codegen",
            "private": True,
            "dependencies": {"json-schema-to-typescript": "15.0.4"},
        }
        _write_json(tmp_path / "package.json", pkg)
        _run(["npm", "install", "--silent", "--no-fund", "--no-audit"], cwd=tmp_path)
        _run(
            ["node", str(script_path), str(bundled_dir), str(out_dir)],
            cwd=tmp_path,
        )

    for path in sorted(out_dir.glob("*.ts")):
        path.write_text(_normalize_ts_source(path.read_text(encoding="utf-8")), encoding="utf-8")


def _content_fingerprint(directory: Path) -> str:
    digest = hashlib.sha256()
    if not directory.exists():
        return digest.hexdigest()
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        rel = path.relative_to(directory).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def generate(*, check: bool = False) -> int:
    store = _load_schemas_by_id()
    schemas_by_stem = {_schema_stem(p): _load_json(p) for p in _iter_schema_files()}

    missing = [s for s in PUBLIC_SCHEMA_STEMS if s not in schemas_by_stem]
    if missing:
        raise SystemExit(f"Missing expected schemas for generation: {missing}")

    before_py = _content_fingerprint(GENERATED_PYTHON)
    before_ts = _content_fingerprint(GENERATED_TYPESCRIPT)

    with tempfile.TemporaryDirectory(prefix="nexus-schema-bundle-") as tmp:
        bundled_dir = Path(tmp) / "bundled"
        bundled_dir.mkdir(parents=True, exist_ok=True)
        for stem in PUBLIC_SCHEMA_STEMS:
            schema = schemas_by_stem[stem]
            bundled = _bundle_schema(schema, store)
            _write_json(bundled_dir / f"{stem}.schema.json", bundled)

        _generate_python(bundled_dir, GENERATED_PYTHON)
        _generate_typescript(bundled_dir, GENERATED_TYPESCRIPT)

    # Remove legacy placeholders if present.
    for keep in (GENERATED_PYTHON / ".gitkeep", GENERATED_TYPESCRIPT / ".gitkeep"):
        if keep.exists():
            keep.unlink()

    after_py = _content_fingerprint(GENERATED_PYTHON)
    after_ts = _content_fingerprint(GENERATED_TYPESCRIPT)

    print("contracts: generated Python types -> packages/contracts/generated/python/")
    print("contracts: generated TypeScript types -> packages/contracts/generated/typescript/")

    if check and (before_py != after_py or before_ts != after_ts):
        print(
            "contracts: generated types are stale; run `make generate-contract-types`",
            file=sys.stderr,
        )
        return 1
    if check:
        print("contracts: generated types are up to date")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if regeneration would change committed generated files.",
    )
    args = parser.parse_args()
    try:
        raise SystemExit(generate(check=args.check))
    except Exception as exc:  # noqa: BLE001 - surface generator failures clearly
        print(f"contracts: generate-contract-types failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
