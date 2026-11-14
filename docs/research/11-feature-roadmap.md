# 11 · Prioritised Feature Roadmap, Open Questions and Next Phase

Proposals only. No timelines are given because team size and budget are unknown.

## 1. Roadmap

### MVP — prove reach and the core loop

- Sign-up and log-in with verified phone or email; age gate; standard recovery.
- Character creation with a chosen background (transparent trade-offs).
- Needs, a small skill set, wellbeing.
- National map with all 37 state hubs; basic travel by road and air with time and cost.
- Templated venues per hub; 4–6 deeper hubs across the six zones.
- A core set of sector careers and gigs tied to state economies.
- Wallet on a double-entry ledger; statements; capped transfers.
- Rent ladder and simple furnishing.
- Text chat by venue and direct message; report, block, automated filtering, human review queue.
- State leaderboards.
- English and Pidgin interface; string catalogues ready for more languages.
- Light installable web client with offline shell.
- Public handbook and SEO-friendly web pages (with robots.txt and sitemap).
- Economy telemetry and admin controls.

### Version 1.0 — make geography and enterprise matter

- Goods markets per hub with price differences between states.
- Player-founded businesses (licence, premises, inputs, staff, pricing).
- Banking: savings, credit score, loans, cooperative thrift.
- Education: vocational courses, institutions across zones, national service posting.
- State governor elections with budgets and policies.
- Associations: cooperatives, unions, town unions.
- Events calendar, achievements, seasonal goals.
- Hausa, Yoruba and Igbo interfaces.
- Travel risk and insurance; rail and water routes.
- Multi-device hand-off; queued offline actions.
- First monetisation: cosmetics, pass, regional in-world ads.

### Version 2.0 — a producing economy

- Farming, mining, manufacturing and crafts with regional inputs.
- Logistics contracts and warehousing.
- Land and building by LGA; letting.
- LGA and federal offices; state and federal levies funding public works.
- Contract disputes and arbitration.
- Tourism and culture collections.
- Voice rooms with safety checks.
- More hubs per state.

### Advanced ecosystem

- Creator platform for mini-games and items with revenue share.
- Merchant storefronts for real SMEs.
- Sponsored education modules (financial literacy, vocational).
- Public data API for economy statistics.
- Native app wrappers.

### Future innovations (speculative)

- Teen world with separate infrastructure.
- Additional local languages and voice interfaces.
- Low-bandwidth access channels (for example USSD or messaging-bot companions for market prices and alerts).
- Diaspora and cross-border trade.
- Classroom editions.

## 2. Unresolved questions

### About Lagos Life

1. What do the sign-up, creator, phone, map, shift and top-up screens actually look like and how do they behave? (Not seen.)
2. Is the teen space open? Is there an official native app today?
3. Current top-up bundles and prices.
4. Are governors, prices and markets per city or global?
5. Is there any player-to-player goods trading or item inventory?
6. What is the "IPO offer"?
7. What does `/stats` show, and why did it return the landing page to our reader?
8. Real-time protocol, database engine, security headers, bundle size and load time.
9. Real length of an in-game day; skill XP curves; need decay rates.
10. Which of the conflicting counts (careers, places) is current?

### About our product

1. Team, budget and target launch window.
2. Product name and trademark clearance.
3. Monetisation stance on currency sales and any chance-based play.
4. Whether minors are admitted at launch.
5. Minimum device and network targets, set from real device testing.
6. Which 4–6 hubs get depth first.

## 3. Recommendation for the next engineering phase

**Step 1 — Close the research gaps (about one week, human-led).**
An adult team member plays the game on their own account for several in-game weeks and records screens and behaviours against the checklist in `05` §9 and `00` §7. Capture response headers and load metrics with ordinary browser tools on public pages. Do not automate, scrape, or register for developer keys.

**Step 2 — Decisions before design.**
Legal review of the checklist in `10` §8; choose name; fix the monetisation stance; set device and data budgets.

**Step 3 — Architecture and economy specification.**
Produce: the ledger and core schema; the simulation tick design; the state-economy data model (goods, production costs, transport costs for 37 states); the real-time channel design; a load-test plan for the chosen stack; a moderation design.

**Step 4 — A thin vertical slice, tested on real low-end phones.**
One account → one character → two states → one job → one trade between the two states → one ledger statement. Measure first-load size, time to interactive on 3G, and memory on a 2 GB device. Proceed to the MVP build only if the budgets hold.

**Step 5 — Economy simulation before launch.**
Model faucets and sinks offline with synthetic players to find inflation and exploit paths before real players do.
