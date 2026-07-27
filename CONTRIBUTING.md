# Contributing to Nexus

Thank you for contributing. This document covers human and coding-agent contribution expectations. Coding agents must also follow [`AGENTS.md`](./AGENTS.md), which is authoritative when guidance differs.

## Branch conventions

Preferred format:

```text
<type>/<issue-number>-<short-description>
```

Allowed types: `feat`, `fix`, `refactor`, `test`, `docs`, `infra`, `chore`, `spike`, `release`, `hotfix`.

**Coding agents:** branch naming is mandatory. If no issue exists, ask a human for an issue number (or create an issue) before opening an implementation branch.

**Humans:** strongly encouraged to follow the same format. Repository CI does **not** hard-block human branch naming.

Direct pushes to `main` should be disabled through GitHub branch-protection settings once the repository exists.

## Commit conventions

Preferred format:

```text
<type>(<scope>): <imperative description>
```

**Coding agents:** commit conventions are mandatory.

**Humans:** strongly encouraged to follow the same format. CI does **not** hard-block human commit messages.

Keep commits focused on one logical change.

## Pull requests

1. Open a PR against `main` from a feature branch.
2. Use the repository pull-request template.
3. Fill in why, what changed, architecture impact, validation, risks, and checklist items.
4. Do not claim tests passed unless they were actually run.

PR titles should follow `<type>(<scope>): <description>`.

**Coding agents:** PR title and template sections are mandatory.

**Humans:** strongly encouraged to follow the same conventions.

## Testing expectations

- Behavior changes require a unit test, integration test, evaluation, or combination of these.
- Contract changes require contract/compatibility tests.
- Prefer fixtures over uncontrolled external services.
- Do not weaken tests merely to make a change pass.
- Run `make check` before requesting review.

## Documentation rules

- Durable docs belong under `docs/`.
- Module purpose belongs in that module’s single `README.md`.
- Do not create summary, status, plan, or completion Markdown files.
- Update existing documents in place instead of adding parallel docs.
- See `AGENTS.md` for the full Markdown allowlist and prohibited filenames.

## Architecture boundaries

Respect module ownership described in `AGENTS.md` and each module README:

- apps may depend on agents and packages;
- agents may depend on packages and tools;
- packages must not depend on apps or domain agents;
- no circular dependencies.

Do not add a new top-level directory without human approval and an ADR.

## Architecture Decision Records (ADRs)

Propose durable architectural decisions as:

```text
docs/decisions/ADR-NNNN-short-description.md
```

Use an architecture-proposal issue when the decision is still under discussion. Accepted decisions belong in `docs/decisions/` and must be linked from `docs/index.md`.

## Contract changes

- Shared agent communication uses `packages/contracts`.
- Public schemas require explicit versions.
- Additive optional fields may keep the current major version.
- Breaking changes require a new major version and contract tests.
- Do not silently change public contracts.

## Definition of done

A change is ready for review when:

- it lives in the correct owning module;
- architectural boundaries are respected;
- contracts remain compatible or are explicitly versioned;
- tests and evaluations are updated;
- documentation is updated in place;
- `make check` passes;
- no secrets or generated artifacts were added;
- no prohibited Markdown files were added.
