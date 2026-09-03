import { Redirect, Stack } from "expo-router";

import { useAuth } from "../../src/auth/AuthContext";

export default function AuthLayout(): React.JSX.Element {
  const { user, isLoading } = useAuth();

  if (!isLoading && user) {
    return <Redirect href="/(tabs)" />;
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}
