# Cornflower Health — Notion Dashboard Design Spec

> **Purpose:** Define the Notion dashboard pages, views, and layout for daily health data interaction. Everything in this spec maps to concrete Notion API block types and Views API calls.
>
> **Design philosophy:** Bevel-style progressive disclosure — lead with recovery zone, show today's metrics at a glance, hide detail behind toggles. Mobile-first single-column layout. Hybrid data strategy: scripted content for read-only sections, linked database views for interactive sections.

---

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Bevel-style progressive disclosure | Notion pages scroll vertically; summary → toggle-detail mirrors tap-to-expand UX |
| D2 | 4-color recovery zone system | 🟢 GREEN (75–100), 🟡 YELLOW (50–74), 🟠 ORANGE (25–49), 🔴 RED (0–24) — per coaching-layer.md |
| D3 | "vs. baseline" always shown next to raw values | Today + 7d avg + 60d baseline inline, with trend arrow (↑↓→) |
| D4 | One Notion page per dashboard screen | Daily, Trends, Flags, Full Table, Settings — linked from parent page |
| D5 | API-first build: spec → deploy script → one-shot push | No iterative Notion pushes; single deployment when approved |
| D6 | Hybrid data strategy | Scripted daily refresh for read-only sections; linked DB views for manual entry |
| D7 | Mobile-first single-column layout | User primarily views on phone; no side-by-side columns that break on mobile |
| D8 | Exertion/stress/energy elevated; booster demoted | Exertion block is 2nd section; booster is collapsed toggle near bottom |
| D9 | Recovery breakdown shows scoring components | Not just the score — show HRV component, RHR component, each modifier |
| D10 | Trend windows: 5 / 10 / 20 / 40 days | User preference; tabs for each window |
| D11 | Buttons configured manually after API push | Only UI-only element needed; small documented list of manual steps |

---

## API vs. UI Capability Map

### Pushable via Notion API (one-shot deploy)
- Page creation under parent (`POST /v1/pages`)
- All content blocks: headings, callouts (with background color + emoji icon), dividers, toggles, paragraphs, tables, tabs (`POST /v1/blocks/{id}/children`)
- Column layouts (`column_list` + `column` with `width_ratio`) — though we avoid these for mobile-first
- Linked database views with filters, sorts, visible properties (`POST /v1/views` with `create_database`)
- Chart views: line, bar, donut, KPI number (`POST /v1/views` with `type: "chart"`)
- Tab blocks (for trend time windows)
- Synced blocks (for duplicating button containers across pages)
- Rich text with color: `{"color": "green"}` for inline text, `green_background` for callout backgrounds

### Available callout/text colors (API `color` field)
`default`, `gray`, `brown`, `orange`, `yellow`, `green`, `blue`, `purple`, `pink`, `red`
Background variants: `gray_background`, `orange_background`, `yellow_background`, `green_background`, `blue_background`, `purple_background`, `pink_background`, `red_background`

### Requires manual UI configuration (after push)
- **Buttons** — "Log Today's Entry" button (action: add page to DB with date=today)
- **"Show as Bar/Ring"** on number properties (display format is UI-only)
- **Conditional row colors** on table views
- **Chart color palette** fine-tuning (accent colors on bar/line charts)

---

## Page Architecture

```
🏠 Cornflower Health (parent page — ID: 339d7cd8-531f-800b-b02d-efefaa086bf5)
 ├── 📊 Daily Dashboard        ← Morning check-in (PRIMARY)
 ├── 📈 Trends                 ← 5 / 10 / 20 / 40-day chart views
 ├── 🚩 Flags & Alerts         ← Filtered view of flagged days
 ├── 📋 Full Data Table        ← Complete database in table view
 └── ⚙️ Settings & Reference   ← Baselines, thresholds, protocol
```

---

## Page 1: Daily Dashboard

Primary interface. Single-column, mobile-first. Answers: "How am I doing today and what should I do?"

**Data strategy:** Sections marked [SCRIPTED] are written by `src/update_dashboard.py` once daily after morning data arrives. Sections marked [LINKED VIEW] are live database views the user interacts with.

