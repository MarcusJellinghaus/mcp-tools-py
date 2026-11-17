# Security Policy

## Reporting a Vulnerability

Report vulnerabilities through GitHub private vulnerability reporting only: [report a vulnerability](https://github.com/MarcusJellinghaus/mcp-tools-py/security/advisories/new).

Do not open public issues for security problems.

## Response

Reports are handled on a best-effort basis. There is no fixed response time.

## Supported Versions

Only the latest release on PyPI receives security fixes.

## Scope

In scope are bypasses of intended restrictions, such as:

- permission gates
- the issue status workflow (e.g. promoting issues without being trusted)
- credential handling

## Threat Model

Issue bodies and comments from untrusted users are untrusted LLM input. An issue body must be trusted — by its author or its last editor — before automated workflows run on it; untrusted bodies are skipped or opened review-only. Feedback counts only from trusted authors (`OWNER`, `MEMBER`, `COLLABORATOR`, or allowlisted). Reports that bypass this are in scope.

See [Issue body trust](https://github.com/MarcusJellinghaus/mcp_coder/blob/main/docs/repository-setup/github.md#issue-body-trust) and [Trust and Validation](https://github.com/MarcusJellinghaus/mcp_coder/blob/main/docs/repository-setup/github.md#trust-and-validation) in the mcp-coder repository.
