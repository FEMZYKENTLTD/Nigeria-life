# 12 · Evidence and Source Register

All items investigated on **14 November 2026**. No screenshots exist for any item (see `00-investigation-log.md` §1). Class: C = first-party confirmed, S = secondary, I = inference.

| ID | Source URL | Page / component | Key observations | Class |
| --- | --- | --- | --- | --- |
| E01 | https://lagoslife.app/ (also naijalife.app, lagoslife.eliysites.com) | Landing page | Title "Lagos Life — live your Lagos story". 36 emoji-labelled venues; 4 "coming soon" labels (Stadium under construction, Airport, Refinery, "OBO"); ~16 player handles shown with 🏠 or 🟢 markers; counters "224k active today", "76.9M visits"; chips "Elect a Governor", "Sea Plots", "400 homes"; buttons "Sign up free" / "Log in"; four official social links; cookie banner ("Essential only" / "Accept") stating one sign-in cookie, one visit-count cookie, no ad trackers | C |
| E02 | /robots.txt, /sitemap.xml, /manifest.json, /login, /signup, /about, /games, /store, /ipo, /partners | 404 page | "This road no dey Lagos" with 🚚, "← Back to the city". Also a "Slow network… still loading" notice | C |
| E03 | /manifest.webmanifest | PWA manifest | name "Lagos Life"; description "Sims, but make it Eko…"; start_url `/?source=pwa`; display standalone; background `#eef2f7`; theme `#16120f`; categories games/entertainment/social; lang en-NG; icons 192/512 + maskable + SVG | C |
| E04 | /sw.js | Service worker (rev 6, 22 Oct 2026) | Paths `/_next/static`, `/models/*.glb`, `/api/*`, `/api/ads/{id}/image`, `/api/sea/{id}/image`; cache names `ll-code-*`, `ll-assets-v2`, `ll-shell-*`, `ll-ads`; source paths `lib/game/pwa.ts`, `lib/game/boot-script.ts`, `components/three/load-retry.ts`, `components/three/model-guard.tsx`; Google Fonts hosts; web push handlers; comment "889 code files"; "Cloudflare serves public/offline.html"; "Admin → Switches" | C |
| E05 | /.well-known/security.txt | Security contact | Contact = /report; expires 2027-11-09 | C |
| E06 | /terms | Terms of Use, effective 23 Oct 2026 | Operator "Vatar"; domains; 13+ with teen space; adult-only areas; Game Naira rules; Flutterwave; community games 70/30; purchasable items list; refunds; ad formats; prohibited conduct; device fingerprinting; enforcement; soft deletion; Nigerian law; support@vatar.com | C |
| E07 | /privacy | Privacy & Cookie Policy, effective 23 Oct 2026 | Data collected; one-device rule; processors (Cloudflare, AWS London eu-west-2, Firebase Cloud Messaging, Apple/Google, Flutterwave, OpenAI, Resend; DigitalOcean former host); 60-day web sessions; voice notes 90 days; deletion flow; teen protections; "IPO offer" mention; NDPA 2023 | C |
| E08 | /disclaimer | Game, Brand & Real-World Content Disclaimer, effective 1 Oct 2026 | Fictional treatment of brands, government, locations, money ("spraying"), finance (shares, crypto, loans, insurance), crime and politics | C |
| E09 | /community-guidelines | Community Guidelines | Prohibited content; strike/mute ladder (2 h, 12 h, 24 h); auto-moderation; appeals | C |
| E10 | /child-safety | Teen safety explainer | Separate teen city; contact-only rules; quiet hours 10 pm–7 am; break nudges | C |
| E11 | /child-safety-standards | CSAE standards | Separate teen database and servers; NCMEC reporting; 14-day limit on teen accounts created on a phone that held an adult account | C |
| E12 | /help | Help and safety | In-game Phone → Support; report/block; "Forgot password?" via owner questions; "Someone stole my account" | C |
| E13 | /delete | Account deletion | Phone → Settings → Account → Delete; 30-day undo; username reserved 90 days; lists Sim, money, homes, land, cars, businesses | C |
| E14 | /report | Public report form | 6 categories; title ≤120 chars; body ≤5,000; up to 3 images; optional contact; reference lookup | C |
| E15 | /advertise | Self-serve ad booking | Billboards ₦250,000 / 7 days, 20 digital boards (8 giant), 15 s rotation; Sea Plots 6×6 ₦18,000 / 7 days; airport boards ₦500k / 7 days (10 boards across Lagos, Abuja, Port Harcourt airports); NGN/USD toggle; Flutterwave; no account needed | C |
| E16 | /developers | Developer landing | "Build games for our worlds… nearly 12 million players" | C |
| E17 | /developers/docs | Vatar Games SDK v1 docs | iframe model; `Vatar.*` SDK; REST base `/api/games/v1`; keys `vtr_test_`/`vtr_live_`; webhooks; matches with Game-Naira stakes, 5% house cut; limits; error codes; rate limits; review checklist | C |
| E18 | /developers/agreement | Developer Agreement v1.0, effective 11 Oct 2026 (§1–15 read) | 70/30 split; ₦100–₦50,000 products; monthly payout ≥ ₦5,000; no gambling; ban on building a competing platform with the tools | C |
| E19 | /developers/sample | "Tap Tap Lagos" sample | Live demo and source for game, server and match | C |
| E20 | /developers/keys, /developers/dashboard | Auth gates | "Sign in first… Sign in to Vatar" | C |
| E21 | /offline | Offline screen | 🔌 "You're offline… Trying again in 7s" | C |
| E22 | https://lagoslifeguide.com/how-to-play/ | Fan guide (checked 8 Oct 2026) | Sign-up fields; creator flow; five dreams; six needs; work modes; transport fares; keyboard shortcuts; UNILAG; gem hunt; governor; relationships | S |
| E23 | https://lagoslifeguide.com/jobs/ | Fan guide | 33 careers × 5 levels; pay tables; promotion rules (first chunk read) | S |
| E24 | https://lagoslifeguide.com/make-money/ | Fan guide | Gig formulas; 8 businesses; trailer; 6 land plots; transfer fee; tax bands; rents | S |
| E25 | https://lagoslifeguide.com/nepo-baby-vs-lapo-baby/ | Fan guide | Birth lottery; starting packages per city | S |
| E26 | https://lagoslifeguide.com/abuja-life-game/ | Fan guide | Abuja: 69 places, 348 activities, 5 homes, 5 careers; flight cabins and fares; bus/drive risk table; insurance | S |
| E27 | innovation-village.com, allbiohub.com, bizwatchnigeria.ng, blog.gosub.ng (Oct 2026) | Press | Launch 1 Oct 2026; founder Shalom Rayhamen; Vatar, Inc. (Delaware, 5 Oct); reported $500k raise at $10M valuation; reported player and revenue figures (developer-reported, unverified); five revenue streams; economy exploit and balance resets; top-up bundles ₦500–₦20,000 | S |
| E28 | Search snippets: lagoslifegame.org, lagoslife.games, lagoslifestylegame.com, lagos-life.xyz, lagoslifegame.co | Other fan sites | Conflicting counts (23 careers, 37 places, ~344 activities); browser minimums (iOS 16.4, Chrome 94); `/stats` page described with 30 s refresh; conflicting claims about a native app | S |
| E29 | Sandbox `curl -I https://lagoslife.app/` | Tooling | TLS connect failure — the sandbox cannot reach the site | C |
