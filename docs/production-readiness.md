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
| Pagination / query bounds | PASS | Every list endpoint is bounded: food/exercise search take limit+offset (max 50), history is capped at 90 days, workout progress at 52 weeks, and the dashboard's session scan is limited. No endpoint returns an unbounded history |
| Data minimization | NEEDS REVIEW | Schema designed with this in mind — see `database-schema.md`. Outbound requests are scoped deliberately: barcode lookup sends only the barcode, AI coach sends only already-user-scoped app data (never email/name/tokens) |
| Retention | NEEDS REVIEW | Defined in `data-flow.md`. Account deletion is now enforced by code; time-based retention windows (session/IP-hash rolling window, backup expiry) are still documentation only |
| Deletion | PASS | `DELETE /account` removes the account and every row it owns, plus progress-photo objects in storage. Requires the current password *and* a typed confirmation phrase, so a stolen session alone can't destroy an account. Rows are deleted explicitly in dependency order rather than by DB cascade (a RESTRICT FK could block cascade ordering, and SQLite doesn't enforce FKs so a cascade version would only fail in production). Audit and consent records are anonymized, not erased. Covered by `tests/test_account.py` |
| Export | PASS | `GET /account/export` returns every category of user data as JSON, credentials excluded (asserted by test). Reachable from Settings → Privacy in the app |

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
| External data validation | PASS | Crowd-sourced nutrition from Open Food Facts is rejected unless it parses and falls inside per-100 g plausibility bounds (calories ≤ 900, each macro ≤ 100 g, macros summing ≤ 105 g); provider text is whitespace-collapsed and truncated to column limits, and the barcode is digits-only-validated before being interpolated into an outbound URL. Covered by `tests/test_food_db_parsing.py` and `tests/test_barcode.py`. Verified live against real Open Food Facts products (field names, the missing-serving-size fallback, and the unknown-barcode path all behave as the tests assume) |
| Upload validation | NEEDS REVIEW | Magic-byte image sniff (JPEG/PNG/WebP — client Content-Type not trusted) + 10 MiB size cap enforced in `progress_photo_service`. Deeper validation (full decode / re-encode to strip metadata) is a documented future hardening, not yet done |
| Storage security | NEEDS REVIEW | MinIO/S3 selected; private bucket required, reads only via short-lived presigned URLs (default 15 min), keys server-side only. Bucket privacy + TLS on the endpoint depend on how ops provisions MinIO — verify before launch |
| Access controls | PASS | Every photo is authorized by DB row ownership (user_id from session), not by object-key guessability; delete is ownership-checked. Covered by `tests/test_progress_photos.py` |

## Infrastructure
| Item | Status | Notes |
|---|---|---|
| Security headers / API hardening | PASS | nosniff, X-Frame-Options, Referrer-Policy, CORP, Permissions-Policy and a deny-all CSP on every response; HSTS only when the request arrived over HTTPS; 12 MiB request-body cap. Covered by `tests/test_security_headers.py` |
| Secrets | NEEDS REVIEW | `.env.example` in place, real secret management TBD |
| Database | NEEDS REVIEW | |
| Backups | NEEDS REVIEW | Not yet implemented |
| Logging | NEEDS REVIEW | Structured JSON logs, no secrets. Security-sensitive operations additionally recorded in `audit_events` (register, login success/failure, logout, consent change, export, deletion); the email on a failed login is hashed, never stored raw. Log shipping/retention not yet decided |
| Monitoring | NEEDS REVIEW | Not yet implemented |

## Resilience
| Item | Status | Notes |
|---|---|---|
| Duplicate-safe retries | PASS | Optional `Idempotency-Key` on `POST /food-diary`, `/water-entries`, `/weight-entries`, `/activity-entries`; keys scoped per user, reuse across endpoints is a 409. Covered by `tests/test_idempotency.py` |
| Offline logging | NEEDS REVIEW | Client outbox persists queued writes and replays them with their original key (`src/api/outbox.ts`, 13 tests). Only water quick-add currently routes through it |
| Idempotency key retention | NEEDS REVIEW | Keys are stored indefinitely and deleted with the account. A pruning job for keys older than the retry window is not yet written |

## Accessibility
| Item | Status | Notes |
|---|---|---|
| Screen reader names | PASS | Every TouchableOpacity/Pressable/TextInput/Switch in `app/` and `src/` has an accessible name, enforced by `src/ui/__tests__/accessibility.test.ts` which fails the build on a new unlabelled control |
| Not colour alone | PASS | Recommendation priority carries a text label beside its coloured rule; selected chips expose `accessibilityState.selected` |
| Contrast, touch targets, reduced motion | NEEDS REVIEW | Not audited against WCAG ratios; no reduced-motion handling (the app has little motion today) |

## Testing
| Item | Status | Notes |
|---|---|---|
| Backend (unit, integration, API, authz, authn, DB) | PASS | 227 tests, run in CI |
| Frontend (component, screen, navigation, form validation) | NEEDS REVIEW | 35 tests covering the API client, BarcodeScanner, Settings → Privacy, and register-form validation, run in CI. Coverage is real but narrow — most screens are still untested |
| Security (unauthorized access, IDOR, tokens, rate limits, uploads, injection) | NEEDS REVIEW | Covered by `tests/test_security.py`, per-feature ownership tests, `test_progress_photos.py`, and `test_security_headers.py`. No external pen-test |
| AI (injection, unsafe health questions, malformed output, tool authorization) | NEEDS REVIEW | Architectural tests in place and one live adversarial session against the real model; not a systematic red-team |

## Legal
| Item | Status | Notes |
|---|---|---|
| Privacy Policy | NEEDS REVIEW | Draft exists, needs legal review |
| Terms | NEEDS REVIEW | Draft exists, needs legal review |
| Health disclaimer | NEEDS REVIEW | Draft exists, needs legal review |
| Consent | NEEDS REVIEW | Implemented: append-only `consent_records`, nothing pre-selected, `GET/PUT /account/consents` surfaced as switches in Settings → Privacy with plain-language descriptions. Still NEEDS REVIEW because *which* consents are legally required in which jurisdiction is a legal question, not an engineering one — see `compliance-checklist.md` |
| Third-party processors | NEEDS REVIEW | Three selected, all optional and all off unless configured: OpenRouter (AI), MinIO (photos — self-hosted, so not a third party in practice), Open Food Facts (barcode lookup, barcode only). Each provider's own retention/logging policy still needs independent review — see `third-party-services.md` |
| Jurisdiction review | NEEDS REVIEW | See `compliance-checklist.md` |

This document will be updated as each item is actually implemented and verified — not marked PASS speculatively.
