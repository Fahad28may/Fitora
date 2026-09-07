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
| Data minimization | NEEDS REVIEW | Schema designed with this in mind — see `database-schema.md`. Outbound requests are scoped deliberately: barcode lookup sends only the barcode, AI coach sends only already-user-scoped app data (never email/name/tokens) |
| Retention | NEEDS REVIEW | Defined in `data-flow.md`, not yet enforced by code |
| Deletion | NEEDS REVIEW | |
| Export | NEEDS REVIEW | |

## AI
| Item | Status | Notes |
|---|---|---|
| Prompt injection | NEEDS REVIEW | Architectural defenses implemented (data/instruction separation, schema validation, length limits — see `ai-safety.md`); not adversarially tested against a live model |
| Data leakage | NEEDS REVIEW | Only dashboard/weight/workout data sent to AI provider, confirmed by code review; provider's own retention/training policy not yet independently verified |
| Tool authorization | PASS | Tool-calling built as propose→confirm (`log_weight`/`log_water`/`log_food`). Write path (`/ai/actions/confirm`) calls no model, takes `user_id` from the session, re-validates every parameter against manual-endpoint bounds, and enforces existing ownership checks. Enforced by construction and covered by `tests/test_ai_actions.py`; does not depend on model compliance. Re-review when `create_workout`/`create_meal` are added |
| Unsafe health advice | NEEDS REVIEW | System-prompt rules in place; actual model compliance not verified without a live `AI_API_KEY` |
| Output validation | PASS | Food parsing: Pydantic schema + one retry + 422 fallback. Coach: non-empty, length-capped |

## Files
| Item | Status | Notes |
|---|---|---|
| External data validation | PASS | Crowd-sourced nutrition from Open Food Facts is rejected unless it parses and falls inside per-100 g plausibility bounds (calories ≤ 900, each macro ≤ 100 g, macros summing ≤ 105 g); provider text is whitespace-collapsed and truncated to column limits, and the barcode is digits-only-validated before being interpolated into an outbound URL. Covered by `tests/test_food_db_parsing.py` and `tests/test_barcode.py` |
| Upload validation | NEEDS REVIEW | Magic-byte image sniff (JPEG/PNG/WebP — client Content-Type not trusted) + 10 MiB size cap enforced in `progress_photo_service`. Deeper validation (full decode / re-encode to strip metadata) is a documented future hardening, not yet done |
| Storage security | NEEDS REVIEW | MinIO/S3 selected; private bucket required, reads only via short-lived presigned URLs (default 15 min), keys server-side only. Bucket privacy + TLS on the endpoint depend on how ops provisions MinIO — verify before launch |
| Access controls | PASS | Every photo is authorized by DB row ownership (user_id from session), not by object-key guessability; delete is ownership-checked. Covered by `tests/test_progress_photos.py` |

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
| Third-party processors | NEEDS REVIEW | Three selected, all optional and all off unless configured: OpenRouter (AI), MinIO (photos — self-hosted, so not a third party in practice), Open Food Facts (barcode lookup, barcode only). Each provider's own retention/logging policy still needs independent review — see `third-party-services.md` |
| Jurisdiction review | NEEDS REVIEW | See `compliance-checklist.md` |

This document will be updated as each item is actually implemented and verified — not marked PASS speculatively.
