# Production Readiness Checklist

Status values: `PASS`, `FAIL`, `NEEDS REVIEW`. This checklist existing does **not** mean Fitora is legally compliant or production-ready — it tracks engineering + legal self-assessment status, to be verified before any real launch.

## Authentication
| Item | Status | Notes |
|---|---|---|
| Password security (Argon2id) | NEEDS REVIEW | Implementation in progress |
| Session security | NEEDS REVIEW | |
| Token security (JWT rotation) | NEEDS REVIEW | |
| Account recovery | NEEDS REVIEW | |

## Authorization
| Item | Status | Notes |
|---|---|---|
| Every endpoint checked | NEEDS REVIEW | |
| Every user-owned resource checked | NEEDS REVIEW | |
| IDOR protection | NEEDS REVIEW | |

## Data
| Item | Status | Notes |
|---|---|---|
| Encryption (at rest/in transit) | NEEDS REVIEW | Depends on hosting provider selection |
| Data minimization | NEEDS REVIEW | Schema designed with this in mind — see `database-schema.md` |
| Retention | NEEDS REVIEW | Defined in `data-flow.md`, not yet enforced by code |
| Deletion | NEEDS REVIEW | |
| Export | NEEDS REVIEW | |

## AI
| Item | Status | Notes |
|---|---|---|
| Prompt injection | NEEDS REVIEW | Design in `ai-safety.md`, not yet implemented |
| Data leakage | NEEDS REVIEW | |
| Tool authorization | NEEDS REVIEW | |
| Unsafe health advice | NEEDS REVIEW | |
| Output validation | NEEDS REVIEW | |

## Files
| Item | Status | Notes |
|---|---|---|
| Upload validation | NEEDS REVIEW | Not yet implemented |
| Storage security | NEEDS REVIEW | Provider not yet selected |
| Access controls | NEEDS REVIEW | |

## Infrastructure
| Item | Status | Notes |
|---|---|---|
| Secrets | NEEDS REVIEW | `.env.example` in place, real secret management TBD |
| Database | NEEDS REVIEW | |
| Backups | NEEDS REVIEW | Not yet implemented |
| Logging | NEEDS REVIEW | |
| Monitoring | NEEDS REVIEW | Not yet implemented |

## Legal
| Item | Status | Notes |
|---|---|---|
| Privacy Policy | NEEDS REVIEW | Draft exists, needs legal review |
| Terms | NEEDS REVIEW | Draft exists, needs legal review |
| Health disclaimer | NEEDS REVIEW | Draft exists, needs legal review |
| Consent | NEEDS REVIEW | Design in `data-flow.md`, not yet implemented |
| Third-party processors | NEEDS REVIEW | None selected yet |
| Jurisdiction review | NEEDS REVIEW | See `compliance-checklist.md` |

This document will be updated as each item is actually implemented and verified — not marked PASS speculatively.
