import { File, Paths } from "expo-file-system";
import { router } from "expo-router";
import * as Sharing from "expo-sharing";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { DELETE_CONFIRMATION_PHRASE, accountApi } from "../src/api/account";
import { ApiError } from "../src/api/client";
import type { ConsentState, ConsentType } from "../src/api/types";
import { useAuth } from "../src/auth/AuthContext";
import { formStyles as s } from "../src/ui/formStyles";
import { screenStyles } from "./(tabs)/styles";

/**
 * Plain-language description of each consent, shown next to its switch.
 * §30 requires consent to be understandable, so these say what actually
 * happens rather than naming a legal basis.
 */
const CONSENT_COPY: Record<ConsentType, { label: string; description: string }> = {
  health_data: {
    label: "Store my health data",
    description:
      "Weight, measurements, food and workout logs. Fitora can't do anything useful without this.",
  },
  ai_processing: {
    label: "Use AI features",
    description:
      "Sends your message and a small slice of your own app data to the AI provider when you use the coach or describe a meal. Never your email, name, or password.",
  },
  wearable_access: {
    label: "Read data from wearables",
    description: "Not built yet — no data is read from any device today.",
  },
  analytics: {
    label: "Optional product analytics",
    description: "Not built yet — Fitora collects no analytics today.",
  },
};

const CONSENT_ORDER: ConsentType[] = [
  "health_data",
  "ai_processing",
  "wearable_access",
  "analytics",
];

