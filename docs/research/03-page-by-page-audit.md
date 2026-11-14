# 03 · Page-by-Page Website Audit

All pages were read as rendered text on 14 Nov 2026 (class C unless stated). Interactions were **seen as labels, not operated** — no button was clicked and no form submitted. Layout, colours and responsive behaviour were not observable.

## 1. `/` — Landing page

- **Title:** "Lagos Life — live your Lagos story".
- **Backdrop:** a city map with 36 emoji-labelled venues (Afrika Shrine, Viewing Centre, Amala Shitta, CcHub, Market, Freedom Park, i-Fitness, Marina Towers, Quilox, Canopy Walk, The Palms, The Library, Beach, General Hospital, Mama Bisi's Salon, Ivory Rooftop, Police Station, Church, Mosque, Naija Radio, Polling Unit, Eko Hotels, Polanco Motors, Boat Cruise, Ikoyi Golf Club, High Court, UNILAG, Eko Casino, MindSpace, Stadium, Charterhouse, Snooker Spot, Computer Village, HANDI HQ, Mako, Jibowu Park) and four construction labels (Stadium · Under Construction; Airport, Refinery and "OBO" · Coming soon).
- **Presence markers:** about 16 `@handles` prefixed 🏠 or 🟢. Likely "at home" and "online" (I). Whether these are live players or sample data is unknown.
- **Top bar:** "224k active today", "👀 76.9M visits", "Sign up", "Log in".
- **Hero:** chips "🏛️ Elect a Governor", "🌊 Sea Plots", "🏘️ 400 homes"; line "224k Lagosians played today · free"; buttons "Sign up free" and "Log in".
- **Footer:** "Official" links to X, TikTok, Instagram, LinkedIn.
- **Cookie banner:** "We use a cookie to keep you signed in, and another to count visits. No ad trackers, ever." Link to Privacy. Buttons "Essential only" and "Accept".
- **Loading notice:** "Slow network… still loading" appears in several page reads.
- **Not seen:** the sign-up and log-in overlays themselves; links to Terms, Help, Advertise or Developers from the landing page (they may exist inside overlays).

## 2. Legal and policy pages

All share a header with links to sibling policies and a "Jump to section" control.

| Route | Title | Effective | Content summary |
| --- | --- | --- | --- |
| `/terms` | Terms of Use | 23 Oct 2026 | 34 sections. See `01`, `02`, `08` for extracted rules |
| `/privacy` | Privacy & Cookie Policy | 23 Oct 2026 | 19 sections. Data inventory, processors, retention, deletion, teens |
| `/disclaimer` | Game, Brand & Real-World Content Disclaimer | 1 Oct 2026 | 21 sections. Fictional treatment of brands, state bodies, places, money |
| `/community-guidelines` | Community Guidelines | 23 Oct 2026 | 8 sections. Rules, strikes, appeals |
| `/child-safety-standards` | Child Safety Standards | 23 Oct 2026 | 6 sections. Zero tolerance, prevention, reporting |
| `/child-safety` | How we keep teens safe | — | Plain-language teen protections |

## 3. `/help` — Help and safety

Sections: Get help (in-game Support, public report form, email); Report a player; Community rules; Can't get in?; Delete your account; Teens and parents; Your data. Readable without login.

## 4. `/delete` — Delete your account

Explains consequences, the 30-day undo, and the 90-day username reservation. Logged out, it tells the visitor to log in and return, at which point "the delete button appears here". Alternative: `/report` → "Account problem".

## 5. `/report` — Report a problem or security issue

| Element | Detail |
| --- | --- |
| Category picker | Security bug · Cheating or bots · Money or payments · Account problem · Appeal a safety decision · Something else |
| Title | Counter 0/120 |
| Description | Counter 0/5,000 |
| Screenshots | Optional, up to 3; JPG, PNG or WebP; compressed client-side before upload |
| Contact | Optional |
| Submit | "Send report" |
| Check a report | Enter a reference to see status |

Submission response, validation errors and reference format: not observed.

## 6. `/advertise` — Advertise in Lagos Life

A three-step order form, no account required.

1. **What you want:** Billboards (₦250,000 each, 7 days, 20 digital boards, quantity stepper starting at 1); Sea Plots (6×6, ₦18,000 each, 7 days, stepper starting at 0); Airport boards (₦500k / 7 days, tick boxes for boards 201–210 across Lagos, Abuja and Port Harcourt airports: Arrivals, Departures, Car Park, Private Jets).
2. **Your logo or ad:** image upload (PNG, JPG, WebP), fitted without cropping.
3. **Your details:** business name, website or social link, email, optional phone.

A running total (₦250,000 by default) with an NGN/USD toggle. A section "On air now" shows current ads. Rules: ads rotate 15 seconds each; new ads go to the least-crowded boards; rule-breaking ads are removed without refund; payment by Flutterwave; an option to publish later is implied ("or when you press Publish, if you pick later").

## 7. Developer portal

| Route | Content |
| --- | --- |
| `/developers` | Headline "Build games for our worlds." Two calls to action: "Get your keys" and "Read the docs" |
| `/developers/docs` | 14 sections: architecture, quick start, sample, keys, SDK reference, purchase flow, matches, server API, webhooks, errors, rate limits, security, review checklist, getting paid. Code blocks have "Copy" buttons |
| `/developers/agreement` | 19 sections, version 1.0, effective 11 Oct 2026 |
| `/developers/sample` | Playable "Tap Tap Lagos" demo marked "DEMO · NO MONEY", with tabs for game, server and match source |
| `/developers/keys` | Gated: "Sign in first" → "Sign in to Vatar" |
| `/developers/dashboard` | Gated the same way |

## 8. System pages and files

| Route | Content |
| --- | --- |
| 404 | 🚚 "404 — This road no dey Lagos — The page you wanted has moved, or it never existed." Link "← Back to the city" |
| `/offline` | 🔌 "You're offline — Lagos is still out there. Trying again in 7s." Buttons "Try again" and "← Back to the city" |
| `/manifest.webmanifest` | See `06` |
| `/sw.js` | See `06` |
| `/.well-known/security.txt` | Contact `/report`; English; expires 9 Nov 2027 |

## 9. In-game screens (not accessed — reconstructed from secondary sources)

Reported surfaces (S, E22): the map; home with Buy mode and a catalogue; the phone; a needs-and-skills panel; a venue view with "Things to do", numbered spots and "People here". Reported desktop shortcuts: `M` map, `H` home, `B` buy mode, `P` phone, `S` Sim panel, `T` things to do, `E` people here, `1–9` pick a spot, arrows/`R`/`Enter`/`Del` for furniture, `C` catalogue, `Esc`, `?`.

First-party confirmation exists only for these in-game paths: Phone → Support → Contact support / Chat with support; Phone → Settings → Account → Delete account; Settings → Blocked players; Settings → Security; Settings → "Who can message me"; a Games app on the phone (E12, E13, E17).
