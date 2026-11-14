# 10 · Nigeria-Wide Product Blueprint

Working name: **Naija Life** (placeholder — note the competitor operates `naijalife.app`, so a different name is needed; check trademarks before choosing).

Everything in this document is a **proposal**. None of it describes Lagos Life.

## 1. Vision

A persistent, shared simulation of Nigerian economic and social life in which every state matters: players live, work, produce, trade, travel, organise and govern across 36 states and the FCT, on any phone, on any network.

**Positioning in one line:** the incumbent simulates city lifestyle; we simulate the national economy that connects the cities.

## 2. Design principles

1. **Phone and data first.** Target a first load under about 1 MB and usable play on a 2 GB-RAM Android phone over 3G. Set exact budgets after device testing.
2. **Geography is a mechanic.** Prices, jobs, goods and risks differ by place, so moving and trading are worth doing.
3. **Players make the economy.** Systems supply rules and scarcity; players supply goods, services and prices.
4. **Transparent rules.** Published formulas and odds; a public handbook.
5. **Respectful representation.** Every region shown with equal care; reviewed by people from that region; no ethnic or religious stereotyping.
6. **Fictional and safe.** Non-redeemable currency, fictional businesses and officials by default, strong moderation.

## 3. World structure

| Level | Count | Role in play | Launch depth |
| --- | --- | --- | --- |
| Federation | 1 | National market indices, federal offices, national events | Indices and events |
| Geopolitical zone | 6 | Climate, seasons, zone leagues | Seasonal modifiers |
| State + FCT | 37 | Signature economy, cost of living, governor, state leaderboard | All 37 as hubs |
| City / LGA | 774 LGAs in reality; begin with 1–3 playable hubs per state | Housing, markets, venues, council | About 50 hubs, expanding |
| Venue | Many | Activities, jobs, social spaces | 8–12 templated venue types per hub plus 1–2 landmarks |

**Templating keeps this feasible.** Each hub is assembled from shared venue types (market, motor park, clinic, school, bank, worship centre, council office, eatery, sports field, farm or workshop) with local names, prices and one or two unique landmarks. Unique content is added where players gather.

### Illustrative state economies (to be validated with regional research)

| Zone | Example signature activities |
| --- | --- |
| South West | Finance, tech, media, ports, cocoa, textiles and adire |
| South East | Trading hubs, manufacturing clusters, spare parts, footwear and garments |
| South South | Oil and gas services, fisheries, river transport, palm produce |
| North Central | Federal administration, yams and grains, solid minerals, tourism |
| North West | Leather, textiles, grains, livestock, cross-border trade |
| North East | Livestock, fishing, gum arabic, grains |

## 4. Modules

| # | Module | Core functions | Phase |
| --- | --- | --- | --- |
| 1 | Identity and safety | Sign-up with verified phone or email, age gate, profile, privacy controls, reporting, moderation | MVP |
| 2 | Character | Appearance, background choice, needs, skills, wellbeing | MVP |
| 3 | World and travel | State map, hubs, venues, road/air/rail/water routes with time and cost | MVP |
| 4 | Work | Sector careers, shifts or task-based work, gigs | MVP |
| 5 | Wallet and ledger | Double-entry currency, statements, transfers with limits | MVP |
| 6 | Housing | Rent ladder per hub, furnishing | MVP |
| 7 | Markets | Goods order books per hub, price history | V1.0 |
| 8 | Enterprise | Found a business: licence, premises, inputs, staff, pricing | V1.0 |
| 9 | Banking | Savings, credit score, loans, cooperative thrift, simple securities | V1.0 |
| 10 | Education | Vocational courses, tertiary institutions, national service posting | V1.0 |
| 11 | Social and associations | Friends, chat, groups, trade unions, cooperatives, town unions | V1.0 |
| 12 | Civic | State elections, budgets, policies; later LGA and federal | V1.0 → V2.0 |
| 13 | Events and seasons | Festivals, competitions, seasonal goals | V1.0 |
| 14 | Production | Farming, mining, manufacturing, crafts with regional inputs | V2.0 |
| 15 | Logistics | Haulage contracts, warehousing, route risk | V2.0 |
| 16 | Property development | Land by LGA, building, letting | V2.0 |
| 17 | Tourism and culture | Heritage sites, cuisine, festivals as activities and collections | V2.0 |
| 18 | Creator platform | Third-party mini-games and items | Advanced |

## 5. Economy design (starting points)

- **Currency:** one non-redeemable in-game unit. Decide on naming and symbol with counsel; the incumbent uses "Naira" and ₦ with extensive disclaimers.
- **Ledger:** every movement is a balanced double entry with an idempotency key.
- **Faucets:** wages, sales to system buyers at floor prices, event prizes.
- **Sinks:** rent, food, transport, licences, taxes, maintenance, spoilage, fees.
- **Balance target:** monitor money supply per active player daily; tune sinks before inflation shows in prices.
- **Regional prices:** each good has a production cost by state and a transport cost between states; arbitrage narrows gaps.
- **Anti-abuse:** transfer caps scaled by account age, velocity limits, device and behaviour signals, reversible settlements within a window, public economy dashboard.
- **No cash-out, no real-money trading.**

## 6. Nationwide engagement loops

- **Daily:** work or trade, meet needs, check market prices.
- **Weekly:** rent and tax day, market-day cycles that differ by town, state league table update.
- **Monthly/seasonal:** harvests, festivals, elections, national competitions.
- **Long term:** build an enterprise, climb office, complete a 37-state travel log.

## 7. Technical direction (to be confirmed in the architecture phase)

| Concern | Direction | Reason |
| --- | --- | --- |
| Client | Installable web app, 2D/2.5D, code-split by feature | Reach and data cost |
| Rendering | DOM/SVG/canvas first; optional richer scenes on capable devices | Low-end Android |
| Server authority | All outcomes and balances computed server-side | Integrity |
| Data | Relational database with a ledger schema; row-level access rules | Money correctness |
| Real time | Presence and chat by hub channel; turn/tick-based simulation rather than continuous movement | Scales and tolerates latency |
| Simulation | Scheduled ticks for wages, rent, markets, production | Predictable load |
| Moderation | Text filters plus human review queue from day one | Safety |
| Localisation | String catalogues from the first commit | Languages |
| Payments | Nigerian provider; bank transfer and USSD options | Local habits |
| Observability | Economy metrics, error and load reporting that respects privacy | Operations |

The repository owner has Supabase and Vercel available. A Postgres-backed stack with hosted auth and real-time channels on that pairing is a reasonable candidate for an MVP; whether it holds at high concurrency needs a load test before commitment.

## 8. Compliance checklist (for counsel, not legal advice)

- Nigeria Data Protection Act 2023, including children's data.
- Consumer protection for digital purchases and refunds.
- Use of currency names and symbols; any feature resembling stored value.
- Any chance-based mechanic or prize, at federal and state level.
- Use of real brand, institution, place and person names and insignia.
- Advertising standards for in-world ads.
- App-store rules for user-generated content and minors.

## 9. Expansion strategy

1. **Launch:** 37 state hubs, thin and templated, with travel and state leaderboards; deepest content in 4–6 hubs spread across all six zones (not only Lagos, Abuja and Port Harcourt).
2. **Deepen by demand:** add hubs and landmarks where population and trade concentrate.
3. **Community input:** state ambassadors and review panels for local content and language.
4. **Partnerships:** universities, state tourism bodies, SME associations.
5. **Beyond Nigeria:** only after the national economy is stable.
