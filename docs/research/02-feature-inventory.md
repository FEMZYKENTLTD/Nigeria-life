# 02 · Complete Feature Inventory

**Format note.** The brief asked for 14 fields per feature. To keep this usable, they are folded into five columns: *What it does and its rules* (description, purpose, actions, responses, inputs/outputs, business logic), *Access* (where it appears, how reached), *Depends on / related*, *Limits and unknowns* (limitations, UX caveats), *Evidence*.

**Evidence warning.** Rows tagged **S** come from unofficial guides or press and were not verified in the game. Numbers were "last checked" by those guides in early October 2026 and the game changes often. Rows tagged **C** were read on first-party pages on 14 Nov 2026.

---

## A. Accounts and identity

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Sign-up | Collects display name, username, password, optional email, date of birth, and a man/woman choice for the avatar | "Sign up free" on `/` (overlay, no own URL) | Age gate, Terms acceptance | Field validation not seen first-hand. Guides: username 3–20 letters/numbers/underscore, password 8+ | C (E06 §4), S (E22) |
| Age gate | DOB decides adult world (18+) or teen space (13–17); under 13 refused; DOB cannot be changed | Sign-up | Teen space | Teen space is "where it is open (on the website first)"; rollout status unknown. Early guides describe an 18+ tick box instead | C (E06 §2), S (E22) |
| Log-in | Username or email plus password. No social sign-in | "Log in" on `/` | Session cookie | In-app browsers (Instagram, X, WhatsApp) reportedly fail to keep the session | C (E07 §4), S (E22) |
| Session | Cookie-based on web, 60-day lifetime; secure storage token in the app | Automatic | Cookie banner | — | C (E07 §7, §11) |
| One device at a time | A generated device ID enforces one active device per account and flags takeovers | Automatic | Security alerts | No simultaneous phone + laptop play | C (E07 §3) |
| Password recovery | "Forgot password?" asks "owner questions" about the account; success lets the user set a new password and logs out other devices. Fallback: "Can't get in?" → "Ask the team" ticket | Login overlay | Support tickets | Guides say questions draw on play history (e.g. other players' usernames, approximate cash), so new accounts cannot use it | C (E12), S (E22) |
| Stolen-account flow | "Think someone else changed it? → Tell the team"; Settings → Security → "Someone stole my account"; option to lock an account | Login overlay, Settings | Security alerts with sign-in location | — | C (E12, E07 §14) |
| Account merge | A second account can pull in the first account's life by entering its password | Not seen | — | Secondary only | S (E22) |
| Profile | Username, display name, bio, avatar; visible to others | In game | Report, Block | Fields beyond these unknown | C (E06 §4, E09 §4) |
| Settings | Blocked players; "Who can message me"; notifications; marketing emails (off by default); Security; Account → Delete; Contact support; dark/light theme | Phone → Settings | — | Full list unknown | C (E07, E12, E17) |
| Account deletion | Password + second confirmation; logged out everywhere; 30-day undo by logging in; then erased; username reserved 90 days; ledger, votes and safety records kept de-identified | Phone → Settings → Account, or `/delete` when logged in | — | — | C (E13, E07 §12) |
| Notifications | Web push and app push for messages, "knocks", money received, governor announcements; in-app display when the game is focused; quiet hours | Settings / OS | Service worker, FCM | iPhone needs "Add to Home Screen" first | C (E04, E07), S (E22) |
| Streaks / daily visits | The operator records daily visits and streaks | Unknown | — | Whether streaks give rewards is unknown | C (E07 §3) |
| Achievements | — | — | — | **Not found in any source** | U |

## B. Character and life simulation

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Sim creator | Five steps: Look → Personality → Dream → Birth lottery → Home | After sign-up | — | — | S (E22) |
| Look | Body, hairstyle, outfit, fabric, skin tone | Creator | 3D character models | Option counts unknown | S (E22); C that 3D character models exist (E04: `/models/chars/…glb`) |
| Personality | Pick two traits | Creator | — | Trait list and effects unknown | S |
| Lifetime dream | One of five: reach top of any career; net worth ₦1,000,000; Music skill 10; four best friends; get a start-up funded | Creator | Careers, skills, friends | Reward for completing unknown | S (E22) |
| Birth lottery | Server decides "Nepo Baby" (₦500,000, furnished flat with rent paid, a car, a mid-level job, Charisma 2) or "LAPO Baby" (₦60,000 loan repaid as ₦72,000 at ₦12,000/week, Hustle 2, learns 25% faster). Once per account | Creator step 4 | Starting home, loan | Odds not published | S (E25) |
| Student start | LAPO players starting in Lagos may choose a university hall: ₦14,000 cash, no loan, ₦1,200/week bunk, ₦3,000 weekly allowance | Creator step 5 | University | Lagos only | S (E25) |
| Needs | Six: hunger, energy, hygiene, bladder, fun, social; low needs hurt mood and work | Sim panel | Food, sleep, venues | Decay rates not captured | S (E22) |
| Mood / moodlets | Timed mood modifiers (e.g. "Lost Luggage": −12 mood for 4 hours) | — | Travel, events | — | S (E26) |
| Sickness | Mild illness treated with chemist drugs (₦1,500) or herbal mix; severe needs hospital injection | Hospital, chemist | Needs | — | S (E22, E24) |
| Skills | Nine reported: Charisma, Coding, Comedy, Cooking, Fitness, Hustle, Music, Photography, Dance; levels to 10 | Sim panel | Jobs, gigs | XP curve unknown | S (E22–E24) |
| Game clock | In-game hours, days and a Monday–Sunday week drive shifts, rent, tax and elections | — | Everything | Real-time length of an in-game day unconfirmed even by the guide | S (E24) |
| Random events | Fuel scarcity (+50% fares), power cuts, business "bad days" | — | Economy | — | S (E22, E24) |
| "Start a new life" | Replaces money, home, items and progress; lottery result stays | Settings | — | — | S (E25) |
| Mental-health venue | "MindSpace" appears on the map | Map | — | Function unknown | C (label only, E01) |

## C. Economy and finance

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Game Naira | Fictional unit shown with ₦. Can be earned, spent, transferred, gifted, lost, taxed, invested. Never withdrawable or redeemable; no exchange rate | Everywhere | — | — | C (E06 §6) |
| Real-money top-up | Adults may buy Game Naira; Flutterwave processes payment | In game | Flutterwave | Current bundle prices not seen; press reports ₦500–₦20,000 bundles | C (E06 §7), S (E27) |
| Rent | Deducted every Saturday morning; arrears become debt; more than two weeks owed leads to eviction to the cheapest area | Automatic | Homes | — | S (E22, E24) |
| Starting loan | ₦72,000 owed, ₦12,000 weekly; missed payment adds 10% of that instalment; early repayment allowed | Automatic | Birth lottery | — | S (E24) |
| Income tax | First ₦1,000,000 of weekly earnings exempt; then 20%; 40% above ₦10m; 45% above ₦50m; resets Monday; not applied to sales or gifts | Automatic on pay | Wages | — | S (E24); C that "virtual taxes" exist (E06 §8) |
| Player transfers | Chat → "Send money"; minimum ₦100; fee 5% rounded up to ₦50 (minimum ₦50) paid by sender | Chat | Friends, moderation | Automated checks may hold transfers or limit sending; off for teens | S (E24), C (E07 §16, E10) |
| Transaction ledger | The operator keeps ledgers used for refunds, reversals and audits | Back end | — | Whether players see a history screen is unknown | C (E06 §12, E07 §14) |
| Investments | Shares, real estate, banks/fintech, crypto, insurance and loans are named as simulated systems | — | — | Rules unknown except land and business shares below | C (E08 §12) |
| Insurance | Insured travel reimburses losses | Travel | Intercity travel | Premiums unknown | S (E26); C that insurance exists (E06 §8) |
| Betting ("LagosBet"), casino, "money tables" | Game-Naira-only wagering; adults only | Phone / casino venue | — | Odds and games unknown | C (E06 §3) |
| "Spraying" money | Cultural mechanic of showering virtual cash at celebrations | Venues | — | — | C (E08 §11) |
| Economy governance | Operator may change prices, wages, tax, probabilities, limits; may reverse ill-gotten balances | — | — | — | C (E06 §8) |

## D. Employment and careers

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Job application | Pick a career on the phone and tap "Apply — start tomorrow" | Phone | Skills | Some careers need a skill level to apply | S (E22) |
| Career ladder | 33 careers × 5 levels. Standard careers promote at skill 1/3/5/7 plus 100% performance | Phone | Skills | Another fan site says 23 careers | S (E23, E28) |
| Shifts | Fixed days and hours per career, at a named workplace; a "Go to work" button appears on work days; lateness lowers performance; leaving early cuts pay | Venue | Transport, needs | — | S (E22, E24) |
| Work modes | Steady; "Work Like Jaguda" (more performance, drains energy/fun); gist with colleagues; flatter the boss; "Take Am Easy" | During shift | Needs | — | S (E24) |
| Shift tasks | Win 4 tasks in a shift for +15% pay | During shift | — | Task design unknown | S (E24) |
| Degree premium | Graduates earn up to 25% more per shift | University | — | — | S (E24) |
| Gigs | 15 listed side jobs with pay formulas tied to skill level, a duration and a cooldown (20 or 45 in-game minutes) | Venues, home, phone | Skills, owned items | — | S (E24) |
| City-specific careers | Abuja and Port Harcourt have their own careers (e.g. civil service, oil and gas, ferry work) | Per city | Travel | — | S (E24, E26) |

Sample pay per shift (S, E23, E24): Tech ₦9,900 → ₦76,500; Banking ₦11,600 → ₦72,000; Music ₦7,400 → ₦99,000; Trading ₦8,300 → ₦63,000; Nursing ₦9,100 → ₦75,000; Chef ₦7,400 → ₦70,500. Career names seen: Tech, Banking, Music, Trading, Nursing, Hairstyling, Chef, DJ, Broadcasting, Real Estate, Medicine, Product Management, Oil & Gas, Aviation, Civil Service (Lagos), Civil Service (Abuja), Refining, Airport Staff, Wuse Market Trading, Creek Road Trading, Law, Fitness Coach, Retail, Keke Riding, Mai Shayi, Ferry Work, Bole & Fish, Security, Teaching, Content Creator, Event Planning, Football, Lounge Waiting.

## E. Business and entrepreneurship

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Buy a business | Eight fixed businesses from ₦150,000 (recharge kiosk) to ₦250,000,000 (a 5% nightclub share). Each pays a random daily income minus fixed running cost at 6 PM; 8–10% chance of a loss-making "bad day"; resale returns 60% | "Own a business" | Game Naira | Passive only: no staff, stock, pricing or customers reported. Offline payouts capped at 7 in-game days | S (E24) |
| Haulage trailer | ₦18,000,000; ₦87,000–₦179,000 net per day after a ₦30,000 driver; 8% breakdown (₦95,000); maximum three | — | — | — | S (E24) |
| Start-up pitch | Once a day with Coding 5 and Charisma 3, a chance at ₦100,000–₦1,000,000 funding | Tech hub venue | Skills | Odds unknown | S (E24) |
| Business texts | Players write business names and texts, which are moderated | — | Moderation | Suggests some player-named businesses; detail unknown | C (E07 §3, E09 §4) |
| Business rankings, employees, P&L | — | — | — | **Not found in any source** | U |

## F. Marketplace, property and assets

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Rented homes | A ladder per city from about ₦2,400 to ₦1,500,000 per week; each home has a size and guest capacity | Creator, later moves | Rent | Landing page chip says "400 homes"; meaning unverified | S (E24–E26), C (E01) |
| Furnishing ("Buy mode") | Catalogue, place, move, rotate, sell furniture; some items need electricity | At home | Power cuts, gigs that need items | — | S (E22); C that furniture models exist (E04) |
| Land | Six plots, ₦250,000–₦150,000,000; value compounds 1.9–5% per week; 5% selling fee; 0–40% chance of a 10% "omo-onile" charge on purchase | — | — | Only Lagos plots documented | S (E24) |
| Vehicles | Cars are owned (a starter car for Nepo players; a car dealer venue on the map); own car means fuel-only travel | Dealer venue | Transport | Prices unknown | S (E25), C (E01, E13) |
| Sea Plots | 6×6 plots on the lagoon sold for real money as ad space, 7 days | `/advertise` | Flutterwave | Whether players can hold sea plots with Game Naira is unknown | C (E15) |
| Player-to-player item trading | — | — | — | **Not found.** Only money transfers and gifts are evidenced | U |
| Partner stores | Real merchants sell through the game; a delivery address may be collected | In game | Flutterwave | Catalogue unknown | C (E07 §3, §9) |
| "Hustle" board | A public posting surface named alongside the feed | In game | Moderation | Purpose (jobs? listings?) unknown | C (E09, E12) |

## G. Social and multiplayer

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Shared world presence | Players see who is at a venue; location in the game world is shared | Venues, "People here" | — | — | S (E22), C (E07) |
| Venue/public chat, DMs, groups | Text chat with reactions and stickers; DMs stored server-side, not end-to-end encrypted | Chat | Moderation | No photos anywhere in the game | C (E06 §17, E07 §3) |
| Voice notes | Sent in chats; deleted after 90 days | Chat | Microphone consent | — | C (E07 §11) |
| Live voice rooms ("Spaces") and 1:1 voice | Live audio, never recorded; speech is transcribed in memory for an automated safety check; adults only | Venues, homes | Cloudflare, OpenAI | — | C (E07 §3, §9) |
| "Lagos Gist" | Public posts and comments; auto-moderated | Phone | Moderation | — | C (E07, E09) |
| Relationships | Friends in two tiers ("Padi", "Paddy Mi"), family, partners, followers; dating, engagement, marriage, babies, break-ups | Social | — | Mechanics unverified | C (graph types, E07 §3), S (E22) |
| Knocks, invites, gifts, rides | Visiting homes, inviting, gifting, shared rides, private game-table invites | Social | — | — | C (E10) |
| Club music | Players add songs in clubs; song titles are moderated | Club venues | — | Link to "music promotion" revenue is press-reported | C (E07 §3), S (E27) |
| Report / block / message controls | Report on profile, chat line or post (also blocks); block; friends-only messaging | Everywhere | Moderation team | — | C (E09, E12) |
| Leaderboards | Per community game: top 50 and own rank | Games app | SDK | A world-wide wealth or rank board was not evidenced; the Terms mention "ranking" | C (E17, E06 §25) |

## H. Entertainment and activities

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Venue activities | About 300 activities in Lagos and about 350 in Abuja, each with time, cost and skill effect | "Things to do" at a venue | Needs, skills | Counts vary by source | S (E22, E26, E28) |
| Daily gem hunt | A daily clue leads to a hidden gem with a cash prize | Map | — | Prize size unknown | S (E22) |
| Community games | Third-party HTML5 games framed inside a "Games" app; items ₦100–₦50,000 in real money; score boards | Phone → Games | SDK | Catalogue size unknown | C (E17) |
| Staked matches | 2–4 players stake Game Naira; winner takes the pot less a 5% house cut; caps of ₦100,000 per match and ₦500,000 per player per day | Inside community games | SDK | Requires separate approval per game | C (E17) |
| Football highlights | Embedded highlights from a third-party provider (ScoreBat) | Viewing centre (I) | — | — | C (E07 §7) |
| Events, quests, missions | — | — | — | Beyond the gem hunt and the lifetime dream, **not found** | U |

## I. Civic, legal and crime

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| Governor election | Weekly vote at a polling unit; ₦50,000 to run; most votes by Sunday 8 PM wins; ₦25,000 daily allowance; winner picks one city-wide policy | Polling venue | — | Whether each city has its own governor is unknown | S (E22, E24); C that elections exist (E06 §3, E01) |
| Policies | Examples: minimum-wage raise (+15% pay), transport subsidy (half fares on buses and tricycles), food subsidy (−30%) | Governor | Economy | — | S (E22, E24) |
| Commissioners | Reported appointed roles | — | — | Unverified | S (E27) |
| Live Court | Court sessions with an AI judge; voice notes in court are transcribed | Court venue | OpenAI | Rules unknown | C (E07 §9) |
| Crime and police | Crime actions can lead to a cell; wait or pay; fines and bail | Police venue | — | Adults only | C (E06 §3), S (E24) |

## J. Geography and travel

| Feature | What it does and its rules | Access | Depends on / related | Limits and unknowns | Evidence |
| --- | --- | --- | --- | --- | --- |
| City map | Named venues with opening hours; 36 labels on the landing map for Lagos | Map | — | — | C (E01), S (E22) |
| Three cities | Lagos, Abuja (69 places reported), Port Harcourt | Start-city choice or travel | — | Start city is pre-selected from the player's approximate real location | S (E25, E26), C (E07 §3 on location use) |
| Local transport | Walk (free), tricycle and bus (₦100 + ₦5/km), motorbike (₦150 + ₦8/km), cab (₦300 + ₦15/km), own car (fuel) | Map | — | — | S (E22) |
| Flights | Base fares ₦120,000–₦150,000 between cities; four cabins (×1, ×1.8, ×4, ×9); lost-bag chance 14% → 6%; about 1.2 in-game hours | Airport | Insurance | — | S (E26) |
| Intercity bus / self-drive | Cheaper and slower with risks: lost luggage 12%, pickpocket 8%, accident 3%; self-drive breakdown 10%, flat tyre 8%, checkpoint 6% | Bus park | Insurance | — | S (E26) |
| Boat cruise, helipad, private jets | Leisure and luxury travel options | Venues | — | — | C (label, E01), S (E26) |
| "Coming soon" | Stadium, refinery and an "OBO" label marked as upcoming on the landing map | Map | — | Landing labels may be out of date | C (E01) |

## K. Safety and support

| Feature | What it does and its rules | Evidence |
| --- | --- | --- |
| Automated moderation | Public text, chats, names and pictures checked automatically; violating content removed or not sent with a reason shown | C (E09) |
| Strike ladder | Three violations in a day → mute for 2 h, then 12 h, then 24 h; six take-downs triggers staff review | C (E09) |
| Teen space | Separate database and servers; contact-only chat; no off-platform handles; no notifications 10 pm–7 am; break nudges at 45 and 60 minutes; optional guardian consent step | C (E10, E11, E07 §13) |
| In-game support | Phone → Support → "Contact support" or "Chat with support"; replies arrive as in-game chat | C (E12) |
| AI helper | An in-game assistant answered by an AI provider; adults only | C (E07 §9) |
| Public report form | `/report`, no login; returns a reference that can be checked later | C (E14) |
| Anti-abuse | Device fingerprinting, bot checks, transfer holds | C (E06 §20, E07) |

## L. Commercial and developer features

| Feature | What it does and its rules | Evidence |
| --- | --- | --- |
| Self-serve advertising | Choose billboards / sea plots / airport boards, upload an image, enter business details, pay; live on payment; per-ad view and tap totals | C (E15, E07 §8) |
| Developer platform | Keys, sandbox with test money, dashboard checklist, review, monthly payouts | C (E17, E18) |
