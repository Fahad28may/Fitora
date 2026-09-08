# Health & Wearable Integrations

Status of §15 / Phase 4: **server side and the whole client side above the
native bridge are built and tested. The native read itself is not, and is
blocked on decisions and accounts only the project owner can provide.**

## What works today

`POST /api/v1/activity-entries/sync` accepts activity reported by a health app
or wearable. It is real, tested (`backend/tests/test_activity_sync.py`), and
ready for a client to call.

| Property | Behaviour |
|---|---|
| Consent | Requires the user's `wearable_access` consent (Settings → Privacy). Returns 403 with a message pointing there. Withdrawing consent stops future syncs immediately. |
| Idempotency | Matched on `(user_id, source, external_id)`. A health app re-reports the same workout on every sync, so entries are updated in place, never appended. Re-syncing a window is a no-op. |
| Revisions | An existing record is refreshed, not skipped — devices finalise a workout's distance after processing. |
| Provenance | Writes only `apple_health` / `health_connect` / `wearable`. A sync cannot write `manual`, and the manual endpoint cannot write a device source. |
| Validation | Identical bounds to manual entry. Device data is not more trustworthy than typed data; a health app reporting a 40-hour run is a bug somewhere and is rejected at the boundary. |
| Batch size | 500 entries per request. A device that has been offline for weeks pages through. |

Request shape:

```jsonc
POST /api/v1/activity-entries/sync
{
  "source": "apple_health",           // or health_connect | wearable
  "entries": [
    {
      "external_id": "HKWorkout-1234", // the device's own id — required
      "logged_at": "2026-09-07",
      "activity_type": "running",
      "duration_min": 32,
      "distance_km": 5.4,
      "steps": 6100,
      "calories_burned": 340
    }
  ]
}
```

## What the app does

Everything between "the device handed us records" and "the server stored them"
is built and tested (`mobile/src/health/`, `mobile/src/api/activity.ts`):

| Piece | Where | Behaviour |
|---|---|---|
| Manual activity logging | `app/log-activity.tsx` | Type, minutes, and optional distance/steps/calories. Reached from the Activity card on Home. Goes through the outbox, so a tap on a flaky connection can't log twice. Each entry shows whether it was typed or device-reported. |
| Provider seam | `src/health/provider.ts` | The `HealthProvider` interface, plus a registry. A build with native modules calls `registerHealthProvider()` once at startup; nothing else changes. Read-only by construction — the interface has no write method. |
| Sync orchestration | `src/health/sync.ts` | Consent check, then OS permission, then a windowed read, then paging at the server's 500-entry cap. |
| Client-side bounds | `src/api/activity.ts` | Mirrors the server's limits so one impossible record is dropped instead of 422-ing the batch it arrived in. The count of dropped records is shown, not swallowed. |
| Honest unavailability | `src/ui/HealthSyncCard.tsx` | In a build with no native module, Settings says exactly that. There is no Connect button that does nothing. |

Two decisions worth knowing about:

**The sync window is a watermark plus an overlap.** The first sync reaches back
30 days, not a lifetime — importing years of HealthKit history is slow, and the
charts only look back 90 days. Later syncs re-read one day before the last
successful sync, because devices finalise a workout's distance and calorie
figures after the fact and a phone backfills when it next meets its watch.
Re-reading is free of consequence: the server matches on `external_id`.

**A failed sync retries by not advancing the watermark, not through the
outbox.** The design constraint below originally said to reuse the outbox. That
turned out to be the wrong mechanism: the outbox exists for data that lives
only in a tap and would otherwise be lost, whereas health records are still on
the device tomorrow. Not moving the bookmark re-reads the same window on the
next attempt, costs no storage, and avoids running a second dedup scheme beside
the `external_id` one the server already has.

## Why the native read isn't built

Reading HealthKit or Health Connect needs native code. That is not a matter of
writing more TypeScript — it changes what the app *is*:

**Expo Go stops working.** Fitora currently runs in Expo Go, which ships a
fixed set of native modules. HealthKit and Health Connect are not among them,
and cannot be. Adding either means moving to a custom development build (EAS
Build or a local native build) for all future development, by everyone.

