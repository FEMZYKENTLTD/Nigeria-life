# 05 · UI/UX Reference Library

## Status: incomplete — no screenshots

No browser could reach the site in this session, so **there are no screenshots, no measured colours beyond two manifest values, no typography measurements, and no responsive testing.** What follows is what can be said from page text, the PWA manifest, the service worker and the developer docs. The capture checklist at the end lists what a person with a browser needs to collect.

## 1. Brand identity (C)

| Element | Observation | Source |
| --- | --- | --- |
| Name and tagline | "Lagos Life — live your Lagos story"; manifest description "Sims, but make it Eko. A life-sim set in Lagos, with real players." | E01, E03 |
| Voice | Nigerian Pidgin and Lagos slang used for system copy: "This road no dey Lagos", "Lagos is still out there", "Lagosians". Policy pages switch to short plain English sentences | E02, E21, E10 |
| Iconography | Emoji carry almost all iconography: venues, status markers, error pages, report categories, cabin classes | E01, E14 |
| Parent brand | "Vatar · Life in Your City" in page footers; developer pages are branded "Vatar Developers" | E12, E16 |

**Design implication.** Emoji-as-icons means no icon font or sprite to download and instant cultural legibility, at the cost of inconsistent rendering across Android vendors and limited accessibility labelling (unverified).

## 2. Colour (C for two values only)

| Token | Value | Source |
| --- | --- | --- |
| App background (splash) | `#eef2f7` — pale blue-grey | E03 |
| Theme colour (browser/OS chrome) | `#16120f` — near-black warm brown | E03 |
| Themes | Dark and light, switchable by the player; community games are told the current theme | E17 |

Everything else about the palette is unknown. (The sample community game uses a purple gradient and amber, but that is a developer demo, not the game's UI.)

## 3. Typography (I)

The service worker caches `fonts.googleapis.com`, `fonts.gstatic.com` and `.woff2` files (E04), so Google-hosted web fonts are used. Families, weights and scale: unknown.

## 4. Layout and navigation patterns

| Pattern | Observation | Class |
| --- | --- | --- |
| Landing | The product itself (the map) is the hero; calls to action float over it. No marketing sections, feature lists or FAQ | C |
| Auth | Overlays on `/`, not separate pages | C (404 on `/login`, `/signup`) |
| Main menu | An in-game phone holds apps: jobs, Support, Settings, Games | C (paths), S (jobs) |
| World navigation | Map → venue → "Things to do" / numbered spots / "People here" | S |
| Long documents | Sibling-policy links at the top and a collapsible "Jump to section" list | C |
| Phone-first | Community games must work at 375 × 812 portrait, by touch, with no hover-only controls; the host keeps a top bar on screen | C (E17) |
| Desktop | A full keyboard shortcut set, discoverable with `?` | S |

## 5. Forms (C)

- Live character counters on text inputs (`0/120`, `0/5,000`).
- Emoji-labelled category chips rather than a dropdown on the report form.
- Quantity steppers (− / +) and tick-box lists on the ad order form, with a running total and a currency toggle.
- Image inputs state accepted formats and that images are compressed before upload "so they're light on data".
- Optional fields are labelled "(optional)".

## 6. States

| State | Copy | Class |
| --- | --- | --- |
| Not found | 🚚 "This road no dey Lagos" + "← Back to the city" | C |
| Offline | 🔌 "You're offline… Trying again in 7s" + "Try again" | C |
| Slow load | "Slow network… still loading" | C |
| Reconnecting | "Reconnecting to Lagos…" | S |
| Session not kept | "You're logged in, but this browser didn't keep it" with advice to open in a real browser | S |
| Returning after absence | "While you were away: your business made …" | S |
| Moderation | The player is told why content was removed and until when a mute lasts; voice rooms show an "AI safety check" sign and a "Think we got it wrong?" link | C |
| Gated developer pages | "Sign in first" with one button | C |

**Design implication.** Error and waiting states are treated as part of the fiction and always offer a way back. This is worth matching.

## 7. Motion, 3D and media

- The world is rendered in 3D from GLB models for characters, furniture and a "city pack" (C, E04). The specific rendering library is not confirmed; a `components/three/` path suggests three.js (I).
- Billboards are "digital screens" rotating ads every 15 seconds (C).
- The birth lottery is described as a spinning reveal (S).
- Transitions and animation timing: unknown.

## 8. Accessibility

Not testable. Risk indicators only: emoji-only icons, a 3D canvas as the primary interface, and no evidence either way of screen-reader support. Positive indicators: keyboard shortcuts (S), plain-language policy pages (C), dark/light themes (C).

## 9. Capture checklist for a human follow-up

Suggested filenames, each at 375, 768 and 1440 px wide:

```
landing-default.png            landing-cookie-banner.png
auth-signup-overlay.png        auth-login-overlay.png
auth-forgot-password.png       system-404.png
system-offline.png             legal-terms-top.png
legal-jump-menu-open.png       help-page.png
report-form-empty.png          report-form-category-selected.png
advertise-form.png             advertise-on-air.png
developers-landing.png         developers-docs-sdk.png
developers-sample-game.png     developers-keys-gate.png
```

In-game captures (creator steps, map, phone, venue, shift, buy mode, top-up screen stopped before payment) should be taken manually by an adult tester on their own account, and used for internal analysis only — not reproduced in our product.
