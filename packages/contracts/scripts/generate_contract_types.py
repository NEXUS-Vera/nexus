#!/usr/bin/env python3
"""Deterministically generate Python and TypeScript types from JSON Schemas.

Generated output lives under:
  packages/contracts/generated/python/
  packages/contracts/generated/typescript/

Do not edit generated files by hand.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
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
    "component-plan.v1",
    "component-category.v1",
    "component-role.v1",
    "selection-constraint.v1",
    "component-candidate.v1",
    "selection-decision.v1",
    "compatibility-check.v1",
    "component-plan-coverage-summary.v1",
    "artifact-type.v1",
    "artifact-type-definition.v1",
    "artifact-command.v1",
    "artifact-command-result.v1",
    "artifact-proposal.v1",
    "workspace-descriptor.v1",
    "workspace-snapshot.v1",
    "workspace-draft-state.v1",
    "workspace-file.v1",
    "execution-request.v1",
    "execution-run.v1",
    "execution-result.v1",
    "execution-command-spec.v1",
    "execution-job.v1",
    "execution-log-chunk.v1",
    "produced-output.v1",
    "runtime-capability.v1",
    "external-workspace-reference.v1",
    "project-event.v1",
    "project-board-projection.v1",
    "artifact-authority.v1",
    "approval-requirement.v1",
    "consequence-level.v1",
    "project-graph-node.v1",
    "project-graph-edge.v1",
    "graph-traversal-result.v1",
    "validation-issue.v1",
    "open-question.v1",
    "vera-response.v1",
    "project-initialization-result.v1",
    "project-current-state.v1",
    "project-history.v1",
    "project-turn-result.v1",
    "project-change-intent.v1",
    "project-impact-analysis.v1",
    "artifact-dependency.v1",
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


def _merge_object_schemas(parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge allOf object schemas into one object for stricter TypeScript output.

    json-schema-to-typescript emits permissive `[k: string]: any` index signatures for
    allOf intersections. Collapsing compatible object allOf nodes preserves
    additionalProperties: false and keeps discriminated unions usable.
    """

    merged: dict[str, Any] = {"type": "object"}
    properties: dict[str, Any] = {}
    required: list[str] = []
    additional_false = False

    for part in parts:
        if part.get("type") not in (None, "object"):
            raise TypeError("Cannot collapse allOf containing non-object schemas")
        for key, value in part.items():
            if key in {"type", "properties", "required", "additionalProperties"}:
                continue
            # Prefer later sibling metadata when keys collide.
            merged[key] = value
        for key, value in (part.get("properties") or {}).items():
            properties[key] = value
        for key in part.get("required") or []:
            if key not in required:
                required.append(key)
        if part.get("additionalProperties") is False:
            additional_false = True

    merged["properties"] = properties
    if required:
        merged["required"] = required
    if additional_false:
        merged["additionalProperties"] = False
    return merged


def _collapse_allof(node: Any) -> Any:
    if isinstance(node, list):
        return [_collapse_allof(item) for item in node]
    if not isinstance(node, dict):
        return node

    collapsed = {key: _collapse_allof(value) for key, value in node.items()}
    allof = collapsed.get("allOf")
    if not isinstance(allof, list) or not allof:
        return collapsed

    # Arrays that combine items + contains/allOf must keep their array shape.
    if collapsed.get("type") == "array" or "items" in collapsed or "contains" in collapsed:
        return collapsed

    # Only collapse when every branch is a plain object schema (no nested combinators).
    object_parts: list[dict[str, Any]] = []
    for part in allof:
        if not isinstance(part, dict):
            return collapsed
        if any(k in part for k in ("allOf", "oneOf", "anyOf", "$ref", "contains")):
            return collapsed
        if part.get("type") not in (None, "object"):
            return collapsed
        if (
            "properties" not in part
            and "required" not in part
            and "additionalProperties" not in part
        ):
            return collapsed
        object_parts.append(part)

    if not object_parts:
        return collapsed

    merged = _merge_object_schemas(object_parts)
    for key, value in collapsed.items():
        if key == "allOf":
            continue
        if key in merged and key in {"properties", "required", "additionalProperties", "type"}:
            continue
        merged[key] = value
    return merged


