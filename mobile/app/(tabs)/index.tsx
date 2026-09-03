import { Pressable, ScrollView, Text, View } from "react-native";

import { useAuth } from "../../src/auth/AuthContext";
import { screenStyles } from "./styles";

export default function HomeScreen(): React.JSX.Element {
  const { user, logout } = useAuth();

  return (
    <ScrollView contentContainerStyle={screenStyles.container}>
      <Text style={screenStyles.title}>How am I doing today?</Text>
      <Text style={screenStyles.body}>
        Signed in as {user?.email}. The daily dashboard (calories, macros, water, steps, today&apos;s
        workout, weight, AI recommendations) lands here once nutrition and workout logging are
        built — see docs/roadmap.md.
      </Text>

      <View style={screenStyles.disclaimerBox}>
        <Text style={screenStyles.disclaimerText}>
          Fitora provides general fitness and nutrition information and estimates. It is not
          medical advice and is not a substitute for a qualified healthcare professional.
        </Text>
      </View>

      <Pressable style={screenStyles.secondaryButton} onPress={() => void logout()}>
        <Text style={screenStyles.secondaryButtonText}>Log out</Text>
      </Pressable>
    </ScrollView>
  );
}
