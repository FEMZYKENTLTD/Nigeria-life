# 06 · Technical Architecture Report

Built only from first-party text: the service worker (E04), manifest (E03), privacy policy (E07), developer docs (E17) and agreement (E18). No headers, bundles, network traces or DNS records were available.

## 1. Confirmed observations

### Front end

| Finding | Evidence |
| --- | --- |
| Static app code is served from `/_next/static/` with hashed filenames | E04 |
| The code base has paths `lib/game/pwa.ts`, `lib/game/boot-script.ts`, `components/three/load-retry.ts`, `components/three/model-guard.tsx` — TypeScript with TSX components | E04 comments |
| 3D assets are `.glb` files under `/models/` (`/models/chars/…`, `/models/furniture/…`, a "city pack") | E04 |
| About 889 code files were fetched on a cold load as of 11 Oct 2026 | E04 comment |
| Fonts come from Google Fonts hosts and local `.woff2` | E04 |
| Installable PWA: standalone display, any orientation, `start_url` `/?source=pwa`, `en-NG` | E03 |
| A service worker (rev 6) handles caching, offline fallback and web push | E04 |
| Dark and light themes | E17 |
| Login and sign-up are not separate routes | E02 |

### Service worker behaviour (E04)

| Request type | Strategy |
| --- | --- |
| `/api/*` | Never cached; always live. Exception: `/api/ads/{id}/image?v=` and `/api/sea/{id}/image?v=` kept in a small cache capped at 80 |
| `/_next/static/*` | Cache-first in a per-build cache; previous build's cache retained so unchanged files are not re-downloaded |
| `/models/*`, `.woff2` | Cache-first in a versioned asset cache (`ll-assets-v2`), with integrity checks: content length must match and a GLB's header and chunks must parse; bad copies are dropped and refetched |
| Icons and images | Stale-while-revalidate |
| Page navigations | Network-first, falling back to `/offline` |
| Downloads | Retried up to 4 times with backoff; a try is abandoned only after 20 s with no bytes; truncated responses are never stored |
| Page ↔ worker messages | `ll-drop` (forget a bad file), `ll-keep` (pre-cache used code files, up to 400) |
| Push | Shows a notification unless a game window is focused; supports `silent`, `tag`, deep-link `url`; a click focuses the open window and posts `{type: "open", url}` |

The comments are an unusually candid change log: white screens on weak mobile data, truncated scripts and models, a model update shipped without a cache bump, players reporting data and battery drain. **Weak-network delivery of a large 3D web client is their hardest front-end problem.**

### Back end and API

| Finding | Evidence |
| --- | --- |
| Same-origin API under `/api/` | E04 |
| Public, documented REST API at `/api/games/v1` for community-game servers | E17 |
| Endpoints: `POST /session/verify`, `GET /purchases/{id}`, `POST /purchases/{id}/deliver`, `GET /matches/{id}`, `POST /matches/{id}/result` | E17 |
| Auth: `Authorization: Bearer vtr_test_…` or `vtr_live_…`; secrets stored hashed, shown once, rotatable | E17 |
| Errors: `{ "error": "<code>", "message": "…" }` with 400/401/403/404/409/429/500 and named codes | E17 |
| Rate limits: 600 calls a minute per game per mode; 30 failed secret checks a minute per address; `Retry-After` on 429 | E17 |
| Webhooks: `purchase.paid`, `match.started`, `match.settled`; HMAC-SHA256 signature header; 5 s timeout; retries at 1 min, 10 min, 1 h, 6 h; strict address rules against internal targets | E17 |
| Match results require a second secret and a signed canonical string (method, path, timestamp, per-match nonce, body hash), with a 5-minute clock window and idempotent settlement | E17 |
| Session tokens for games: signed, 15-minute life, prefixed `vtr1.` | E17 |
| Embedded games run in a sandboxed iframe with a postMessage SDK limited to named origins, 8 KB messages and strict message shapes | E17 |
| Web sessions are cookie-based, 60 days | E07 |
| Passwords stored as hashes | E07 |
| An admin console with feature "Switches" exists | E04 comment |

### Infrastructure and third parties (stated by the operator, E07 §9–10)

