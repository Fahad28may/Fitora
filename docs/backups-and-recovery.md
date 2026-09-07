# Backups and Disaster Recovery

> **Draft — this is a design, not a running system.** Nothing in this document
> is implemented. It exists so that whoever provisions Fitora's infrastructure
> has a specification to build against, and so the gap is visible rather than
> assumed away. See §60 of the build spec: *a backup is not considered reliable
> until restoration has actually been tested.*

## Status

| Item | Status |
|---|---|
| Automated database backups | **Not implemented** |
| Encrypted backups | **Not implemented** |
| Retention policy | Defined below, not enforced |
| Restoration testing | **Never performed** |
| Disaster recovery runbook | Drafted below, never rehearsed |

Do not describe Fitora as having backups until the table above says otherwise.
The privacy policy already discloses that deleted data persists in backups for
a retention window; that disclosure becomes accurate only once backups exist.

## What has to be backed up

| Asset | Contains | Loss impact |
|---|---|---|
| PostgreSQL database | Everything: accounts, health data, food and workout logs, consent records, audit trail | Total. This is the product. |
| Object storage bucket (progress photos) | User-uploaded images | High, and unrecoverable — these are personal photos with no other copy |
| Secrets (JWT key, DB credentials, API keys) | — | Not backed up with the data. See "Secrets" below. |

Application code lives in git and needs no separate backup. Redis holds only
cache and rate-limit state and is deliberately not backed up — losing it costs
a cold cache, nothing more.

## Database backups

**Method.** Managed provider snapshots (daily, retained per the table below)
plus continuous WAL archiving for point-in-time recovery. WAL archiving is what
makes "restore to 10 minutes before the bad migration" possible; daily snapshots
alone give a worst case of 24 hours of lost data.

**Encryption.** At rest with a provider-managed key, and in transit to the
backup destination. The backup destination must be a different failure domain
from the primary database — a snapshot sitting in the same account and region as
the thing it protects covers hardware failure and nothing else.

**Access.** Backup restore rights are separate from application credentials. The
application's database user must not be able to read, delete, or overwrite
backups; a compromised application credential should not be able to destroy the
recovery path.

## Object storage backups

Versioning enabled on the bucket, with a deletion protection window. Note the
tension with §29: a user deleting their account expects their photos gone.
Object versions must therefore expire on a **shorter** window than the database
backup retention, and that window is disclosed in the privacy policy. Deletion
is not complete until the last version expires — say so, rather than claiming
immediate erasure.

## Retention

| Backup | Retention |
|---|---|
| Hourly WAL segments | 7 days (point-in-time recovery window) |
| Daily snapshots | 30 days |
| Monthly snapshots | 6 months |
| Object versions | 30 days |

Retention is a privacy commitment as much as an operational one: it is the
upper bound on how long deleted user data survives. Lengthening it requires
updating `privacy-policy.md` and `data-flow.md` in the same change.

## Recovery objectives

| Objective | Target |
|---|---|
| RPO (max acceptable data loss) | 15 minutes, via WAL archiving |
| RTO (max acceptable downtime) | 4 hours |

These are targets, not measurements. They are unproven until a restoration
drill has actually met them.

## Restoration drill

Required before launch, and quarterly after. A backup nobody has restored is a
belief, not a backup.

1. Provision a scratch database, isolated from production.
2. Restore the most recent snapshot, then replay WAL to a chosen timestamp.
3. Run `alembic current` and confirm the schema revision matches what the
   application expects.
4. Spot-check integrity: a known user's food diary, weight history, workout
   sessions, consent records, and audit events are all present and consistent.
5. Restore a progress-photo object version and confirm it opens.
6. Point a staging application at the restored database and exercise login,
   logging a food, and reading the dashboard.
7. Record the wall-clock time taken and compare against the RTO above.
8. Destroy the scratch environment — it holds real personal data and is subject
   to exactly the same protections as production.

**Log the outcome in this document.** A drill nobody wrote down did not happen.

### Drill log

| Date | Restored to | Time taken | Outcome | Notes |
|---|---|---|---|---|
| — | — | — | — | No drill has been performed |

## Secrets

Secrets are **not** in the database backup and cannot be recovered from it.
Losing `JWT_SECRET_KEY` invalidates every session (recoverable — users log in
again). Losing the database credentials or object-storage keys without a copy in
the secret manager means the restored data is unreachable.

Whatever secret manager is chosen must have its own documented recovery path,
and it must be verified during the drill — restoring a database you cannot
authenticate to is not a recovery.

## Failure scenarios

| Scenario | Response |
|---|---|
| Accidental destructive migration | Point-in-time restore to just before it. This is the case WAL archiving exists for. |
| Database host loss | Restore latest snapshot + WAL to a new host. |
| Region outage | Restore from the cross-region backup copy. Untested; RTO likely exceeded. |
| Ransomware / credential compromise | Restore from a backup predating the compromise. Depends entirely on backup credentials being separate from application credentials — see "Access" above. |
| Object storage bucket deleted | Restore from versioning if within the window; otherwise **photos are unrecoverable**. Users should be told this plainly rather than reassured. |

## Before this document can be trusted

- [ ] Hosting and database provider selected (`third-party-services.md`)
- [ ] Automated snapshots and WAL archiving configured
- [ ] Backup destination in a separate failure domain
- [ ] Backup credentials separated from application credentials
- [ ] Object versioning enabled with an expiry shorter than DB retention
- [ ] One restoration drill completed and logged above
- [ ] `production-readiness.md` Backups row updated to reflect reality