### Section 1 — Recovery Zone [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  CALLOUT (background colored by zone)       │
│  Icon: zone emoji (🟢/🟡/🟠/🔴)            │
│  Text: "GREEN — 82/100"                     │
│  Subtext: "HRV 9% above baseline, RHR in   │
│  range. Full training cleared."             │
│                                             │
│  Color mapping:                             │
│    GREEN  → green_background                │
│    YELLOW → yellow_background               │
│    ORANGE → orange_background               │
│    RED    → red_background                  │
└─────────────────────────────────────────────┘
```

**Block type:** `callout` with `icon.emoji`, `rich_text`, `color`
**API-creatable:** Yes

### Section 2 — Recovery Breakdown [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  CALLOUT (gray_background, neutral)         │
│  📊 Recovery Breakdown                      │
│                                             │
│  HRV component:       54 / 60              │
│  RHR component:       28 / 40              │
│  ─────────────────────────────              │
│  Base score:          82 / 100             │
│                                             │
│  Deep sleep (52 min): +0  (neutral)        │
│  SpO2 avg (95%):      +0  (normal)         │
│  Resp rate (14.2):    +2  (low arousal)    │
│  Sleep quality:       +0                    │
│  Stress context:      +0  (not entered)    │
│  ─────────────────────────────              │
│  Final score:         84 / 100             │
│                                             │
│  Hard gates: None active                    │
└─────────────────────────────────────────────┘
```

**Block type:** `callout` (gray_background) with formatted `rich_text`
**API-creatable:** Yes

### Section 3 — Exertion / Stress / Energy [SCRIPTED + LINKED VIEW]

```
┌─────────────────────────────────────────────┐
│  HEADING 2: Exertion & Stress               │
│  DIVIDER                                    │
│                                             │
│  [SCRIPTED paragraph block]                 │
│  Exertion rec: "Zone 2 cleared, cap 60min"  │
│  Yesterday load: Rest day / [workout summary]│
│                                             │
│  [LINKED VIEW — today's row, gallery card]  │
│  Editable fields: energy_1_5, stress_context,│
│  fatigue_level, morning_heaviness,           │
│  afternoon_crash                             │
└─────────────────────────────────────────────┘
```

**Block types:** `heading_2`, `divider`, `paragraph` (scripted), linked DB view (Views API)
**API-creatable:** Yes (all parts)

### Section 4 — Key Metrics [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  HEADING 2: Key Metrics                     │
│  DIVIDER                                    │
│                                             │
│  HRV:  58.1 ms  (7d: 55.2 | 60d: 53.2) ↑  │
│  RHR:  63 bpm   (7d: 64.1 | 60d: 64.8) ↓  │
│  SpO2: 95%  ✅                              │
│  Resp: 14.2 brpm  ✅                        │
│  Temp: 99.1°F                               │
│  HR dip: 14.2% (Normal dipper)              │
└─────────────────────────────────────────────┘
```

Format: each metric on its own line. Today's value bold, baselines in parentheses, trend arrow at end. Green ✅ if in normal range; yellow ⚠️ if borderline; red 🔴 if flagged.

**Block type:** `paragraph` blocks with colored `rich_text`
**API-creatable:** Yes

### Section 5 — Sleep [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  HEADING 2: Sleep                           │
│  DIVIDER                                    │
│                                             │
│  Total: 7h 12m  |  Efficiency: 91%         │
│  Deep: 52 min ✅  |  REM: 1h 22m           │
│  Core: 3h 08m    |  Awake: 18 min          │
│  Bed: 11:15 PM → Wake: 6:27 AM             │
│  In bed: 7h 52m                             │
└─────────────────────────────────────────────┘
```

**Block type:** `paragraph` blocks with `rich_text`
**API-creatable:** Yes

### Section 6 — Active Flags [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  ▶ TOGGLE: Flags (1 active)                 │
│    🟡 Deep sleep gate: 52 min (< 50 target) │
│    (No other flags today)                   │
│                                             │
│    If no flags: "✅ No flags active today"  │
└─────────────────────────────────────────────┘
```

**Block type:** `toggle` with `paragraph` children
**API-creatable:** Yes

### Section 7 — Booster Protocol [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  ▶ TOGGLE: Booster Protocol (collapsed)     │
│    Decision: 🟢 Green light — both doses    │
│    HRV ≥48 ✅ | Deep ≥50 ✅ | RHR ≤66 ✅   │
│    Protocol: Vyvanse 60mg + Dex 5mg @10am   │
│    + 5mg @1pm                               │
└─────────────────────────────────────────────┘
```

**Block type:** `toggle` with `paragraph` children (collapsed by default)
**API-creatable:** Yes

### Section 8 — Rolling Averages [SCRIPTED]

```
┌─────────────────────────────────────────────┐
│  ▶ TOGGLE: Rolling Averages                 │
│    HRV  — 7d: 55.2 ms  |  60d: 53.2 ms     │
│    RHR  — 7d: 64.1 bpm |  60d: 64.8 bpm    │
│    Deep — 7d: 48.3 min                      │
│    HR dip — 7d: 12.4%                       │
└─────────────────────────────────────────────┘
```

**Block type:** `toggle` with `paragraph` children
**API-creatable:** Yes

### Section 9 — Manual Notes [LINKED VIEW]

