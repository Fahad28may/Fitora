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
| Id guards | `src/health/sync.ts` | Colliding ids within one read are dropped rather than allowed to overwrite each other server-side; ids that change between overlap re-reads are detected and reported as a fault in Fitora. See "The one constraint" below. |

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

## Runbook: landing the native read

Everything here is executable once the prerequisites below are met. Nothing in
it has been run — no build of Fitora has ever included these modules — so
treat the package APIs as a starting point and check them against each
package's current documentation. What *is* settled is the contract: satisfy
`HealthProvider` and the rest of the app already works.

### Prerequisites (yours, not the code's)

| # | What | Why it can't be worked around |
|---|---|---|
| 1 | A decision to leave Expo Go | HealthKit and Health Connect are native modules. Expo Go ships a fixed set and cannot load them. After this, everyone developing Fitora uses a custom dev build. |
| 2 | Android: a physical device with the Health Connect app | Health Connect is a separate system app, absent from most emulator images, and grants permissions through its own UI. |
| 3 | iOS: a paid Apple Developer account (US$99/yr) and a physical iPhone | The HealthKit entitlement needs a provisioning profile, which needs a paid account. The Simulator does not serve real HealthKit data. |

Do Android first. It costs nothing beyond a handset, and it proves the shape
before the iOS money is spent.

### Step 1 — leave Expo Go

```bash
cd mobile
npx expo install expo-dev-client
```

Then build a development client instead of running in Expo Go: either EAS
Build, or local `npx expo run:android` / `npx expo run:ios` with the platform
toolchains installed. Update `mobile/README.md` in the same change — its
current instructions say to use Expo Go, and they will stop working.

### Step 2 — Android (Health Connect)

```bash
npx expo install react-native-health-connect
```

`app.json` gains the plugin and the read permissions. Four scopes, matching
exactly what §15 and the privacy policy promise — steps, distance, workouts,
active energy — and nothing else:

```jsonc
{
  "expo": {
    "plugins": [
      // ...existing plugins...
      ["react-native-health-connect"]
    ],
    "android": {
      "permissions": [
        "android.permission.health.READ_STEPS",
        "android.permission.health.READ_DISTANCE",
        "android.permission.health.READ_EXERCISE",
        "android.permission.health.READ_ACTIVE_CALORIES_BURNED"
      ]
    }
  }
}
```

**`READ_ACTIVE_CALORIES_BURNED`, not `READ_TOTAL_CALORIES_BURNED`.** An
earlier draft of this document said total. Active is the correct one: the
privacy policy tells users Fitora reads "active energy", and total additionally
includes basal metabolic burn, which Fitora neither needs nor promised to read.
Requesting total would make the policy false.

Health Connect also requires the app to answer the permissions-rationale
intent (`androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE`) — Google rejects
apps that don't handle it. Point it at a screen explaining the four scopes; the
copy already in `HealthSyncCard` was written for exactly that job and can be
reused rather than reworded.

Sketch of the provider. Check the package's current API before relying on it:

```ts
// mobile/src/health/healthConnectProvider.ts
import {
  initialize, requestPermission, getGrantedPermissions, readRecords,
} from "react-native-health-connect";

export const healthConnectProvider: HealthProvider = {
  source: "health_connect",
  name: "Health Connect",
  isAvailable: () => initialize(),
  hasPermissions: async () => (await getGrantedPermissions()).length > 0,
  requestPermissions: async () =>
    (await requestPermission([
      { accessType: "read", recordType: "Steps" },
      { accessType: "read", recordType: "Distance" },
      { accessType: "read", recordType: "ExerciseSession" },
      { accessType: "read", recordType: "ActiveCaloriesBurned" },
    ])).length > 0,
  readActivity: async (since, until) => {
    const filter = {
      timeRangeFilter: {
        operator: "between",
        startTime: since.toISOString(),
        endTime: until.toISOString(),
      },
    } as const;
    const sessions = await readRecords("ExerciseSession", filter);
    // metadata.id is Health Connect's own record id. That is the value that
    // must become external_id — see "the one constraint" below.
    return sessions.records.map(toDeviceActivityEntry);
  },
};
```

### Step 3 — iOS (HealthKit)

```bash
npx expo install react-native-health
```

`app.json` needs the entitlement and a usage string. iOS shows that string to
the user, so it has to match what the app actually does:

```jsonc
{
  "expo": {
    "ios": {
      "entitlements": { "com.apple.developer.healthkit": true },
      "infoPlist": {
        "NSHealthShareUsageDescription":
          "Fitora reads your steps, distance, workouts and active energy so your activity appears alongside what you log. It only reads — Fitora never writes anything to Health."
      }
    }
  }
}
```

