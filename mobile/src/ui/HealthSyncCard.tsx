import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Platform, Text, TouchableOpacity, View } from "react-native";

import { getHealthProviderStatus, type HealthProviderStatus } from "../health/provider";
import { healthSync, type HealthSyncOutcome } from "../health/sync";
import { formStyles as s } from "./formStyles";

/**
 * Why no device can be connected, said plainly.
 *
 * `no_native_module` is this build's real state. Saying "coming soon" or
 * showing a Connect button that silently does nothing would be a claim the
 * app can't honour — §66's bar is a real app, and a real app doesn't offer
 * switches that aren't wired to anything.
 */
const UNAVAILABLE_COPY: Record<string, string> = {
  unsupported_platform:
    "Reading activity from a device works on iOS and Android only. Nothing is read here.",
  no_native_module:
    "This build of Fitora can't read Apple Health or Health Connect — doing so needs a version of the app built with those components included. You can still log activity by hand, and everything else works normally.",
  not_installed:
    "Health Connect isn't installed on this device. Install it from the Play Store to sync activity automatically.",
};

function outcomeMessage(outcome: HealthSyncOutcome): string {
  switch (outcome.kind) {
    case "consent_required":
      return 'Turn on "Read data from wearables" above first — that\'s you allowing Fitora to store it.';
    case "permission_denied":
      return "Your device didn't grant access to activity data, so nothing was read.";
    case "failed":
      return outcome.partial
        ? `${outcome.message} Some activity was saved; the rest will retry.`
        : outcome.message;
    case "synced": {
      if (outcome.read === 0) return "Nothing new to sync.";
      const parts = [`${outcome.created} new`, `${outcome.updated} updated`];
      if (outcome.dropped > 0) {
        // Not hidden: a device that reports impossible records is a fact the
        // user is entitled to see, not something to quietly swallow.
        parts.push(`${outcome.dropped} skipped as out of range`);
      }
      if (outcome.duplicateIds > 0) {
        parts.push(`${outcome.duplicateIds} skipped as repeated`);
      }
      const summary = `Synced — ${parts.join(", ")}.`;
      // The one contract the provider interface can't enforce. Said in full
      // rather than as a count, because it means the history is being
      // duplicated and the cause is a bug in the app, not in the user's
      // device or their data.
      return outcome.unstableIds
        ? `${summary} Your health app is reporting the same activities under new ids each time, which duplicates them here. This is a fault in Fitora — please report it, and turn the sync off until it's fixed.`
        : summary;
    }
  }
}

export function HealthSyncCard({
  hasWearableConsent,
}: {
  hasWearableConsent: boolean;
}): React.JSX.Element {
  const [status, setStatus] = useState<HealthProviderStatus | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const resolved = await getHealthProviderStatus(Platform.OS);
    setStatus(resolved);
    if (resolved.kind === "available") {
      setLastSyncedAt(await healthSync.lastSyncedAt(resolved.provider.source));
    }
  }, []);

  useEffect(() => {
    // Resolution is async; setState lands after it settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function handleSync(): Promise<void> {
    if (status?.kind !== "available") return;
    setIsSyncing(true);
    setMessage(null);
    try {
      const outcome = await healthSync.run({
        provider: status.provider,
        hasWearableConsent,
      });
      setMessage(outcomeMessage(outcome));
      setLastSyncedAt(await healthSync.lastSyncedAt(status.provider.source));
    } finally {
      setIsSyncing(false);
    }
  }

  return (
    <View style={[s.card, { gap: 10, marginTop: 16 }]}>
      <Text style={{ fontSize: 16, fontWeight: "700" }}>Activity from your device</Text>

      {status === null ? (
        <ActivityIndicator />
      ) : status.kind === "unavailable" ? (
        <Text style={s.helpText}>{UNAVAILABLE_COPY[status.reason]}</Text>
      ) : (
        <>
          <Text style={s.helpText}>
            Fitora reads steps, distance, workouts and active energy from {status.provider.name}.
            It only reads — nothing is ever written back to your health app.
          </Text>
          <Text style={s.helpText}>
            {lastSyncedAt === null
              ? "Not synced yet."
              : `Last synced ${lastSyncedAt.toLocaleString()}.`}
          </Text>
          <TouchableOpacity
            style={[s.button, { marginTop: 0 }, isSyncing && s.buttonDisabled]}
            disabled={isSyncing}
            onPress={() => void handleSync()}
            accessibilityRole="button"
            accessibilityLabel={`Sync activity from ${status.provider.name}`}
          >
            {isSyncing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={s.buttonText}>Sync now</Text>
            )}
          </TouchableOpacity>
        </>
      )}

      {message ? <Text style={s.helpText}>{message}</Text> : null}
    </View>
  );
}
