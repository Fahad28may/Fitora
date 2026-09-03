# Fitora Mobile

Expo + React Native + TypeScript client, using [Expo Router](https://docs.expo.dev/router/introduction/) for file-based navigation.

## Setup

```bash
cd mobile
npm install
cp .env.example .env   # point EXPO_PUBLIC_API_URL at your running backend
npm start
```

Requires the [backend](../backend/README.md) running locally (or reachable) at the URL in `EXPO_PUBLIC_API_URL`.

## Project layout

```text
app/            Expo Router routes (file-based navigation)
  (auth)/       Login / register — shown when signed out
  (tabs)/       Home, Nutrition, Workout, Progress, Coach — shown when signed in
src/
  api/          Backend API client, typed request/response models
  auth/         Auth context, token storage (expo-secure-store)
```

## Auth

Access/refresh tokens are stored via `expo-secure-store` (OS keychain/keystore), never `AsyncStorage`. The API client automatically retries a request once after a silent token refresh on `401`.

## Notes

- `EXPO_PUBLIC_*` env vars are inlined into the client bundle — never put secrets in them. See `.env.example`.
- Placeholder tab screens (Nutrition, Workout, Progress, Coach) are intentionally minimal until their backend features ship — see [`../docs/roadmap.md`](../docs/roadmap.md).
