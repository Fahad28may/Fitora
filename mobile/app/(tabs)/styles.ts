import { StyleSheet } from "react-native";

export const screenStyles = StyleSheet.create({
  container: {
    flexGrow: 1,
    padding: 24,
    gap: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
  },
  body: {
    fontSize: 15,
    color: "#374151",
    lineHeight: 22,
  },
  disclaimerBox: {
    backgroundColor: "#f3f4f6",
    borderRadius: 10,
    padding: 14,
  },
  disclaimerText: {
    fontSize: 13,
    color: "#4b5563",
    lineHeight: 18,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 8,
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#111827",
  },
});
