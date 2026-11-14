# 04 · User Journey Documentation

Journeys J1, J7, J8 and J9 are built from first-party pages (C). The others depend on secondary sources (S) and are marked. None was performed by us.

## J1 · New visitor arrives (C)

- **Start:** `https://lagoslife.app/`
- **Sees:** city map, live counters, cookie banner, "Sign up free" / "Log in".
- **Branches:** accept or limit cookies; sign up; log in; leave via a social link.
- **Failure states:** slow connection ("Slow network… still loading"); no connection (offline screen with auto-retry); unknown URL (Pidgin 404).

```mermaid
flowchart TD
  A[Open lagoslife.app] --> B{Network?}
  B -- none --> O[Offline screen, retries every few seconds]
  B -- slow --> S[Slow network notice] --> C
  B -- ok --> C[Landing map + counters]
  C --> D{Cookie banner}
  D --> C
  C --> E[Sign up free]
  C --> F[Log in]
  C --> G[Official social links]
```

## J2 · Registration and Sim creation (S; fields C)

```mermaid
flowchart TD
  A[Sign up overlay] --> B[Name, username, password, optional email, date of birth, avatar sex]
  B --> C{Age}
  C -- under 13 --> X[Refused]
  C -- 13 to 17 --> T{Teen space open?}
  T -- no --> X
  T -- yes --> TS[Teen world]
  C -- 18+ --> D[Look]
  D --> E[Two personality traits]
  E --> F[Lifetime dream]
  F --> G[Birth lottery, decided by server]
  G -- Nepo --> H1[Cash, furnished flat, car, job]
  G -- LAPO --> H2[Loan + choose cheap home or student hall]
  G -- lottery unreachable --> H3[Starts 'self-made']
  H1 --> I[City and home confirmed]
  H2 --> I
  H3 --> I
  I --> J[Enter the world]
```

- **Inputs:** identity fields; appearance; two traits; one dream; start city (pre-selected from approximate location); home.
- **Success:** the Sim wakes at home.
- **Dependencies:** cookies must persist (in-app browsers reportedly fail).

## J3 · Returning user logs in (S; recovery C)

```mermaid
flowchart TD
  A[Log in overlay] --> B[Username or email + password]
  B --> C{Correct?}
  C -- yes --> D{Another device active?}
  D -- yes --> D2[One-device rule applies - which device yields is unknown]
  D2 --> E[Game resumes; missed business payouts settled]
  D -- no --> E
  C -- no --> F[Forgot password?]
  F --> G[Owner questions]
  G -- pass --> H[Set new password; other devices logged out]
  G -- fail --> I["Can't get in? then Ask the team, ticket issued"]
  C -- no --> K["Think someone else changed it? then Tell the team"]
```

## J4 · Earning virtual currency through a job (S)

1. Phone → pick a career → "Apply — start tomorrow".
2. On a work day, tap "Go to work"; choose transport; arrive before the start time.
3. Choose a work mode; complete tasks (4 wins = +15%).
4. Stay to the end; pay is credited, with tax taken automatically above the weekly threshold.
5. Train the career's skill; at 100% performance and the required skill level, promotion follows.

- **Failure states:** late arrival (performance drop); leaving early (reduced pay); low needs (poor work); venue closed.

## J5 · Buying something with Game Naira (S)

- **Furniture:** at home → Buy mode → catalogue → place → confirm. Selling is available.
- **Business:** "Own a business" → pick → pay → daily 6 PM settlement.
- **Land:** buy a plot → possible "omo-onile" charge → hold → sell with 5% fee.

## J6 · Buying Game Naira with real money (C that it exists; screens not seen)

```mermaid
flowchart TD
  A[Adult player opens top-up] --> B[Chooses bundle]
  B --> C[Flutterwave checkout]
  C --> D{Provider confirms paid?}
  D -- yes --> E[Game Naira credited; ledger entry]
  D -- no --> F[No credit]
  E --> G{Chargeback later?}
  G -- yes --> H[Credit reversed; account may be suspended]
  D -- paid but not credited --> R[Refund considered against provider record + game ledger]
```

## J7 · Advertiser books a billboard (C)

```mermaid
flowchart TD
  A["/advertise page"] --> B[Pick billboards, sea plots, airport boards]
  B --> C[Upload logo or ad image]
  C --> D[Business name, link, email, optional phone]
  D --> E[Total shown in NGN or USD]
  E --> F[Pay via Flutterwave]
  F --> G{Publish now or later}
  G -- now --> H[Ad live, rotating 15 s on least-crowded boards]
  G -- later --> I[Publish when ready]
  H --> J{Breaks ad rules?}
  J -- yes --> K[Removed, no refund]
```

## J8 · Developer ships a community game (C)

```mermaid
flowchart TD
  A[Sign in to the game] --> B["/developers/keys form: studio, email, game name, HTTPS URL, webhook, description"]
  B --> C[Test secret + webhook secret, shown once]
  C --> D[Add products in dashboard]
  D --> E[Play in sandbox: test purchases, scores, matches]
  E --> F{Integration checklist complete?}
  F -- no --> E
  F -- yes --> G[Add icon, 3-5 screenshots, descriptions; accept agreement]
  G --> H[Review]
  H -- approved --> I[Live secret; listed in Games app]
  H -- changes or rejected --> E
  I --> J[Sales split 70/30; payout by the 15th if at least N5,000]
```

In-game purchase inside a community game: game calls `purchase(productId)` → the host shows its own pay sheet → player pays → host verifies with the payment provider → game is told → developer's server checks the purchase → delivers → marks delivered.

## J9 · Reporting, moderation and appeal (C)

```mermaid
flowchart TD
  A[Player sees a problem] --> B[Tap Report on profile, chat line or post]
  B --> C[Reported player is also blocked]
  C --> D[Team reviews: warn, mute, restrict, rename, suspend, close]
  E[Automatic check removes a post or stops a message] --> F{3 in a day?}
  F -- yes --> G[Mute 2 h, then 12 h, then 24 h]
  G --> H[Appeal via in-game support or /report]
  H --> I[Human review; restore if wrong]
```

## J10 · Travelling to another city (S)

Go to the airport (open 24 hours) → check-in desk → "Book a Flight" → choose cabin → optional insurance → fly → land at the destination airport. Alternative: intercity bus from the bus park, or self-drive. The home does not move; rent continues in the origin city.

## J11 · Running for governor (S)

Pay the campaign fee → write campaign text → players vote at the polling unit during the week → count at Sunday 8 PM → winner receives a daily allowance for a week and selects one policy that changes prices or pay for everyone.

## J12 · Deleting an account (C)

Phone → Settings → Account → Delete account → password → second confirmation → logged out everywhere → 30 days to undo by logging in → erased → username held 90 days.

## Journeys we could not reconstruct

Profile viewing and editing; settings screens in full; messaging UI; dating and marriage flows; betting and casino; the court; crime; partner-store checkout; university enrolment and exams.