```
┌─────────────────────────────────────────────┐
│  HEADING 2: Notes & Log                     │
│  DIVIDER                                    │
│  [LINKED DB VIEW — filtered to today]       │
│  Visible fields: meds_notes, notes          │
│  [BUTTON: "Log Today's Entry"] ← UI-only   │
└─────────────────────────────────────────────┘
```

**Block types:** `heading_2`, `divider`, linked DB view (Views API)
**Button:** Manual UI config after push

### Section 10 — Workout Log [LINKED VIEW]

```
┌─────────────────────────────────────────────┐
│  ▶ TOGGLE: Workout Log                      │
│  [LINKED DB VIEW — filtered to today]       │
│  Visible: workout_type, workout_total_min,  │
│  workout_exertion_felt, workout_z2/z3/z4,   │
│  workout_summary, workout_rest_day          │
└─────────────────────────────────────────────┘
```

**Block types:** `toggle` containing linked DB view
**API-creatable:** Yes (the toggle and the view)

---

## Page 2: Trends

Answers: "How have my metrics been trending?"

### Layout

```
┌─────────────────────────────────────────────┐
│  TAB BLOCK: [5 Days] [10 Days] [20 Days] [40 Days] │
└─────────────────────────────────────────────┘

Within each tab:

  CHART: HRV Trend (line)
  x: date, y: hrv_sdnn_ms

  CHART: RHR Trend (line)
  x: date, y: rhr_bpm

  CHART: Deep Sleep (bar)
  x: date, y: sleep_deep_min

  CHART: Total Sleep (bar)
  x: date, y: sleep_time_asleep_min

  CHART: SpO2 (line)
  x: date, y: spo2_avg_pct

  CHART: Resp Rate (line)
  x: date, y: resp_rate_brpm

  LINKED DB VIEW: Recent days table
  Sorted date desc, visible: date, recovery_score,
  hrv_sdnn_ms, rhr_bpm, sleep_deep_min,
  sleep_time_asleep_min, spo2_avg_pct, source_tags
```

**Implementation:**
- Tab block with 4 tabs: ✅ API-creatable
- Charts within each tab: ✅ API-creatable via Views API (`type: "chart"`, with date filter per window)
- Each tab's charts filter by `date on_or_after` computed dynamically (today minus 5/10/20/40 days)
- Charts auto-refresh as new data arrives — no daily script needed

**Chart config per type:**
- Line charts: `gradient_fill: true`, `smooth_line: true` for visual polish
- Bar charts: data labels on
- All charts: height "medium", grid lines on

---

## Page 3: Flags & Alerts

Answers: "When have things gone wrong, and is there a pattern?"

```
  HEADING 2: Flagged Days

  LINKED DB VIEW: Table
  Filter: last 14 days WHERE any flag = true
  (Notion filter: OR across all flag_* formula fields = true)
  Visible: date, all flag_* fields, recovery_score,
  hrv_sdnn_ms, rhr_bpm, sleep_deep_min
  Sorted: date descending

  CHART: Flag Frequency (bar)
  x: date, y: count of flagged fields (requires a formula)

  ▶ TOGGLE: Flag Definitions
  Table listing each flag, its threshold, and interpretation
```

---

## Page 4: Full Data Table

Power-user access to all data.

```
  LINKED DB VIEW: Full table
  All columns visible
  Sorted: date descending
  Quick filters enabled: source_tags, date range
  Wrap cells: false
  Frozen column: date (index 0)
```

---

## Page 5: Settings & Reference

Static reference content. Updated manually or via script when baselines change.

```
  HEADING 2: Current Baselines
  Paragraph: HRV 60-day: 53.2 ms
  Paragraph: RHR target: 61–66 bpm
  Paragraph: Deep sleep target: ≥50 min
  Paragraph: Deep sleep floor: ≥35 min
  Paragraph: HRV hard floor: ≥40 ms

  ▶ TOGGLE: Recovery Scoring Algorithm
  (Full algorithm from coaching-layer.md)

  ▶ TOGGLE: Stimulant Protocol & Decision Tree
  (Full protocol from coaching-layer.md)

  ▶ TOGGLE: Flag Thresholds
  Table: each flag formula, its trigger condition, interpretation

  ▶ TOGGLE: Zone Mapping
  Table: score range → zone → color → meaning
```

---

## Deployment Script Spec (`src/deploy_dashboard.py`)

### What it does
1. Creates 5 child pages under the Cornflower Health parent page
2. Appends all block children (headings, callouts, toggles, dividers, paragraphs, tabs) to each page
3. Creates linked database views via `POST /v1/views` with `create_database` param
4. Creates chart views via `POST /v1/views` with `type: "chart"`
5. Handles 2-level nesting limit with recursive append calls
6. Stores created page IDs and view IDs in a config file (`config/dashboard_ids.json`) for the daily update script to reference

