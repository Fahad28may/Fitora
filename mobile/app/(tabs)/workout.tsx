import { ScrollView, Text } from "react-native";

import { screenStyles } from "./styles";

export default function WorkoutScreen(): React.JSX.Element {
  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>Workout</Text>
      <Text style={screenStyles.body}>
        Exercise library, routines, and workout tracking land here in Phase 2. See
        docs/roadmap.md.
      </Text>
    </ScrollView>
  );
}