export default function SettingsScreen(): React.JSX.Element {
  const { user, logout } = useAuth();

  const [consentState, setConsentState] = useState<ConsentState | null>(null);
  const [consentError, setConsentError] = useState<string | null>(null);
  const [savingConsent, setSavingConsent] = useState<ConsentType | null>(null);

  const [isExporting, setIsExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const [showDeleteForm, setShowDeleteForm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadConsents = useCallback(async () => {
    try {
      setConsentState(await accountApi.getConsents());
    } catch (err) {
      setConsentError(err instanceof ApiError ? err.message : "Could not load your choices.");
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadConsents();
  }, [loadConsents]);

  async function handleToggleConsent(type: ConsentType, granted: boolean): Promise<void> {
    setConsentError(null);
    setSavingConsent(type);
    // Optimistic, but reverted below if the write fails — a consent switch
    // that silently lies about what was recorded would be worse than a spinner.
    setConsentState((prev) =>
      prev ? { ...prev, consents: { ...prev.consents, [type]: granted } } : prev
    );
    try {
      await accountApi.setConsent(type, granted);
    } catch (err) {
      setConsentState((prev) =>
        prev ? { ...prev, consents: { ...prev.consents, [type]: !granted } } : prev
      );
      setConsentError(err instanceof ApiError ? err.message : "Could not save that choice.");
    } finally {
      setSavingConsent(null);
    }
  }

  async function handleExport(): Promise<void> {
    setExportError(null);
    setExportMessage(null);
    setIsExporting(true);
    try {
      const data = await accountApi.export();
      const json = JSON.stringify(data, null, 2);

      if (Platform.OS === "web") {
        // No file/share sheet on web; the data is still retrievable directly
        // from the API, so say so rather than pretending it worked.
        setExportMessage(
          "Export is ready, but saving a file isn't supported in the browser build. Open Fitora on your phone to save it."
        );
        return;
      }

      const file = new File(Paths.cache, "fitora-export.json");
      if (file.exists) file.delete();
      file.create();
      file.write(json);

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(file.uri, {
          mimeType: "application/json",
          dialogTitle: "Save your Fitora data",
        });
        setExportMessage("Export saved.");
      } else {
        setExportMessage(`Export written to ${file.uri}`);
      }
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Could not export your data.");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleDelete(): Promise<void> {
    setDeleteError(null);
    setIsDeleting(true);
    try {
      await accountApi.deleteAccount(deletePassword, deleteConfirmation);
      // The account is gone, so there is nothing left to log out of on the
      // server — clear local tokens and get out of the authenticated tree.
      await logout();
      router.replace("/(auth)/login");
    } catch (err) {
      setDeleteError(
        err instanceof ApiError ? err.message : "Could not delete your account."
      );
    } finally {
      setIsDeleting(false);
    }
  }

  function confirmDelete(): void {
    Alert.alert(
      "Delete your account?",
      "This permanently deletes your account and everything in it — food logs, workouts, weight history, photos. It cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        { text: "Delete forever", style: "destructive", onPress: () => void handleDelete() },
      ]
    );
  }

  const canDelete =
    deletePassword.length > 0 && deleteConfirmation === DELETE_CONFIRMATION_PHRASE;

  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Settings</Text>
      <Text style={s.helpText}>Signed in as {user?.email}</Text>

      <Text style={[screenStyles.cardTitle, { marginTop: 24 }]}>Privacy</Text>

      {/* --- consent --- */}
      <View style={[s.card, { gap: 14, marginTop: 8 }]}>
        <Text style={screenStyles.cardTitle}>Your choices</Text>
        {consentState === null ? (
          <ActivityIndicator />
        ) : (
          <>
            {CONSENT_ORDER.map((type) => (
              <View key={type} style={{ gap: 4 }}>
                <View style={s.row}>
                  <Text style={[screenStyles.body, { flex: 1, paddingRight: 12 }]}>
                    {CONSENT_COPY[type].label}
                  </Text>
                  <Switch
                    value={consentState.consents[type]}
                    disabled={savingConsent === type}
                    onValueChange={(v) => void handleToggleConsent(type, v)}
                    accessibilityLabel={CONSENT_COPY[type].label}
                  />
                </View>
                <Text style={s.helpText}>{CONSENT_COPY[type].description}</Text>
              </View>
            ))}
            <Text style={s.helpText}>Policy version {consentState.policy_version}</Text>
          </>
        )}
        {consentError ? <Text style={s.error}>{consentError}</Text> : null}
      </View>

      {/* --- export --- */}
      <View style={[s.card, { gap: 10, marginTop: 16 }]}>
        <Text style={screenStyles.cardTitle}>Export my data</Text>
        <Text style={s.helpText}>
          Downloads everything Fitora holds about you as a JSON file. Progress photos are
          listed but not included — save those from the Progress screen first.
        </Text>
        <TouchableOpacity
          style={[s.button, { marginTop: 0 }]}
          onPress={() => void handleExport()}
          accessibilityRole="button"
          accessibilityLabel="Export my data"
        >
          {isExporting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={s.buttonText}>Export my data</Text>
          )}
        </TouchableOpacity>
        {exportMessage ? <Text style={s.helpText}>{exportMessage}</Text> : null}
        {exportError ? <Text style={s.error}>{exportError}</Text> : null}
      </View>

      {/* --- deletion --- */}
      <View style={[s.card, { gap: 10, marginTop: 16 }]}>
        <Text style={screenStyles.cardTitle}>Delete my account</Text>
        <Text style={s.helpText}>
          Permanently deletes your account and everything in it. This cannot be undone, so
          export your data first if you want to keep it.
        </Text>

        {showDeleteForm ? (
          <>
            <TextInput
              style={s.input}
              placeholder="Your password"
              secureTextEntry
              autoCapitalize="none"
              value={deletePassword}
              onChangeText={setDeletePassword}
              accessibilityLabel="Your password"
            />
            <TextInput
              style={s.input}
              placeholder={`Type ${DELETE_CONFIRMATION_PHRASE}`}
              autoCapitalize="characters"
              autoCorrect={false}
              value={deleteConfirmation}
              onChangeText={setDeleteConfirmation}
              accessibilityLabel={`Type ${DELETE_CONFIRMATION_PHRASE} to confirm`}
            />
            <TouchableOpacity
              style={[
                s.button,
                { marginTop: 0, backgroundColor: canDelete ? "#dc2626" : "#fca5a5" },
              ]}
              disabled={!canDelete || isDeleting}
              onPress={confirmDelete}
              accessibilityRole="button"
              accessibilityLabel="Delete my account permanently"
            >
              {isDeleting ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={s.buttonText}>Delete my account permanently</Text>
              )}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setShowDeleteForm(false)}>
              <Text style={s.secondaryButtonText}>Cancel</Text>
            </TouchableOpacity>
          </>
        ) : (
          <TouchableOpacity
            onPress={() => setShowDeleteForm(true)}
            accessibilityRole="button"
            // Distinct from the "Delete my account permanently" button this
            // reveals; two controls reading identically is a screen-reader
            // trap, not just an ambiguous test query.
            accessibilityLabel="Start deleting my account"
          >
            <Text style={[s.secondaryButtonText, { color: "#dc2626" }]}>
              Delete my account
            </Text>
          </TouchableOpacity>
        )}
        {deleteError ? <Text style={s.error}>{deleteError}</Text> : null}
      </View>

      <TouchableOpacity
        style={{ marginTop: 24 }}
        onPress={() => router.back()}
        accessibilityRole="button"
      >
        <Text style={s.secondaryButtonText}>Back</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
