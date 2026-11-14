# 00 · Investigation Log, Method and Coverage

Investigated: 14 November 2026. Target: https://lagoslife.app/

## 1. How the investigation was done (read this first)

| Item | Reality |
| --- | --- |
| Direct network access from the research sandbox to lagoslife.app | **Not available.** `curl` to the site fails at TLS connect (E29). The sandbox may only reach GitHub, npm and PyPI. |
| What was used instead | A server-side page reader that returns each URL as text/markdown, plus web search. |
| Real browser, DevTools, screenshots, viewport emulation | **Not possible in this session.** |
| HTTP response headers, status codes, DNS, TLS details | **Not observable.** A "404" below means the site's 404 page content was returned; the numeric status is unverified. |
| JavaScript bundles, network waterfall, browser storage | **Not inspected.** |
| Account creation / logged-in gameplay | **Not done.** No account was created; nothing behind login was accessed. |
| Requests made to the operator's domains | About 45 single page reads, spread over the session. No automation loops, no form submissions. |

Consequences:

- Everything about the **public website, legal pages, advertiser page and developer platform** is first-party evidence (class **C**).
- Almost everything about **in-game mechanics** (jobs, pay, rent, needs, businesses, land, travel) comes from unofficial fan guides that say they read the game's client code, plus press coverage. That is class **S** (secondary). It is internally consistent and matches first-party hints, but it has not been verified in the game by us.
- Deliverable 5 contains **no screenshots**. It contains a text-derived design reference and a capture checklist for a human to complete.
- Responsive behaviour (desktop/tablet/mobile) was **not tested**.

## 2. Evidence classes used throughout the package

| Tag | Meaning |
| --- | --- |
| **C** | Confirmed: read directly on a first-party page on 14 Nov 2026 |
| **S** | Secondary: unofficial fan guide or press report; not verified in-game |
| **I** | Strong indication: inferred from first-party evidence, not directly stated |
| **H** | Hypothesis |
| **U** | Unknown / inaccessible |

Evidence IDs (E01…E29) are defined in `12-evidence-register.md`.

## 3. Page discovery checklist

| Route | Result | Evidence |
| --- | --- | --- |
| `/` | Loaded. Landing page over a labelled city map | E01 |
| `/robots.txt` | Site 404 page. **No robots.txt was found** | E02 |
| `/sitemap.xml` | Site 404 page | E02 |
| `/manifest.json` | Site 404 page | E02 |
| `/manifest.webmanifest` | Loaded (PWA manifest) | E03 |
| `/sw.js` | Loaded (service worker, heavily commented). Chunks 1 and 3 of 3 read | E04 |
| `/.well-known/security.txt` | Loaded | E05 |
| `/offline` | Loaded (offline screen) | E21 |
| `/terms` | Loaded, read in full | E06 |
| `/privacy` | Loaded, read in full | E07 |
| `/disclaimer` | Loaded, read in full | E08 |
| `/community-guidelines` | Loaded, read in full | E09 |
| `/child-safety` | Loaded, read in full | E10 |
| `/child-safety-standards` | Loaded, read in full | E11 |
| `/help` | Loaded, read in full | E12 |
| `/delete` | Loaded (logged-out state) | E13 |
| `/report` | Loaded (form seen, not submitted) | E14 |
| `/advertise` | Loaded (order form seen, not submitted) | E15 |
| `/developers` | Loaded | E16 |
| `/developers/docs` | Loaded, read in full | E17 |
| `/developers/agreement` | Loaded; sections 1–15 read, 16–19 **not read** | E18 |
| `/developers/sample` | Loaded | E19 |
| `/developers/keys`, `/developers/dashboard` | "Sign in first" gate. Not passed | E20 |
| `/developers/sandbox/<draft>` | Referenced in docs. Not visited (needs a developer draft) | E17 |
| `/stats` | Returned the **homepage** content. Fan sites and press describe a live stats page; we could not see it | E01, E28 |
| `/login`, `/signup`, `/about`, `/games`, `/store`, `/ipo`, `/partners` | Site 404 page. Login and sign-up are overlays on `/`, not routes | E02 |
| `naijalife.app/` | Same landing page | E01 |
| `lagoslife.eliysites.com/stats` | Same landing page | E01 |

Not visited at all: `/sdk/vatar-games-v1.js`, any `/api/*` endpoint, `/_next/static/*`, `/models/*`, `/icons/*`, `vatar.com`, the app-store listings, the four social profiles, the game itself.

**Coverage statement.** The public, logged-out website surface appears small and is probably close to fully mapped, but with no sitemap and no link crawler this cannot be proven. The game — which is the product — was not entered. Coverage of in-game features is therefore **not exhaustive** and rests on secondary sources.

## 4. A redirect observation

For most pages the reader reported the final address as `vatarverse.com/...` rather than `lagoslife.app/...`, and internal links were written against `vatarverse.com`. The developer docs list `vatarverse.com` among the operator's own origins (E17). This suggests the site answers on, or redirects to, `vatarverse.com` for some clients (**I**). It was not confirmed with headers.

## 5. Conflicts between sources (unresolved)

| Topic | Source A | Source B |
| --- | --- | --- |
| Minimum age | Terms (23 Oct): 13+, teens in a separate space "where it is open" | Fan guides (early Oct): 18+ only. The Terms likely supersede; teen space rollout status is unknown |
| Careers | lagoslifeguide.com: 33 careers | lagoslifegame.org: 23 careers |
| Lagos places | lagoslifeguide.com: 34 | lagoslifegame.org: 37; homepage map labels: 36 named + 4 "coming soon" |
| Airport | Homepage map label: "Airport · Coming soon" | Fan guide and `/advertise`: airports exist in three cities |
| Billboard price | `/advertise` today: ₦250,000 / 7 days | Press, 5 Oct: ₦5,000 rising to ₦50,000 / week |
| Native app | Privacy policy: "Vatar: Life in Your City" for iPhone and Android | Fan sites disagree on whether an official app exists; one names a Google Play app by another publisher as unrelated |
| Password reset | Privacy policy: email used for resets | Help page + fan guide: reset by "owner questions", no email link |

## 6. Legal and ethical boundaries observed, and ones to keep

- The Terms prohibit scraping without permission, automation, and reverse engineering (E06 §19, §23). This session read public pages at human-scale volume only.
- The Developer Agreement forbids using the developer tools "to build a competing platform" (E18 §2.2e). **Do not register for developer keys for competitive research.**
- The fan guides state they read the game's client code. We cite their published numbers as secondary evidence; we did not obtain or read that code.
- Nothing here should be copied into our product: no names of their venues-as-branded, text, art, 3D models, code or SDK shapes.

## 7. Open items for a follow-up pass (needs a human with a browser)

1. Manual, logged-in walkthrough with a consenting adult tester's own account: creator flow, phone apps, map, a work shift, a purchase screen (stop before paying).
2. Screenshots at 375, 768 and 1440 px for the landing page, auth overlay, legal pages, `/advertise`, `/developers`.
3. Response headers for `/` (hosting, caching, security headers) and the `/stats` behaviour.
4. Confirm teen-space status, native-app status, current top-up bundle prices.
5. Read Developer Agreement sections 16–19.