def _strip_codegen_unsupported_keywords(node: Any) -> Any:
    """Remove JSON Schema keywords that json-schema-to-typescript mishandles.

    Runtime validation still enforces these via the canonical schemas. Stripping them
    for TypeScript generation avoids spurious `[k: string]: any` intersections from
    `contains`, `if`/`then`/`else`, and empty allOf leftovers.
    """

    if isinstance(node, list):
        return [_strip_codegen_unsupported_keywords(item) for item in node]
    if not isinstance(node, dict):
        return node

    skip = {"contains", "if", "then", "else"}
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in skip:
            continue
        out[key] = _strip_codegen_unsupported_keywords(value)

    allof = out.get("allOf")
    if isinstance(allof, list):
        filtered = [part for part in allof if isinstance(part, dict) and part]
        if not filtered:
            out.pop("allOf", None)
        else:
            out["allOf"] = filtered
            out = _collapse_allof(out)
    return out


def _prepare_schema_for_typescript(schema: dict[str, Any]) -> dict[str, Any]:
    prepared = _strip_codegen_unsupported_keywords(_deep_copy(schema))
    if not isinstance(prepared, dict):
        raise TypeError("Prepared TypeScript schema must be an object")
    return prepared


def _bundle_schema(schema: dict[str, Any], store: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema_id = schema.get("$id")
    stack = [schema_id] if isinstance(schema_id, str) else []
    root = _deep_copy(schema)
    bundled_any = _bundle_node(root, store, stack, root)
    if not isinstance(bundled_any, dict):
        raise TypeError("Bundled schema must be an object")
    bundled: dict[str, Any] = _collapse_allof(bundled_any)
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
    "export type { ProjectInitializationResult } from './project-initialization-result_v1';",
    "export type { ProjectCurrentState } from './project-current-state_v1';",
    "export type { ProjectHistory } from './project-history_v1';",
    "export type { ProjectTurnResult } from './project-turn-result_v1';",
    "export type { ProjectChangeIntent } from './project-change-intent_v1';",
    "export type { ProjectImpactAnalysis } from './project-impact-analysis_v1';",
    "export type { ArtifactDependency } from './artifact-dependency_v1';",
    "export type { Artifact } from './artifact_v1';",
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
    "export type { ComponentPlanContent } from './component-plan_v1';",
    "export type { ComponentCategory } from './component-category_v1';",
    "export type { ComponentRole } from './component-role_v1';",
    "export type { SelectionConstraint } from './selection-constraint_v1';",
    "export type { ComponentCandidate } from './component-candidate_v1';",
    "export type { SelectionDecision } from './selection-decision_v1';",
    "export type { CompatibilityCheck } from './compatibility-check_v1';",
    "export type { ComponentPlanCoverageSummary } from './component-plan-coverage-summary_v1';",
    "export type { ArtifactEnvelope } from './artifact-envelope_v1';",
    "export type { ArtifactStatus } from './artifact-status_v1';",
    "export type { ArtifactType } from './artifact-type_v1';",
    "export type { ArtifactTypeDefinition } from './artifact-type-definition_v1';",
    "export type { ArtifactCommand } from './artifact-command_v1';",
    "export type { ArtifactCommandResult } from './artifact-command-result_v1';",
    "export type { ArtifactProposal } from './artifact-proposal_v1';",
    "export type { WorkspaceDescriptor } from './workspace-descriptor_v1';",
    "export type { WorkspaceSnapshot } from './workspace-snapshot_v1';",
    "export type { WorkspaceDraftState } from './workspace-draft-state_v1';",
    "export type { WorkspaceFile } from './workspace-file_v1';",
    "export type { ExecutionRequest } from './execution-request_v1';",
    "export type { ExecutionRun } from './execution-run_v1';",
    "export type { ExecutionResult } from './execution-result_v1';",
    "export type { ExecutionCommandSpec } from './execution-command-spec_v1';",
    "export type { ExecutionJob } from './execution-job_v1';",
    "export type { ExecutionLogChunk } from './execution-log-chunk_v1';",
    "export type { ProducedOutput } from './produced-output_v1';",
    "export type { RuntimeCapability } from './runtime-capability_v1';",
    "export type { ExternalWorkspaceReference } from './external-workspace-reference_v1';",
    "export type { ProjectEvent } from './project-event_v1';",
    "export type { ProjectBoardProjection } from './project-board-projection_v1';",
    "export type { ArtifactAuthority } from './artifact-authority_v1';",
    "export type { ApprovalRequirement } from './approval-requirement_v1';",
    "export type { ConsequenceLevel } from './consequence-level_v1';",
    "export type { ProjectGraphNode } from './project-graph-node_v1';",
    "export type { ProjectGraphEdge } from './project-graph-edge_v1';",
    "export type { GraphTraversalResult } from './graph-traversal-result_v1';",
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
        try:
            _run(["npm", "install", "--silent", "--no-fund", "--no-audit"], cwd=tmp_path)
        except RuntimeError as exc:
            raise RuntimeError(
                "TypeScript generation requires network access to the npm registry "
                "to install json-schema-to-typescript@15.0.4."
            ) from exc
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
    for path in sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ):
        rel = path.relative_to(directory).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@contextlib.contextmanager
