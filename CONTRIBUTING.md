# Contributing to Fitora

## Development workflow

```text
PLAN → IMPLEMENT → TEST → SECURITY REVIEW → FIX → DOCUMENT → COMMIT → PUSH → NEXT FEATURE
```

Never skip testing because a feature "looks like it works."

## Commit style

Use conventional, scoped commit messages that represent a single logical unit of work:

```text
feat: add authentication system
fix: correct macro rounding in calorie calculator
security: harden authorization checks on meal endpoints
test: add nutrition calculation tests
docs: add privacy and security documentation
chore: initialize Fitora project
```

Avoid one giant commit for multiple unrelated changes.

## Before committing

- [ ] Tests pass (`backend`: pytest; `mobile`: relevant test runner)
- [ ] Lint passes
- [ ] Type checks pass
- [ ] No secrets in the diff (`git status`, review `git diff`)
- [ ] `.gitignore` still covers all local/secret files

## Backend setup

See [`backend/README.md`](backend/README.md).

## Mobile setup

See [`mobile/README.md`](mobile/README.md).

## Security & privacy expectations

Read [`SECURITY.md`](SECURITY.md) and [`docs/ai-safety.md`](docs/ai-safety.md) before touching authentication, authorization, file uploads, or anything that calls an AI provider. Security, privacy, and health-safety take priority over feature velocity — see the project's governing master prompt.
