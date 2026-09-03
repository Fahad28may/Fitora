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
  setupCard: {
    backgroundColor: "#111827",
    borderRadius: 12,
    padding: 18,
    gap: 4,
  },
  setupCardTitle: {
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },
  setupCardBody: {
    color: "#d1d5db",
    fontSize: 14,
  },
  statRow: {
    flexDirection: "row",
    gap: 10,
  },
  statBox: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  statValue: {
    fontSize: 20,
    fontWeight: "700",
  },
  statLabel: {
    fontSize: 12,
    color: "#6b7280",
    marginTop: 2,
  },
  card: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
});
