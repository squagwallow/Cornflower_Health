# Intra-Day Monitoring — Design Document

This document specifies the architecture for capturing health data multiple times per day, enabling real-time strain/battery tracking and LLM-driven intra-day coaching. It extends the existing daily pipeline (HAE → Render → Notion) without replacing it.

**Status:** Design phase. Not yet implemented. Added to implementation backlog as Phase 5.

**Origin:** Discussed in the April 6, 2026 session. The user wants to replicate how Bevel and Athlytic provide ongoing stress/recovery interpretation throughout the day — suggesting when to keep working, follow through on a workout, or take it easy.

---

## Design Principles

1. **The daily table stays as-is.** One row per day in Daily Health Metrics remains the authoritative overnight recovery record. Intra-day data lives in a separate table.
2. **The DB should expect the data even before automation is fully wired.** Schema and server endpoints should be built to accept intra-day snapshots regardless of whether HAE automations are configured.
3. **Unlimited rows per day.** No artificial cap. Default is 4 scheduled syncs + manual on-demand, but the system accepts any number.
4. **Smart filtering.** Sleep data only populates on the first morning sync. Subsequent syncs capture only metrics that change intra-day (HR, HRV, steps, active energy).
5. **Steps in every update.** Steps are always included — they're the most reliable passive activity signal throughout the day.

---

## Research Summary

### How Athlytic Does It (preferred model)

