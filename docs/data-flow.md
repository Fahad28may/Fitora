# Data Flow & Privacy by Design

## Principle

For every piece of personal data collected: **why do we need this?** If there's no strong product requirement, Fitora doesn't collect it.

## Data inventory

| Data type | Purpose | Storage | Retention | Access | Third-party sharing |
|---|---|---|---|---|---|
| Email + password hash | Authentication | PostgreSQL | Until account deletion | Backend only | None |
| Profile (age, height, sex, activity level) | BMR/TDEE calculation | PostgreSQL | Until account deletion or user edit/delete | Backend, deterministic calc service | None |
| Food diary entries | Core nutrition tracking | PostgreSQL | Until account deletion or user delete | Backend | Food-DB provider receives only the search query, not the diary entry |
| Natural-language food text ("I ate two eggs...") | Parsing into structured items | Sent transiently to AI provider for parsing, structured result stored in PostgreSQL | Raw text not retained beyond the parse request unless the user also saves it as a note | Backend, AI provider (transient) | AI provider — see `ai-safety.md` |
| Food photos (optional) | Photo-based food recognition | Object storage, private bucket, encrypted at rest | Deleted after processing unless user opts to keep it; defined max retention if kept | Backend + vision provider (transient) | Vision AI provider — image only, no user identity metadata |
| Progress photos (optional) | User-tracked visual progress | Object storage, private bucket, encrypted at rest | Until user deletes or account deletion | Backend only, never AI providers | None |
| Weight / measurements | Progress tracking | PostgreSQL | Until account deletion or user delete | Backend | None |
| Workout data | Workout tracking | PostgreSQL | Until account deletion or user delete | Backend | None |
| AI conversation history | AI coach context | PostgreSQL | Until account deletion or user delete; see retention note in `privacy-policy.md` | Backend, AI provider (per-message, minimum necessary) | AI provider |
| Consent records | Legal/audit requirement | PostgreSQL, append-only | Retained per legal requirement even after account deletion (anonymized) | Backend | None |
| Refresh token hashes | Session management | PostgreSQL | Until expiry/revocation | Backend | None |
| Hashed IP / user agent (sessions) | Fraud/abuse detection | PostgreSQL | Rolling window, short retention | Backend | None |

## Standing rules

- The AI layer never receives: email, full name, password, auth tokens, payment information. See `ai-safety.md` for exactly what each AI call does receive.
- Analytics (if/when added) never receive raw health data (weights, food logs, workout details) without a specific, documented, lawful reason — see §34 of the master prompt.
- Images are processed for their required signal (food recognition, progress comparison) and not retained by default; if retained, they are encrypted and user-deletable.

## Account deletion flow

```text
Settings → Privacy → Delete Account → Confirmation → Deletion workflow
```

On confirmed deletion:

1. Mark `users.status = pending_deletion` immediately; block login.
2. Hard-delete or anonymize (per table below) within the documented deletion window.
3. Cascade-delete: profile, goals, food diary, meals, workouts, weight/measurements, water, activity, progress photos (including object storage), AI conversations, sessions.
4. Anonymize rather than delete where legally required for audit (e.g. `audit_events`, `consent_records`) — user identifier replaced with a non-reversible reference.
5. Backups: not immediately purged (see below) — this gap is disclosed in the privacy policy.

## Backup retention

Backups follow the hosting/backup provider's retention window (documented once a provider is chosen in `third-party-services.md`). Data deleted from the primary database will persist in backups until they age out or are rotated. This is disclosed to users rather than silently omitted.

## Data export

`Settings → Privacy → Export My Data` produces a machine-readable (JSON) export of: profile, goals, food diary, meals, workouts, weight/measurements, water, activity, progress-photo references (with signed download links, not embedded binaries), AI conversation history. Export is generated on request and delivered via a time-limited signed link, not email attachment.
