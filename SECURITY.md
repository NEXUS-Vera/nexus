# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `main` (unreleased foundation) | Yes |

Support channels and versioning will be updated as releases are published.

## Reporting a vulnerability

Do **not** open a public GitHub issue for security vulnerabilities.

Use GitHub private vulnerability reporting for the `NEXUS-Vera/nexus` repository once it is enabled by the organization:

1. Open the repository’s **Security** tab.
2. Choose **Report a vulnerability**.
3. Provide a clear description, impact assessment, and reproduction steps if available.

Until private vulnerability reporting is configured for the organization, contact a repository maintainer through a private channel. Do not disclose vulnerability details publicly before maintainers have reviewed and addressed the report.

## Secrets and credentials

- Never commit secrets, API keys, tokens, certificates, or credentials.
- Prefer `.env.example` for non-secret configuration templates.
- If credentials are exposed, rotate them immediately and notify maintainers.

## Infrastructure and production changes

Production configuration and infrastructure apply/destroy operations require explicit human authorization. Do not change production systems as part of unrelated work.
