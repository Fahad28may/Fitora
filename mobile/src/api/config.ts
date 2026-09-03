// EXPO_PUBLIC_-prefixed env vars are inlined into the client bundle by Expo,
// so only put values here that are safe to ship to the device — never secrets.
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