| Provider | Role |
| --- | --- |
| Cloudflare | Hosting, security, "website and app servers", live voice rooms, in-memory speech-to-text for safety, bot checks, object storage for voice notes and pictures, IP-based approximate location |
| AWS, London (eu-west-2) | "Main database and servers"; account emails |
| Google Firebase Cloud Messaging | Push to the native app (no Firebase Analytics) |
| Flutterwave | Web payments and partner-store orders (an earlier provider was used before 6 Oct 2026) |
| OpenAI | In-game helper, AI judge, picture checks, text moderation, voice-note transcription in court |
| Resend | Backup email |
| ScoreBat | Football highlights embed |
| DigitalOcean | Former host; read-only data from before 4 Oct 2026 |
| Apple / Google | App distribution and in-app purchases "when offered" |

No analytics or advertising SDKs, by the operator's own statement.

### Domains

`lagoslife.app` (primary), `naijalife.app`, `lagoslife.eliysites.com` (original; redirects to primary), `vatarverse.com`, and `vatar.com` (named in the developer agreement and support email).

## 2. Strong indications

| Inference | Basis | Confidence |
| --- | --- | --- |
| The front end is a Next.js application (React) | `/_next/static/` path convention plus TSX component paths | High |
| The 3D layer uses three.js, possibly via a React wrapper | `components/three/` directory name, GLB assets | Medium |
| Cloudflare sits in front of all traffic and serves static files | "Cloudflare serves public/offline.html" plus the policy's hosting statement | High |
| The front end runs on Cloudflare's edge platform rather than a conventional Node host | Policy says Cloudflare provides "the website and app servers"; webhook rules ban `*.workers.dev` targets, suggesting familiarity with that platform | Medium |
| Real-time presence and chat use persistent connections | A shared live city, a "Reconnecting to Lagos…" state, and the worker ignoring non-GET and `/api` traffic | Medium; protocol unknown |
| Teen and adult worlds are separate deployments | "their own database and servers" | High (operator statement) |
| Money is recorded in an append-only ledger | Repeated references to a "transaction or game ledger", reversals, reconciliation | High |
| The site also answers on `vatarverse.com` for some clients | The page reader's final URLs | Medium |

## 3. Hypotheses

- The database is relational (ledger, reconciliation and idempotent settlement fit that), hosted on a managed AWS service. **No direct evidence of the engine.**
- Live voice uses Cloudflare's real-time media products. The policy says Cloudflare runs voice rooms; the specific product is not named.
- The original build was a single developer's project on a small host, migrated to Cloudflare + AWS on about 4 October 2026 under load (the policy's host change date; press reports a solo developer).

## 4. Unknown or inaccessible

Database engine and schema; real-time protocol; state-management library; styling system; build tooling; the private game API (`/api/*` other than the documented games API); security headers and CSP; TLS and DNS configuration; bundle sizes and load timings; how the game clock is synchronised; server authority over movement and actions; anti-cheat design beyond the policy's description.

## 5. Performance and reliability (qualitative only)

- Cold start is heavy (hundreds of code files plus 3D models). The operator has invested in resumable, verified, patient downloads rather than in shrinking the client (C, E04).
- Press reports lag at peak concurrency and monthly infrastructure costs in the low thousands of dollars at about 2.5 million sign-ups (S, E27).
- Minimum browsers reported by a fan site: iOS 16.4, Chrome 94, Firefox 93; Opera Mini unsupported (S, E28). Opera Mini's exclusion matters in Nigeria.

## 6. Lessons for our architecture

1. Treat weak mobile data as the default case from the first commit: small initial payload, progressive asset loading, verified caching.
2. A 3D world is costly on low-end Android. A 2D or 2.5D presentation with optional richer scenes would reach more devices.
3. Use a double-entry ledger for all currency movement, with idempotency keys, from day one.
4. Server-authoritative outcomes for anything that pays out; never trust the client.
5. Their third-party games design (sandboxed frame, host-owned pay sheet, server-verified purchases, signed results) is a sound reference pattern for any extension system — to be designed independently, not copied.
6. Keep teen and adult data physically separate if minors are ever admitted.
