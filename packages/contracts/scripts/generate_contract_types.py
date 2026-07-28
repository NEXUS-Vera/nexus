from __future__ import annotations

import sys


def main() -> None:
    # This phase intentionally does not implement a full schema->types generator.
    #
    # Reasons:
    # - The artifact union is a discriminated `oneOf` with strict content payloads.
    # - Cross-record invariants (semantic validation) cannot be expressed as static types
    #   without drift risk in this repo phase.
    #
    # Follow-up work can introduce a deterministic generator once a tool is selected
    # that can represent these unions precisely in both Python and TypeScript.
    print("contracts: generate-contract-types is not implemented for v1 yet.")
    print("contracts: generated/python and generated/typescript remain as placeholders.")
    sys.exit(1)


if __name__ == "__main__":
    main()
