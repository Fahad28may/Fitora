import { ScrollView, Text } from "react-native";

import { screenStyles } from "./styles";

export default function ProgressScreen(): React.JSX.Element {
  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Progress</Text>
      <Text style={screenStyles.body}>
        Weight, measurements, progress photos, and charts land here in Phase 1–2. See
        docs/roadmap.md.
      </Text>
    </ScrollView>
  );
}