def _restore_on_failure(*dirs: Path) -> Iterator[None]:
    """Roll back generated output if generation does not complete.

    Generation clears its output directory before writing. Those directories are
    tracked in git, so without this a missing codegen tool or a bad schema left
    the working tree with the generated contracts deleted and no way back.
    """
    snapshot: dict[Path, bytes] = {}
    for directory in dirs:
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file():
                    snapshot[path] = path.read_bytes()
    try:
        yield
    except BaseException:
        for directory in dirs:
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file():
                        path.unlink()
        for path, data in snapshot.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        raise


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
        ts_bundled_dir = Path(tmp) / "bundled-ts"
        ts_bundled_dir.mkdir(parents=True, exist_ok=True)
        py_out_dir = Path(tmp) / "generated-python"
        ts_out_dir = Path(tmp) / "generated-typescript"
        py_out_dir.mkdir(parents=True, exist_ok=True)
        ts_out_dir.mkdir(parents=True, exist_ok=True)
        for stem in PUBLIC_SCHEMA_STEMS:
            schema = schemas_by_stem[stem]
            bundled = _bundle_schema(schema, store)
            _write_json(bundled_dir / f"{stem}.schema.json", bundled)
            _write_json(
                ts_bundled_dir / f"{stem}.schema.json",
                _prepare_schema_for_typescript(bundled),
            )

        _generate_python(bundled_dir, py_out_dir)
        _generate_typescript(ts_bundled_dir, ts_out_dir)

        # Replace destination directories only after both generations succeed;
        # restore the previous outputs if the swap itself fails.
        with _restore_on_failure(GENERATED_PYTHON, GENERATED_TYPESCRIPT):
            GENERATED_PYTHON.mkdir(parents=True, exist_ok=True)
            GENERATED_TYPESCRIPT.mkdir(parents=True, exist_ok=True)
            for path in GENERATED_PYTHON.glob("*.py"):
                path.unlink()
            for path in GENERATED_TYPESCRIPT.glob("*.ts"):
                path.unlink()
            for path in sorted(py_out_dir.glob("*.py")):
                (GENERATED_PYTHON / path.name).write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8"
                )
            for path in sorted(ts_out_dir.glob("*.ts")):
                (GENERATED_TYPESCRIPT / path.name).write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8"
                )

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