**iOS needs a paid Apple Developer account.** HealthKit requires the HealthKit
entitlement, which requires a provisioning profile, which requires a paid
account (US$99/year). There is no test path around this: HealthKit does not
work in the iOS Simulator for real data, so it needs a paid account *and* a
physical device.

**Android needs the Health Connect app and a physical device.** Health Connect
is a separate system app. It is not present on most emulator images, and
permissions are granted through its own UI.

**Neither can be verified in CI.** The Metro export smoke test would still
pass — native modules don't break JS bundling — but that would prove nothing
about whether reading a step count works. Any claim that the integration works
would be untested.

Writing an unverifiable integration and calling it done would be worse than
not writing it. Everything above that boundary is built because it *can* be
tested — with a fake provider, in CI, today. The native read stops here.

## What is needed to proceed

Roughly in order:

1. **A decision to leave Expo Go.** Everything after this depends on it.
   Development moves to custom dev builds, which are slower to iterate on.
   Nothing else in the app has to change for this: the work is one file
   implementing `HealthProvider` and one `registerHealthProvider()` call.
2. **Android first** — it is the cheaper path to a working integration.
   - `react-native-health-connect` (community package)
   - A physical Android device with the Health Connect app installed
   - `READ_STEPS`, `READ_DISTANCE`, `READ_EXERCISE`, `READ_TOTAL_CALORIES_BURNED`
     declared and requested at runtime
3. **iOS**, once Android proves the shape:
   - A paid Apple Developer account, and the HealthKit entitlement on the
     provisioning profile
   - `react-native-health` (community package)
   - A physical iPhone; the Simulator is not sufficient
   - `NSHealthShareUsageDescription` in the Info.plist, worded to say Fitora
     reads activity and never writes back
4. **A build pipeline** — EAS Build, or local Xcode/Gradle builds.

## Design constraints for whoever builds it

These are settled by what already exists, not open questions. The ones marked
✅ are already enforced in code above the seam, so an implementation gets them
by satisfying the interface:

- **Read-only.** ✅ The `HealthProvider` interface has no write method, so an
  implementation cannot add one without changing the contract. Request read
  scopes only, and say so in the permission strings.
- **Minimum scopes.** §15: ask for the minimum permission the feature needs,
  and explain why *before* requesting it. Steps, distance, workouts and active
  energy. Not sleep, not heart rate, not clinical records — none of which
  Fitora uses.
- **The device's record id becomes `external_id`.** Not enforceable above the
  seam — this is the one constraint an implementation can still get wrong, and
  getting it wrong produces duplicates rather than an error. HealthKit's `UUID`,
  Health Connect's record id. Do not synthesise one from a timestamp: it will
  change when the device revises a record, and the dedup will fail open into
  duplicates.
- **Two consents, not one.** ✅ Enforced and tested in `src/health/sync.ts`:
  without `wearable_access` the OS is never asked. The OS permission is the
  device agreeing to hand data over. `wearable_access` is the user agreeing Fitora may store it. Ask
  for the app-level one first — being sent to a system permission dialog before
  anyone has explained why is exactly the pattern §30 calls deceptive.
- **Sync windows, not full history.** ✅ Paging at the 500-entry cap and the
  watermark/overlap logic live in `src/health/sync.ts`.
- **Offline.** ✅ Handled, but *not* via the outbox — see the reasoning above.
  A failed sync leaves the watermark unmoved and re-reads next time.

## Privacy

Done, in the same change as the client layer: `privacy-policy.md` §4c covers
device activity, `data-flow.md` carries both device-reported entries and the
on-device sync watermark in the inventory, and `third-party-services.md`
records that a health app is a data *source* and not a processor.

The user-facing consent copy moved with it. It previously read "Not built yet
— no data is read from any device today"; it now explains the two-agreement
model, because the switch is now connected to something real even though no
shipped build can read a device yet.

Update all of these again when the native read lands — at that point Fitora
really does read from a health app, and the phrase "your build may not support
it" stops being true.
