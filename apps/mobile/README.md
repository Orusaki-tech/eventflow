# EventFlow mobile

Expo (React Native) client for the EventFlow API: **share or paste** messy links and social text, get a **structured draft**, then **confirm** and optionally **export `.ics`**.

## Requirements

- Node 20+
- [Expo dev client](https://docs.expo.dev/develop/development-builds/introduction/) (Share Sheet and push require native builds; Expo Go is limited.)
- Xcode 16+ / CocoaPods 1.16+ for iOS share extension (`@bacons/apple-targets`)
- Backend with **Supabase JWT** verification configured (`SUPABASE_JWKS_URL`, etc.) so the same user id is used for draft create → patch → confirm.

## Environment

Copy `.env.example` to `.env` and set:

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_EVENTFLOW_API_URL` | API origin, e.g. `http://localhost:8000` |
| `EXPO_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `EXPO_PUBLIC_APPLE_TEAM_ID` | Optional; silences prebuild warning and helps signing |

## Commands

```bash
npm install
npm run start          # Metro
npm run test           # Unit tests (payload normalization)
npm run typecheck      # TypeScript
npx expo prebuild      # Regenerate ios/ android (gitignored)
npx expo run:ios
npx expo run:android
```

## Native behavior

### Android

- **Intent filter** `ACTION_SEND` / `text/plain` so EventFlow appears in the share sheet.
- **Config plugin** [`plugins/withAndroidShareHandoff.js`](plugins/withAndroidShareHandoff.js) persists `EXTRA_TEXT` to `eventflow-share-handoff.json` under the app files directory; JS reads it on resume (see [`src/hooks/useShareHandoff.ts`](src/hooks/useShareHandoff.ts)).

### iOS

- **Share extension** in [`targets/share/`](targets/share/) (type `share` via `@bacons/apple-targets`): collects URLs/plain text, writes to the **App Group** (`group.com.eventflow.mobile`), opens `eventflow://share-handoff`, then the host app reads the handoff via `ExtensionStorage`.

### Deep links (testing)

- `eventflow://import?text=<url-encoded>` — opens import pipeline when logged in; otherwise queues until after sign-in.

## Privacy (store listings)

- The app sends pasted or shared **URLs and text** to your **EventFlow backend**, which may fetch remote pages and call **Google Gemini** (see server README).
- **Push tokens** are sent to `POST /api/v1/users/me/push-tokens` (Expo).
- **Supabase** handles authentication; link your privacy policy for auth data.

Further manual scenarios: [`docs/MANUAL_TEST_MATRIX.md`](docs/MANUAL_TEST_MATRIX.md).
