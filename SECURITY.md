# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in Fitora, please report it privately rather than opening a public issue. Open a GitHub issue marked `security` with minimal public detail and request a private channel, or contact the repository owner directly.

Do not include real user data, live credentials, or exploit payloads that could affect production systems in a public report.

## Scope

This policy covers the `backend/` API, `mobile/` client, and infrastructure configuration in this repository. It does not cover third-party providers (AI, food database, storage, email) — report issues in those directly to the provider, and see [`docs/third-party-services.md`](docs/third-party-services.md) for what data each one receives.

## Supported practices

Fitora's security posture is described in detail in:

- [`docs/security-threat-model.md`](docs/security-threat-model.md) — threats, impact, likelihood, mitigations
- [`docs/ai-safety.md`](docs/ai-safety.md) — AI-specific threats (prompt injection, tool authorization, output validation)
- [`docs/production-readiness.md`](docs/production-readiness.md) — pre-launch audit checklist

Baseline practices enforced across the codebase:

- Argon2id password hashing; passwords and tokens are never logged.
- JWT access tokens (short-lived) + rotating refresh tokens; sessions can be invalidated server-side.
- Every endpoint that touches a user-owned resource verifies ownership server-side — client-supplied IDs are never trusted alone (IDOR protection).
- All database access goes through the ORM / parameterized queries — no raw SQL built from user input.
- Rate limiting on authentication and AI endpoints.
- File uploads are validated by size, MIME type, and extension, stored in private buckets, and served only via signed URLs.
- Secrets live in environment variables only; `.env` is git-ignored and `.env.example` documents every variable without real values.
- CORS is never wildcarded in production.
- Internal errors (stack traces, SQL errors) are never exposed to clients.

## Before every commit / push

1. Search the diff for API keys, passwords, tokens.
2. Confirm `.env` and other secret files are not staged.
3. Run lint, type checks, and tests.
4. Review changed files for anything unexpected.

If a secret is ever committed: revoke it, rotate it, and remove it from Git history before pushing further.
