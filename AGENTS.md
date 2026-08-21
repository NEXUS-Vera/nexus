# AGENTS.md

Canonical operating contract for all coding agents working in the Nexus monorepo.

Cursor rules, Claude instructions, and any other coding-agent guidance **must defer to this file**. Do not duplicate or contradict these rules elsewhere.

---

## 1. Repository purpose

Nexus is a modular agentic engineering platform in which:

- **Vera** is the global orchestrator that routes and coordinates work.
- **Domain agents** perform bounded specialist work (for example, embedded systems).
- **Shared packages** provide contracts, runtime, memory, retrieval, board state, observability, and evaluation helpers.
- **Deterministic tools** perform verifiable calculations and operations independent of model nondeterminism.

This repository is one modular monorepo. Do not create separate repositories for individual agents without an explicit ADR and human approval.

---

## 2. Mandatory workflow for coding agents

### Before editing code

1. Read `AGENTS.md`.
2. Identify the owning module.
3. Inspect the relevant module `README.md`.
4. Search for existing implementations before creating new files.
5. Determine whether the change affects a public contract.
6. Determine which tests or evaluations must change.
7. Avoid unrelated refactors.

### Before declaring completion

1. Run the relevant formatter.
2. Run linting.
3. Run type checking.
4. Run relevant unit tests.
5. Run relevant integration tests.
6. Run relevant evaluations.
7. Run `make check`.
8. Review the final Git diff.
9. Confirm no secrets, generated artifacts, logs, or prohibited documentation files were added.

---

## 3. Architectural boundaries

- Applications may depend on agents and shared packages.
- Agents may depend on shared packages and tools.
- Shared packages must not depend on applications.
- Shared packages must not depend on individual domain agents.
- Domain agents must not import another domain agent’s private implementation.
- Vera communicates with agents through shared contracts and interfaces.
- Tools must not depend on UI code.
- Contracts must not depend on concrete implementations.
- No circular dependencies are permitted.
- Do not place domain-specific logic in `packages/agent-runtime`.
- Do not place reusable platform logic inside a specific agent.

### Ownership model

| Area | Contains |
| --- | --- |
| `apps/` | Deployable applications only |
| `agents/` | Domain-agent packages |
| `packages/` | Reusable platform capabilities |
| `tools/` | Deterministic, independently testable capabilities |
| `knowledge/` | Manifests, schemas, fixtures, metadata, allowlists, hashes |
| `evals/` | Agent-behavior evaluations |
| `infra/` | Deployment and local-infrastructure configuration |
| `docs/` | Durable long-form documentation |

Shared business logic must not be placed directly in `apps/`.

---

## 4. File and folder creation rules

- Never create a new top-level directory without explicit human approval and an ADR.
- Do not create files merely to summarize completed work.
- Update an existing README or durable document instead of creating a new Markdown file.
- Do not create duplicate implementations suffixed with `new`, `final`, `v2`, `fixed`, `copy`, or similar names.
- Replace or migrate existing implementations intentionally.
- Do not create empty abstractions for hypothetical future needs.
- Do not create a separate service, agent, package, or tool unless it has a clearly distinct responsibility.

---

## 5. Naming conventions

### Directories

Use `kebab-case`.

Examples: `embedded-systems`, `agent-runtime`, `model-gateway`, `power-calculator`.

### Python files and modules

Use `snake_case.py`.

- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### TypeScript files

Use `kebab-case.ts` and `kebab-case.tsx`.