- **Recovery** — static, computed once from overnight HRV, does not change all day
- **Battery** — real-time readiness that updates every time Apple Watch records a new HRV sample. Compares rolling HRV (configurable smoothing: 1hr, 8hr, 24hr) against 60-day baseline. Source: [Athlytic Battery docs](https://athlyticapp.helpscoutdocs.com/article/38-understanding-battery)
- **Exertion/Effort** — tracks more aggressively than Bevel. Appears to use HR + steps together, capturing low-level activity like chores, cooking, walking around the house. Even without a logged workout, extended periods of moderate movement rack up exertion. This mirrors the user's real-world experience.
- **Stress** — real-time, HRV-based. Lower HRV relative to baseline = higher stress signal.
- **Key detail:** Athlytic pulls HRV samples throughout the day from Apple Health. Enabling AFib History in Apple Health increases HRV sampling frequency, making Battery more responsive. A Breathe session in the Mindfulness app triggers an immediate HRV reading.

### How Bevel Does It

- **Strain Score** — has two components: active strain (logged workouts) and passive strain (motion, HR, steps outside workouts). Source: [Bevel Strain docs](https://www.bevel.health/blog/what-is-strain-score)
- **Energy Bank** — combines recovery, sleep, strain, and stress into a single metric showing energy build/drain throughout the day
- **Key limitation:** Bevel historically required workout logging to capture meaningful strain. A recent update added passive strain, but Apple Watch only samples HR every ~5 minutes outside workouts (vs. every second during workouts), so "hidden effort" like chores/teaching/walking often goes unrecorded unless logged as a workout. Source: [Reddit discussion](https://www.reddit.com/r/bevelhealth/comments/1o243ok/bevel_strain_level_with_and_without_training/)

### How WHOOP Does It

- **Day Strain** — accumulates continuously from midnight, including non-exercise cardiovascular load. Logarithmic scale (0–21): harder to build more strain the higher you go. A stressful meeting or busy afternoon raises strain even on rest days. Source: [WHOOP Strain docs](https://www.whoop.com/us/en/thelocker/how-does-whoop-strain-work-101/)
- **Recovery** — static morning score based on HRV, RHR, sleep performance, respiratory rate. Source: [WHOOP Recovery docs](https://www.whoop.com/us/en/thelocker/how-does-whoop-recovery-work-101/)
- **Key advantage:** WHOOP samples HR every second, 24/7. This gives it much more granular strain data than Apple Watch (which samples every ~5 min outside workouts).

### User Preference

The user prefers Athlytic's approach because:
- It captures strain from non-workout activity (chores, cooking, walking) more aggressively
- Hours of household chores should register as comparable strain to a one-hour workout
- Steps + HR together are a better proxy for total daily exertion than HR alone (which misses low-intensity movement)
- The Battery concept (real-time readiness fluctuating throughout the day) is preferred over a static daily recovery score alone
- Stress tracking via HRV throughout the day is valued

### Best Practice: Exertion Calculation

Based on the STATSports HR Exertion formula and TrainingPeaks TRIMP methodology:

```
HR Exertion = C * Σ (Wi * dti)

Where:
  Wi = weighting based on HR / Max HR (exponential curve — higher zones weighted more)
  dti = time interval between measurements
  C = scaling constant
```

For our implementation (Apple Watch with ~5 min sampling outside workouts):
- Use HR zone time estimates between samples
- Supplement with step cadence as a proxy for effort intensity during gaps
- Weight steps + HR together: if steps are high but HR data is sparse, infer moderate exertion

---

## Architecture

### Two-Table Model

```
Daily Health Metrics (existing)          Intra-Day Snapshots (new)
┌──────────────────────────────┐        ┌──────────────────────────────┐
│ One row per calendar day     │        │ Multiple rows per day        │
│ Overnight recovery data      │◄───────│ Links to daily row via date  │
│ Sleep, HRV, RHR, flags       │        │ HR, HRV, steps, energy,      │
│ Coaching layer primary input │        │ strain, battery, self-reports │
│ Source: morning HAE sync     │        │ Source: scheduled + manual    │
└──────────────────────────────┘        └──────────────────────────────┘
```

### Intra-Day Snapshots — Notion Schema

| Field | Type | Populated By | Notes |
|---|---|---|---|
| `snapshot_id` | Title | Auto | `YYYY-MM-DD_HH:MM` |
| `date` | Date | Auto | Links to daily table row |
| `timestamp` | Rich text | Auto | Full ISO timestamp with timezone |
| `snapshot_type` | Select | Auto/Manual | `morning` / `midday` / `afternoon` / `evening` / `manual` |
| `source` | Select | Auto | `hae_scheduled` / `hae_manual` / `user_manual` |
| **Biometric — always included** | | | |
| `hr_current_bpm` | Number | HAE | Latest HR reading at sync time |
| `hr_avg_since_wake` | Number | Computed | Avg HR from first snapshot to now |
| `hrv_latest_ms` | Number | HAE | Most recent HRV sample |
| `steps_cumulative` | Number | HAE | Total steps so far today |
| `steps_since_last` | Number | Computed | Steps since previous snapshot |
| `active_energy_cumulative` | Number | HAE | Active calories so far today |
| **Derived — computed at each snapshot** | | | |
| `strain_score` | Number | Computed | Cumulative exertion (0–21 scale, logarithmic, WHOOP-style) |
| `strain_delta` | Number | Computed | Strain accumulated since last snapshot |
| `battery_pct` | Number | Computed | Real-time readiness (0–100, Athlytic-style) |
| `stress_signal` | Select | Computed | `low` / `moderate` / `high` / `very_high` based on HRV vs baseline |
| **Subjective — manual only** | | | |
| `energy_self_report` | Select | Manual | 1–5 scale |
| `stress_self_report` | Select | Manual | 1–5 scale |
| `activity_note` | Rich text | Manual | e.g., "45 min walk", "2hr desk work", "cooking + cleaning" |
| `notes` | Rich text | Manual | Freeform |
| **Morning-only fields** | | | |
| `sleep_carried_over` | Checkbox | Auto | True if this snapshot includes sleep data (first morning sync only) |

### Default Sync Schedule

| Time | Type | What's Captured |
|---|---|---|
| ~7:00 AM | `morning` | Full sync: overnight sleep data → daily table + first intra-day snapshot (recovery, battery starting point, initial HR/HRV/steps) |
| ~12:00 PM | `midday` | HR, HRV, steps, active energy, strain, battery. No sleep data. |
| ~5:00 PM | `afternoon` | Same as midday. Captures post-work/workout exertion. |
| ~9:00 PM | `evening` | Same as midday. End-of-day strain total, final battery reading. |
| Any time | `manual` | User-triggered. Same fields as midday. |

### Strain Calculation (Athlytic-inspired, steps-inclusive)

```python
def compute_strain(snapshots_today, max_hr, resting_hr):
    """
    Cumulative strain score (0-21, logarithmic).
    Uses HR zone time + step cadence as dual inputs.
    
    Key design choice: steps contribute to strain even when
    HR data is sparse (Apple Watch 5-min sampling gap).
    This captures chores, cooking, errands — the "hidden effort"
    that Bevel historically missed but Athlytic captures.
    """
    raw_load = 0
    
    for i, snap in enumerate(snapshots_today[1:], 1):
        prev = snapshots_today[i - 1]
        duration_min = (snap.timestamp - prev.timestamp).total_seconds() / 60
        
        # HR component: time-in-zone weighted
        hr = snap.hr_current_bpm or prev.hr_current_bpm
        if hr:
            hr_reserve_pct = (hr - resting_hr) / (max_hr - resting_hr)
            hr_weight = max(0, hr_reserve_pct) ** 1.5  # exponential weighting
            raw_load += hr_weight * duration_min
        
        # Step component: captures movement between sparse HR samples
        steps_delta = (snap.steps_cumulative or 0) - (prev.steps_cumulative or 0)
        cadence = steps_delta / max(duration_min, 1)  # steps per minute
        if cadence > 30:  # meaningful movement threshold
            step_weight = min(cadence / 120, 1.0) * 0.3  # caps at ~120 spm
            raw_load += step_weight * duration_min
    
    # Logarithmic scaling to 0-21 (WHOOP-style)
    strain = 21 * (1 - math.exp(-raw_load / 500))
    return round(strain, 1)
```

### Battery Calculation (Athlytic-inspired)

```python
def compute_battery(hrv_latest, hrv_baseline_60d, morning_recovery_score,
                    strain_current, hours_since_wake):
    """
    Real-time readiness (0-100).
    Starts at morning recovery score, drains with strain,
    adjusts with HRV relative to baseline.
    
    Smoothing: 8hr default (configurable).
    """
    # HRV ratio: >1.0 means above baseline (good), <1.0 means below (draining)
    hrv_ratio = hrv_latest / hrv_baseline_60d if hrv_baseline_60d else 1.0
    
    # Strain drain: logarithmic — high strain drains faster
    strain_drain = strain_current * 3  # roughly 3 battery points per strain unit
    
    # Time drain: natural energy decline through the day
    time_drain = hours_since_wake * 1.5
    
    # HRV adjustment: above-baseline HRV slows drain, below accelerates it
    hrv_adjustment = (hrv_ratio - 1.0) * 20  # ±20 points max
    
    battery = morning_recovery_score - strain_drain - time_drain + hrv_adjustment
    return round(max(0, min(100, battery)), 0)
```

### Stress Signal (HRV-based)

```python
def compute_stress(hrv_latest, hrv_baseline_60d):
    """
    Real-time stress signal based on current HRV vs baseline.
    Lower HRV = higher stress.
    """
    if not hrv_latest or not hrv_baseline_60d:
        return None
    
    ratio = hrv_latest / hrv_baseline_60d
    
    if ratio >= 0.9:
        return "low"
    elif ratio >= 0.7:
        return "moderate" 
    elif ratio >= 0.5:
        return "high"
    else:
        return "very_high"
```

---

## Server Changes

### New Endpoint: `/snapshot`

Accepts intra-day HAE payloads. Separate from `/webhook` (which handles the daily full sync).

```
POST /snapshot
  → validate secret
  → log raw payload
  → snapshot_normalize(payload)  # extracts only intra-day relevant fields
  → compute strain, battery, stress from today's snapshot history
  → write to Intra-Day Snapshots Notion table
  → return 200 with snapshot summary
```

### Smart Routing (alternative)

Or, the existing `/webhook` endpoint detects whether the payload is a morning full-sync or an intra-day update based on:
- Time of day
- Whether sleep data is present and fresh
- Whether a daily row already exists for today

This is simpler from the HAE configuration side (one URL for everything).

---

## LLM Coaching Integration

### Two Prompt Variants

**Morning Brief** (existing design, uses daily table):
```
## RECOVERY
[Score] | [Zone] | [One-line summary]
## KEY METRICS / SLEEP / TODAY / FLAGS
...
```

**Intra-Day Check-In** (new, uses snapshot table):
```
## CURRENT STATUS
Battery: [X]% (started at [Y]%) | Strain: [X]/21
Stress signal: [level] | Steps: [count]

## SINCE LAST CHECK-IN
Strain added: [+X] | Battery change: [±X]%
Activity: [summary from notes or inferred from steps/HR]

## GUIDANCE
[Should you push through, ease off, take a break?]
[Workout go/no-go based on current battery + morning recovery]
[Booster decision update if applicable]
```

### When to Surface Intra-Day Coaching

The coaching layer should generate an intra-day interpretation when:
- A scheduled snapshot arrives (4x/day)
- The user manually requests a check-in
- Battery drops below a threshold (e.g., 30%)
- Strain exceeds the day's recommended target (based on morning recovery)

---

## HAE Configuration

### Automation Setup (4 scheduled + manual)

Each HAE automation exports the same metrics but at different times:

1. **Cornflower Morning** — 7:00 AM → `https://cornflower-health.onrender.com/webhook` (full daily sync, writes to both tables)
2. **Cornflower Midday** — 12:00 PM → `https://cornflower-health.onrender.com/snapshot`
3. **Cornflower Afternoon** — 5:00 PM → `https://cornflower-health.onrender.com/snapshot`
4. **Cornflower Evening** — 9:00 PM → `https://cornflower-health.onrender.com/snapshot`

Manual: user triggers any automation at will → creates an additional `manual` snapshot.

### HAE Metrics to Include in Intra-Day Exports

Not all 30 metrics HAE sends are needed for intra-day. Configure exports to include:

| Metric | Why |
|---|---|
| `heart_rate` | Current HR, avg/min/max since last reading |
| `heart_rate_variability` | Latest HRV sample for battery/stress |
| `step_count` | Cumulative steps — always included |
| `active_energy` | Active calories burned |
| `apple_exercise_time` | Minutes of exercise-level activity |
| `apple_stand_time` | Stand hours (proxy for sedentary vs. active) |
| `flights_climbed` | Additional movement signal |
| `walking_heart_rate_average` | Ambulatory HR (useful for strain when resting HR is unavailable) |

Sleep metrics, respiratory rate, wrist temperature, SpO2 — **excluded from intra-day** (only meaningful in morning sync).

---

## Implementation Plan

This is Phase 5 work (after backfill is complete), broken into sub-tasks:

| Task | Description | Depends On |
|---|---|---|
| 5.0 | Create Intra-Day Snapshots Notion database via API | — |
| 5.1 | Write `snapshot_normalize()` function | Task 5.0 |
| 5.2 | Write strain/battery/stress computation module | Task 5.1 |
| 5.3 | Add `/snapshot` endpoint to server | Tasks 5.1, 5.2 |
| 5.4 | Smart routing: detect morning vs. intra-day in `/webhook` | Task 5.3 |
| 5.5 | Configure 4 HAE scheduled automations | Task 5.3 deployed |
| 5.6 | Intra-day coaching prompt template | Task 5.3 |
| 5.7 | Battery/strain dashboard view in Notion | Task 5.2 |

---

## Open Questions

1. **HAE automation limits** — Does HAE free tier support 4+ scheduled automations? Need to verify.
2. **Apple Watch HR sampling rate** — Outside workouts, Apple Watch samples HR every ~5 minutes. This limits strain granularity. Enabling AFib History or doing Breathe sessions increases HRV sampling but not HR. Steps fill the gap.
3. **Battery smoothing window** — Default 8hr. Should this be configurable per user? (Athlytic allows 1hr/8hr/24hr.)
4. **Strain scale** — WHOOP uses 0–21 (logarithmic). Athlytic uses a different scale. Which to adopt? Recommendation: 0–21 (well-understood, documented).
5. **Notion performance** — Multiple rows per day multiplied by months of data could grow large. May need periodic archival or a rollup strategy.

---

*Created: 2026-04-06. Status: Design only — not yet implemented.*
