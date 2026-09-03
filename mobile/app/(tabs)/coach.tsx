import { ScrollView, Text } from "react-native";

import { screenStyles } from "./styles";

export default function CoachScreen(): React.JSX.Element {
  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Coach</Text>
      <Text style={screenStyles.body}>
        The AI fitness coach lands here in Phase 3, built on structured application data with
        strict tool authorization and output validation. See docs/ai-safety.md.
      </Text>
    </ScrollView>
  );
}
