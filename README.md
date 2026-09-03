# Fitora

Fitora is a privacy-first, AI-assisted personal fitness and nutrition application.

> Fitora provides general fitness and nutrition information and estimates. It is **not** medical advice and is not a substitute for a qualified healthcare professional. See [`docs/health-disclaimer.md`](docs/health-disclaimer.md).

## Philosophy

**Log → Understand → Track → Analyze → Improve**

Fitora helps users understand their nutrition, workouts, activity, habits, and progress in one place — without pretending to be a medical device.

## Repository layout

```text
backend/    FastAPI + PostgreSQL API
mobile/     Expo / React Native (TypeScript) client
docs/       Architecture, security, privacy, and compliance documentation
```

## Status

Early development (Phase 1: authentication, profile, goals, nutrition logging, calorie calculation, dashboard, weight tracking). See [`docs/roadmap.md`](docs/roadmap.md) for the full phased plan.

## Getting started

See [`backend/README.md`](backend/README.md) and [`mobile/README.md`](mobile/README.md) once those are scaffolded, and copy [`.env.example`](.env.example) to `.env` before running anything locally.

## Documentation

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture overview |
| [SECURITY.md](SECURITY.md) | Security policy and practices |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow |
| [docs/database-schema.md](docs/database-schema.md) | Data model |
| [docs/security-threat-model.md](docs/security-threat-model.md) | Threat model |
| [docs/data-flow.md](docs/data-flow.md) | Data flow / privacy-by-design |
| [docs/ai-safety.md](docs/ai-safety.md) | AI architecture, guardrails, cost control |
| [docs/third-party-services.md](docs/third-party-services.md) | External providers and data shared |
| [docs/compliance-checklist.md](docs/compliance-checklist.md) | Jurisdiction / regulation tracking |
| [docs/privacy-policy.md](docs/privacy-policy.md) | Privacy policy (draft, needs legal review) |
| [docs/terms-of-service.md](docs/terms-of-service.md) | Terms of service (draft, needs legal review) |
| [docs/health-disclaimer.md](docs/health-disclaimer.md) | Health/medical disclaimer |
| [docs/production-readiness.md](docs/production-readiness.md) | Pre-launch audit checklist |

## License

Not yet decided — do not treat this repository as open for reuse until a license is added.
