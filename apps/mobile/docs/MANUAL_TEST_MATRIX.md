# Manual test matrix (EventFlow mobile)

Run on **release or dev client** builds, not Expo Go, for share extension and file handoff.

| # | Scenario | Steps | Expected |
|---|----------|-------|----------|
| 1 | Paste import | Home → Paste a link → enter TikTok or event URL → Continue | Processing → Draft with fields populated |
| 2 | Text-only import | Paste copy without URL | `share/text` path; draft or validation error surfaced |
| 3 | Android share | Chrome or Instagram share sheet → EventFlow | App opens; Processing runs with shared text |
| 4 | iOS share | Safari / TikTok share → EventFlow extension | Host app opens; draft flow runs |
| 5 | Logged-out share | Sign out; share from another app | Payload queued; after sign-in, Processing runs once |
| 6 | Confirm | Draft → Confirm | Confirmed screen; upcoming list shows event |
| 7 | ICS export | Confirmed → Share calendar file | Share sheet with `.ics` |
| 8 | Edit draft | Draft → Edit details → Save | PATCH applied; detail screen reflects changes |
| 9 | 401 recovery | Revoke session server-side or expire JWT | User-friendly error; optional refresh path on retry flows |
|10 | Sign out | Home → Sign out | Redirect to Auth; no stale Home stack |
|11 | Link thumbnail (YouTube) | Import a YouTube link → Processing/Draft screens | Thumbnail renders via `/api/v1/media/thumbnail?url=...` (URL is encoded); no CORS issues |
|12 | Link thumbnail (Instagram best-effort) | Import a public Instagram reel/post link | If extraction works: thumbnail renders. If not: placeholder “No preview” (expected without cookies/login) |
|13 | Port sanity | Ensure `EXPO_PUBLIC_EVENTFLOW_API_URL` points to backend (`:8000`) not Metro (`:808x`) | API calls succeed; “Network request failed” only occurs if base URL is wrong/unreachable |

Record failures with OS version, build profile, and API logs (`application/problem+json` bodies).