- Classes, types, interfaces, enums, and React components: `PascalCase`
- Functions and variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`

### Tests

Python:

```text
test_<unit>.py
```

TypeScript:

```text
<unit>.test.ts
<component>.test.tsx
<workflow>.e2e.test.ts
```

Evaluations:

```text
<capability>.<scenario>.eval.yaml
```

### Schemas

Use explicit versions:

```text
task-contract.v1.schema.json
agent-result.v1.schema.json
board-update.v1.schema.json
evidence-record.v1.schema.json
```

Never use names such as `final`, `latest`, `new`, `newest`, `updated`, `fixed`, or `v2-final` unless `v2` is a legitimate public contract version.

---

## 6. Branch conventions for coding agents

These rules are **mandatory for coding agents**. Humans are encouraged, but not technically blocked, from using them.

Coding-agent branches must follow:

```text
<type>/<issue-number>-<short-description>
```

Allowed types: `feat`, `fix`, `refactor`, `test`, `docs`, `infra`, `chore`, `spike`, `release`, `hotfix`.

Examples:

```text
feat/142-embedded-power-tool
fix/218-board-state-race
docs/94-monorepo-adr
infra/255-staging-observability
```

Coding agents must **not** create branches such as `claude-work`, `cursor-changes`, `updates`, `fixes`, `new-branch`, `final`, or `test-branch`.

When no GitHub issue exists for agent-generated work, the agent must ask the human to provide an issue number or create an issue before creating the implementation branch.

Exception for repository bootstrap only: `chore/1-initialize-nexus-monorepo`.

---

## 7. Commit conventions for coding agents

These rules are **mandatory for coding agents**. Humans are encouraged, but not technically blocked, from using them.

Use:

```text
<type>(<scope>): <imperative description>
```

Allowed common scopes: `repo`, `web`, `api`, `worker`, `desktop`, `vera`, `embedded`, `runtime`, `contracts`, `board`, `memory`, `persistence`, `retrieval`, `models`, `observability`, `evals`, `infra`, `ci`, `deps`, `docs`.

Examples:

```text
chore(repo): initialize nexus monorepo structure
feat(embedded): add typed power calculation interface
fix(board): prevent stale project state writes
test(vera): add cross-domain routing evaluations
```

Do not use commit messages such as `updates`, `changes`, `fix stuff`, `final version`, `claude changes`, `cursor work`, or `misc`.

Keep each commit focused on one logical change.

---

## 8. Pull-request conventions for coding agents

These rules are **mandatory for coding agents**. Humans are encouraged, but not technically blocked, from using them.

PR titles must follow:

```text
<type>(<scope>): <description>
```

Every coding-agent PR must include:

- why the change is needed;
- what changed;
- architecture impact;
- validation performed;
- agent or evaluation impact;
- risks;
- relevant screenshots or artifacts;
- confirmation that no prohibited documentation or generated artifacts were added.

Coding agents must not claim tests passed unless they were actually run successfully.

---

## 9. Contract policy

- All shared agent communication must use `packages/contracts`.
- Public schemas must have explicit versions.
- Additive optional changes may preserve the current major version.
- Removing, renaming, or changing required fields requires a new major version.
- Agents must reject unsupported major versions.
- Contract changes require contract tests.
- Public contract changes must not be made silently.
- Domain agents may define private internal schemas, but cross-agent communication must use shared contracts.

---

## 10. Prompt policy

- Do not bury important prompts inside arbitrary source strings.
- Agent prompts belong in the owning agent’s `src/prompts` directory.
- Prompts should be separated into system, workflow, and reusable policy fragments only when needed.
- Prompt changes that affect behavior require evaluation changes.
- Do not create a new prompt file for trivial wording changes.
- Prompt versions should change only when behavior or contract meaningfully changes.

---

## 11. Testing and evaluation policy

- Every behavior change requires a test, an evaluation, or both.
- Unit tests validate deterministic code.
- Integration tests validate module interaction.
- Evaluations validate model and agent behavior.
- Contract changes require compatibility tests.
- Agent changes must include relevant evaluation coverage.
- Tests must not rely on uncontrolled external services.
- Use fixtures for repeatable evaluation inputs.
- Do not weaken tests merely to make a change pass.

---

## 12. Generated artifacts policy

Never commit by default:

```text
logs/
outputs/
results/
tmp/
coverage/
dist/
build/
vector-store/
embeddings/
model-cache/
uploads/
generated-notebooks/
.env
.env.*
```

Allow `.env.example`.

Do not commit secrets, credentials, API keys, user-uploaded data, production logs, model weights, generated vector indexes, caches, downloaded datasheets, or large binary artifacts.

---

## 13. Security policy

- Never commit secrets.
- Never log sensitive credentials.
- Do not weaken authentication or authorization.
- Use least-privilege permissions.
- Do not execute destructive infrastructure actions without explicit human authorization.
- Do not change production configuration as part of unrelated work.
- External inputs must be validated.
- Tool execution must use typed inputs and explicit permission boundaries.
- Any suspected secret exposure must be reported immediately.

---

## 14. Documentation policy

### Allowed root Markdown files

```text
README.md
AGENTS.md
CLAUDE.md
CONTRIBUTING.md
SECURITY.md
CODE_OF_CONDUCT.md
CHANGELOG.md
```

### Module Markdown

A major module may contain one `README.md` explaining purpose, public boundary, what belongs there, what must not be placed there, and future development expectations.

### Durable documentation

Long-form documentation belongs only under `docs/`. Architecture decisions use `docs/decisions/ADR-NNNN-short-description.md`.

### Prohibited files

Do not create files such as:

```text
IMPLEMENTATION_SUMMARY.md
PHASE_1_COMPLETE.md
CURRENT_STATUS.md
FINAL_NOTES.md
ARCHITECTURE_NEW.md
FIXES_DONE.md
CLAUDE_SUMMARY.md
PROJECT_PLAN.md
TODO_NOTES.md
```

Temporary work belongs in GitHub issues, pull-request descriptions, or issue comments.

> Coding agents must place completion summaries in their final response or pull-request description, never in newly created repository files.

---

## 15. Definition of done

A coding-agent change is complete only when:

- it is placed in the correct module;
- architectural boundaries are respected;
- public contracts remain compatible or are versioned;
- tests and evaluations are updated;
- `make check` passes;
- relevant documentation is updated in place;
- the final diff has been reviewed;
- no secrets or prohibited artifacts were added;
- commit and PR conventions are followed.
