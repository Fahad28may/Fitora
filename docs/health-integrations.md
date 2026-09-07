# Health & Wearable Integrations

Status of §15 / Phase 4: **server side built and tested; device side not
started, and blocked on decisions and accounts only the project owner can
provide.**

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

## Why the device side isn't built

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
not writing it. The server side is built because it *can* be tested; the device
side stops here.

## What is needed to proceed

Roughly in order:

1. **A decision to leave Expo Go.** Everything after this depends on it.
   Development moves to custom dev builds, which are slower to iterate on.
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

These are settled by what already exists, not open questions:

- **Read-only.** Fitora reads activity from the device. It does not write back.
  Request read scopes only, and say so in the permission strings.
- **Minimum scopes.** §15: ask for the minimum permission the feature needs,
  and explain why *before* requesting it. Steps, distance, workouts and active
  energy. Not sleep, not heart rate, not clinical records — none of which
  Fitora uses.
- **The device's record id becomes `external_id`.** HealthKit's `UUID`,
  Health Connect's record id. Do not synthesise one from a timestamp: it will
  change when the device revises a record, and the dedup will fail open into
  duplicates.
- **Two consents, not one.** The OS permission is the device agreeing to hand
  data over. `wearable_access` is the user agreeing Fitora may store it. Ask
  for the app-level one first — being sent to a system permission dialog before
  anyone has explained why is exactly the pattern §30 calls deceptive.
- **Sync windows, not full history.** Page through with the 500-entry cap.
- **Offline.** The existing outbox (`mobile/src/api/outbox.ts`) already handles
  queue-and-retry; a sync that fails on the network should use it rather than
  inventing a second mechanism.

## Privacy

When this ships, `privacy-policy.md`, `data-flow.md` and
`third-party-services.md` all need updating in the same change — device health
data is a new category, and the policy currently does not mention it because
none is collected. Do not ship the integration and the policy update separately.
