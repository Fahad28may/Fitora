import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { aiApi, type CoachMessageOut } from "../../src/api/ai";
import { ApiError } from "../../src/api/client";
import { formStyles as s } from "../../src/ui/formStyles";
import { screenStyles } from "./styles";

export default function CoachScreen(): React.JSX.Element {
  const [messages, setMessages] = useState<CoachMessageOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDisabled, setIsDisabled] = useState(false);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<FlatList<CoachMessageOut>>(null);

  const load = useCallback(async () => {
    try {
      setMessages(await aiApi.listCoachMessages());
      setIsDisabled(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setIsDisabled(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not load the coach.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: setState happens after the awaited API call resolves.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function handleSend(): Promise<void> {
    if (!input.trim()) return;
    const text = input.trim();
    setInput("");
    setError(null);
    setIsSending(true);
    try {
      await aiApi.sendCoachMessage(text);
      await load();
      requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setIsDisabled(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not send that message.");
      }
    } finally {
      setIsSending(false);
    }
  }

  async function handleClear(): Promise<void> {
    await aiApi.clearCoachMessages();
    setMessages([]);
  }

  if (isLoading) {
    return (
      <View style={[screenStyles.container, { flex: 1, justifyContent: "center" }]}>
        <ActivityIndicator />
      </View>
    );
  }

  if (isDisabled) {
    return (
      <View style={screenStyles.container}>
        <Text style={screenStyles.title}>Coach</Text>
        <View style={screenStyles.card}>
          <Text style={screenStyles.body}>
            The AI coach isn&apos;t configured on this server yet — it needs an AI_API_KEY. Core
            features (nutrition, workouts, progress) work normally without it.
          </Text>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <FlatList
        ref={listRef}
        style={{ flex: 1 }}
        contentContainerStyle={[screenStyles.container, { flexGrow: 1 }]}
        data={messages}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View style={{ gap: 8, marginBottom: 12 }}>
            <Text style={screenStyles.title}>Coach</Text>
            <View style={screenStyles.disclaimerBox}>
              <Text style={screenStyles.disclaimerText}>
                Fitora&apos;s AI coach provides general fitness and nutrition information — not
                medical advice. For medical questions, consult a qualified healthcare
                professional.
              </Text>
            </View>
            {messages.length === 0 ? (
              <Text style={screenStyles.body}>
                Ask about your progress, nutrition, or workouts — e.g. &quot;How did I do this
                week?&quot;
              </Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) => (
          <View
            style={[
              screenStyles.card,
              {
                marginBottom: 10,
                backgroundColor: item.role === "user" ? "#111827" : undefined,
              },
            ]}
          >
            <Text
              style={[
                screenStyles.body,
                item.role === "user" ? { color: "#fff" } : null,
              ]}
            >
              {item.content}
            </Text>
          </View>
        )}
        ListFooterComponent={
          messages.length > 0 ? (
            <TouchableOpacity
              onPress={() => void handleClear()}
              accessibilityRole="button"
              accessibilityLabel="Clear the whole coach conversation"
            >
              <Text style={[s.error, { fontSize: 13, marginTop: 4 }]}>Clear conversation</Text>
            </TouchableOpacity>
          ) : null
        }
      />

      {error ? (
        <Text style={[s.error, { paddingHorizontal: 24 }]}>{error}</Text>
      ) : null}

      <View style={{ flexDirection: "row", gap: 10, padding: 24, paddingTop: 8 }}>
        <TextInput
          style={[s.input, { flex: 1 }]}
          placeholder="Ask the coach..."
          accessibilityLabel="Message to the coach"
          value={input}
          onChangeText={setInput}
          onSubmitEditing={() => void handleSend()}
        />
        <TouchableOpacity
          style={[s.button, { marginTop: 0 }, (!input.trim() || isSending) && s.buttonDisabled]}
          onPress={() => void handleSend()}
          disabled={!input.trim() || isSending}
          accessibilityRole="button"
          accessibilityLabel="Send message to the coach"
        >
          {isSending ? <ActivityIndicator color="#fff" /> : <Text style={s.buttonText}>Send</Text>}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
