import { ScrollView, Text } from "react-native";

import { screenStyles } from "./styles";

export default function NutritionScreen(): React.JSX.Element {
  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Nutrition</Text>
      <Text style={screenStyles.body}>
        Food search, manual logging, custom foods/meals, and natural-language logging land here
        in Phase 1–3. See docs/roadmap.md.
      </Text>
    </ScrollView>
  );
}