### Arguments
- `--dry-run` — print all API calls without executing
- `--page [name]` — deploy only a specific page (for partial updates)

### Output
- `config/dashboard_ids.json` — maps page names to Notion page IDs and block IDs for scripted sections

---

## Daily Update Script Spec (`src/update_dashboard.py`)

### What it does
1. Reads `config/dashboard_ids.json` to find the Daily Dashboard page and its block IDs
2. Queries Notion for today's row + last 7 and 60 rows (for baselines)
3. Computes recovery score breakdown using the algorithm from coaching-layer.md
4. Formats all scripted sections (recovery callout, breakdown, metrics, sleep, flags, booster, averages)
5. Updates existing blocks via `PATCH /v1/blocks/{id}` or deletes + re-appends if structure changed
6. Leaves linked database view sections untouched

### Schedule
Run daily at ~09:00 AM MDT (after HAE morning export and baselines computation). Can also be run manually via CLI.

### Arguments
- `--dry-run` — show formatted output without writing to Notion
- `--date YYYY-MM-DD` — override date (useful for testing with historical data)

---

## Manual UI Steps (Post-Deploy Checklist)

After the API deployment, complete these in the Notion UI:

- [ ] Add "Log Today's Entry" button on Daily Dashboard (action: add page to daily health DB with date = today)
- [ ] Set "Show as Bar" display on `recovery_score` property (in Full Data Table view)
- [ ] Configure chart accent colors if defaults aren't satisfactory
- [ ] Set conditional row coloring on Flags table (red background for RED zone days)
- [ ] Verify all linked views render correctly on mobile
- [ ] Add pages to Notion Favorites for quick mobile access

---

*Design spec v2 — incorporates all user feedback from April 6 conversation.*
*Ready for implementation.*

---

## Phase 6 — Visual Enhancement Spec (added 2026-04-07)
*Not yet implemented. Design target for a future agentic session.*

### Goal
Elevate the Daily Dashboard from structured text to a visually rich, card-based interface
resembling the Athlytic / Bevel mobile UI. The current text-based blocks are functional
but don't provide strong at-a-glance visual cues.

### Desired Visual Elements

**1. Recovery Ring / Circle Progress Indicator**
The top-of-page recovery zone display should show a visual ring or arc representing
0–100 score (like Athlytic's green ring or Bevel's circular gauge), not just text.
Notion does not natively support SVG or HTML embeds in standard pages, so this will
likely require either:
- A hosted HTML page (served from Render at `/dashboard`) that reads from Notion via API
  and renders charts with Chart.js or D3
- A Notion embed block pointing to that hosted URL
- Fallback: text-based progress bar approximation using Unicode block chars (▓▓▓▓░)

**2. Metric vs Baseline Band Visualization**
Key metrics (HRV, RHR, deep sleep) should be plotted or displayed relative to the
user's personal historical range, similar to Athlytic's "normal range band" visualization:
- Show today's value as a point
- Show the 60-day ± 1 SD band as context
- Color-code the position: above band = green, in band = yellow, below band = red
- Notion approach: formatted text + colored callout block indicating position
- Full visual approach: hosted HTML with sparkline charts

**3. Card-Based Section Layout**
Each metric section (Recovery, Sleep, Flags, Booster) should feel like a distinct card:
- Colored background callout as the card container (already partially done)
- Icon + bold title at top of each card
- Key number large and prominent
- Secondary context (7d avg, 60d baseline) smaller below
- Horizontal dividers between cards (already present)

**4. Trend Arrows with Context**
Current arrows (↑↓→) are good but should include color context:
- Green ↑ for favorable direction (HRV up, RHR down)
- Red ↓ for unfavorable direction
- Gray → for stable
Notion's colored text annotations support this.

### Implementation Path
1. **Short term (Notion-only):** Improve callout formatting in `update_dashboard.py` —
   better emoji use, colored text for metrics, Unicode progress bars for the ring
2. **Medium term (hosted dashboard):** Build `src/dashboard_server.py` — a FastAPI
   page that queries Notion and renders an HTML mobile dashboard with Chart.js rings
   and baseline bands. Serve at `https://cornflower-health.onrender.com/dashboard`.
   This is the approach needed for true Athlytic-style visual richness.
3. **Long term:** Consider a dedicated iOS shortcut or widget that hits the Render
   endpoint and shows a native-feeling card widget.

### Priority
Medium. The data pipeline and daily automation are the foundation. Visual polish
comes once the data is confirmed reliable for 2+ weeks of live operation.