Do **not** add `NSHealthUpdateUsageDescription`. Fitora does not write to
Health, `HealthProvider` has no write method, and asking for write access would
contradict both the interface and the privacy policy.

Read types: `StepCount`, `DistanceWalkingRunning`, `Workout`,
`ActiveEnergyBurned`. HealthKit samples carry a `UUID` — that is the
`external_id`.

### Step 4 — register it

One call at startup, guarded by platform:

```ts
// mobile/app/_layout.tsx, before the provider tree renders
registerHealthProvider(
  Platform.OS === "android" ? healthConnectProvider :
  Platform.OS === "ios" ? healthKitProvider :
  null
);
```

Nothing else changes. `HealthSyncCard` stops saying the build can't read a
health app and starts offering "Sync now" by itself, because it asks
`getHealthProviderStatus()` rather than assuming an answer.

### Step 5 — verify on real hardware

CI cannot do any of this. Run it by hand, on a device, and don't mark §15 done
until every line passes:

| # | Check | Passing looks like |
|---|---|---|
| 1 | Fresh install; sync before granting the in-app consent | The system permission dialog never appears. This is the §30 ordering; a unit test already covers it, so this confirms the real build agrees. |
| 2 | Grant `wearable_access`, then sync | The OS dialog appears listing four scopes and no others. |
| 3 | Deny the OS dialog | "Your device didn't grant access", and nothing is written. |
| 4 | Grant it, sync | Records appear under Home → Activity labelled "From Apple Health" / "From Health Connect", not "Typed by you". |
| 5 | **Sync twice in a row** | The second sync reports 0 new and some updated. New records again means the ids are not stable — see below. |
| 6 | Record a workout on a watch, sync, let the watch finalise it, sync again | The entry updates in place. The count does not grow. |
| 7 | Withdraw `wearable_access`, sync | Refused — and the server returns 403 regardless of what the client does. |
| 8 | Airplane mode, sync; restore network, sync | First reports a failure and promises a retry; the second lands everything, with no duplicates. |
| 9 | Delete the account | Device activity goes with it (`DELETE /account` already covers this). |

### Step 6 — fix the documents this makes wrong

Landing the native read falsifies several statements. Correct them in the same
change:

- `privacy-policy.md` §4c — drop "The data does not leave your device unaided",
  which is true only because no build can read a device.
- `third-party-services.md` — the Apple Health / Health Connect row's status.
- `production-readiness.md` — "HealthKit / Health Connect (device read)" leaves
  **Not started**; "Device record ids" can only leave NEEDS REVIEW once check 5
  above passes on hardware.
- `roadmap.md` — Phase 4's last ◐ becomes ✅.
- `mobile/README.md` — Expo Go is no longer how you run the app.

## The one constraint, and what now guards it

`external_id` must be the device's own record id. The interface cannot force
that: any implementation can return a string, and a wrong string produces
duplicated history rather than an error. Three ways to get it wrong, and where
each is caught:

| Failure | Caught by | What happens |
|---|---|---|
| Two records in one read share an id | `dedupeById` in `src/health/sync.ts` | The later one is dropped instead of silently overwriting the earlier one server-side, and the count surfaces as "N skipped as repeated". |
| A new id is minted for a record already reported | `idsLookUnstable` in `src/health/sync.ts` | The overlap re-read is checked against the ids the last sync sent. If days the last sync definitely covered come back with no familiar id at all, the user is told it is a fault in Fitora, not in their device. |
| An id that is stable but not the device's | **Nothing** | Undetectable from here — a provider hashing its own fields looks identical to a correct one until the device revises a record and the hash moves. Check 5 and 6 in Step 5 are the only defence. |

The stability check deliberately stays quiet rather than guessing: on a first
sync, when the overlap window is genuinely empty, and when the remembered id
set was truncated by its 500-entry cap. A false accusation of a broken provider
would be worse than no check. It reports rather than blocks, because the
records themselves are real and refusing to sync them would livelock a user
whose health app had simply been cleared.

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
- **The device's record id becomes `external_id`.** ◐ The one constraint the
  interface cannot enforce, though two of its three failure modes are now
  detected — see "The one constraint, and what now guards it" above.
  HealthKit's sample `UUID`, Health Connect's `metadata.id`. Do not synthesise
  one from a timestamp or a loop index: it will change when the device revises
  a record, and the server's dedup will fail open into duplicates.
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
