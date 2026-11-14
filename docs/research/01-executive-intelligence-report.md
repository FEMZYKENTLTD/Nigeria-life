# 01 · Executive Intelligence Report

Evidence tags (C/S/I/H/U) and IDs are defined in `00-investigation-log.md` and `12-evidence-register.md`.

## 1. The three findings that change the plan

1. **Lagos Life is no longer a Lagos-only product.** Its Terms describe "one game world, multiple locations… across Nigeria" (C, E06 §5). Abuja and Port Harcourt are reported live since about 6 October 2026, joined by in-game airports and intercity buses (S, E26, E27; supported by airport ad boards in all three cities on the first-party ad page, C, E15). The operator also runs `naijalife.app` and brands the company "Vatar: Life in Your City" (C, E06, E07). "Nationwide" on its own is therefore not a differentiator; they are already walking that road.
2. **It is becoming a platform, not just a game.** There is a public SDK that lets third-party web games run inside the in-game phone, sell items for real money on a 70/30 split, and host staked multiplayer matches in game currency (C, E17, E18).
3. **This investigation could not enter the game.** The sandbox had no network path to the site and no browser. The public website is documented first-hand; in-game mechanics are documented from fan guides and press and are marked as secondary. No screenshots were captured. See `00-investigation-log.md`.

## 2. What Lagos Life is

A free, browser-based, multiplayer life simulation in the style of The Sims, set in a stylised Nigeria (C, E03, E06). Players create a "Sim", receive a random privileged or indebted start, rent a home, work shifts, train skills, buy businesses and land, socialise, date, vote for a player-governor, and move between Lagos, Abuja and Port Harcourt (S, E22–E26).

- **Operator:** "Vatar", Nigeria, per the legal pages (C). Press reports Vatar, Inc. was incorporated in Delaware on 5 October 2026 by founder Shalom Rayhamen (S, E27).
- **Launch:** 1 October 2026 (S, E27; the Disclaimer's effective date is 1 October 2026, C, E08).
- **Scale claims:** the landing page showed "224k active today" and "76.9M visits"; the developer page says "nearly 12 million players" (C that the site says this; the numbers themselves are operator-reported).
- **Funding:** a reported $500,000 round at a $10M valuation (S, E27).

## 3. How the product is structured

| Layer | What exists | Class |
| --- | --- | --- |
| Landing page | A labelled city map as the backdrop, live counters, sign-up/log-in overlays | C |
| The game | 3D rendered world (GLB models, a `components/three` code path), an in-game **phone** as the main menu (jobs, Support, Settings, Games app), a map, venues with activities | C for the technical hints (E04) and the phone paths (E12); S for the gameplay |
| Social layer | Venue chat, DMs, groups, voice notes, live voice rooms ("Spaces"), a public feed ("Lagos Gist"), a "Hustle" board, stickers, friends/family/partners/followers | C (E06, E07, E09) |
| Civic layer | Weekly governor elections, campaign texts, policies, a "Live Court" with an AI judge, police and crime | C that these exist (E06 §3, E07 §9); S for rules |
| Economy | "Game Naira": wages, rent, tax, loans, businesses, land, shares, insurance, betting ("LagosBet"), casino, player transfers | C that these exist (E06, E08); S for numbers |
| Commerce | Real-money top-ups, self-serve billboards and "Sea Plots", brand integrations, partner stores with delivery addresses, community-game sales | C (E06, E07, E15) |
| Developer platform | SDK, sandbox, dashboard, review process, payouts | C (E17, E18) |
| Safety | Age gate, separate teen world, automated text and voice moderation, strike ladder, reporting, account recovery | C (E09–E12) |

## 4. How the economy works (summary; detail in `02` and `08`)

- **Faucets (S):** shift pay (₦6,600–₦99,000 per shift across 33 careers × 5 levels), gigs, business and haulage income, land appreciation, a daily gem hunt, a governor's allowance, a start-up pitch, and purchased top-ups (C that top-ups exist).
- **Sinks (S):** weekly rent, a starting loan, progressive tax above ₦1,000,000 a week, transport and intercity fares, food and health, furniture, a 5% player-transfer fee, a 5% land-sale fee, 40% loss when selling a business, fines and bail, campaign fees.
- **Hard rule (C):** Game Naira cannot be withdrawn, redeemed or sold; betting and the casino use Game Naira only (E06 §3, §6).
- **Known stress (S):** press reports an early transfer exploit, players holding "trillions", and balances being reset (E27). The Terms reserve the right to rebalance and reverse (C, E06 §8).

## 5. Business model (detail in `08`)

Confirmed on first-party pages: real-money purchase of Game Naira via Flutterwave; self-serve advertising (₦250,000 per billboard per week; ₦18,000 per Sea Plot per week; ₦500,000 per airport board per week); negotiated brand integrations; a 30% platform share on community-game sales; a 5% house cut on staked matches (in game currency); partner stores. The privacy policy also mentions a website-only "IPO offer" involving a payment provider, an identity check and an "issuing house" — its nature is unknown (C that it is mentioned; U what it is).

## 6. Strengths

- Cultural specificity is the product: Pidgin copy ("This road no dey Lagos"), the Nepo/LAPO birth lottery, omo-onile land fees, NEPA outages, danfo fares.
- Zero-install distribution with a carefully engineered weak-network loader (C, E04).
- An economy with real sinks, and a legally careful definition of the currency.
- Monetisation that does not depend on ad-tech: in-world ads sold self-serve, with a privacy position to match (C, E07).
- A serious trust-and-safety and child-safety posture for a product this young.
- A developer platform with a secure, well-documented payment and match model.

## 7. Weaknesses and openings

- No robots.txt or sitemap, and login/sign-up are overlays without their own URLs (C) — weak discoverability, which a crowd of unofficial guide and clone sites now fills (S).
- Heavy client: the service worker comments mention 889 code files and failures on weak data (C, E04).
- One account, one device at a time (C, E07).
- Account recovery relies on gameplay "owner questions" rather than a standard verified channel (C, E12; S, E22).
- Economy balance incidents in the first weeks (S).
- Only three cities; UNILAG is the only university (S). No evidence of local-language support, production chains (farming, manufacturing), or state-level government (U — absence in our sources is not proof of absence).
- Sources conflict on basic facts (age rule, app availability, counts) — a sign that official documentation for players is thin.

## 8. Recommendation in one paragraph

Do not build "Lagos Life for all of Nigeria" — the incumbent is already expanding city by city with funding and millions of sign-ups. Build a **state-first economic simulation**: all 36 states and the FCT present from day one at light depth, each with a distinct economy, inter-state trade in goods players actually produce, local-language interfaces, and a client that works on low-end Android phones over poor data. Before any architecture work, run a one-week human-led pass to close the gaps this session could not (see `00` §7 and `11`).
