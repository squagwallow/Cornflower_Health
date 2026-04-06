# Coaching Layer — Domain Logic Reference

This document captures the product logic, scoring algorithms, coaching prompt structure, and personal health baselines that give the data pipeline its purpose. It is the specification for the LLM coaching layer that sits on top of the Notion database.

**Source:** Rescued from deprecated thread reports (April 5–6, 2026). This content existed only in those threads and is recorded here to prevent loss.

---

## Architecture Position

```
Notion database (daily rows)
    ↓
LLM coaching layer (reads Notion fields → generates daily brief)
    ↓
Mobile-first dashboard output
```

The pipeline (HAE → backend → Notion) is infrastructure. This document defines what the pipeline serves.

---

## User Health Baselines

These are the calibrated personal baselines as of April 2026. They inform all recovery scoring and interpretation thresholds.

| Metric | Baseline Value | Notes |
|---|---|---|
| HRV 60-day rolling baseline | **53.2 ms** | SDNN; used as denominator in recovery score |
| RHR target range | **61–66 bpm** | Below 61 = well-recovered; above 66 = elevated |
| Deep sleep target | **≥50 min** | Advancement gate for titration; flag threshold |
| Deep sleep absolute floor | **≥35 min** | Hard gate: below this, cannot score GREEN |
| HRV hard floor | **≥40 ms** | Below this AND deep < 35 min → force RED |

---

## Recovery Scoring Algorithm

### Base Score Formula

The recovery score (0–100) is computed from two components:

**HRV component (~60% weight):**
```
hrv_score = (hrv_sdnn_ms / hrv_baseline_60d_ms) * 60
```
Capped at 60. If `hrv_sdnn_ms` is above baseline, the component is still capped at 60 to prevent inflation.

**RHR component (~40% weight):**
```
rhr_score = clamp(((rhr_baseline_60d_bpm - rhr_bpm) / rhr_baseline_60d_bpm) * 40 + 40, 0, 40)
```
Higher RHR subtracts from the component; lower RHR adds.

**Combined base:**
```
base_score = hrv_score + rhr_score  (range: 0–100)
```

### Modifier Adjustments

Apply these modifiers to the base score:

| Condition | Adjustment | Notes |
|---|---|---|
| Deep sleep 50–65 min | +0 | Neutral |
| Deep sleep 65–80 min | +3 | Good |
| Deep sleep ≥80 min | +5 | Excellent |
| Deep sleep 35–50 min | -5 | Mild deficit |
| Deep sleep 20–35 min | -10 | Moderate deficit |
| Deep sleep <20 min | -15 | Severe deficit |
| SpO2 avg ≥95% | +0 | Normal |
| SpO2 avg 92–94% | -3 | Borderline |
| SpO2 avg <92% | -8 | Significant |
| SpO2 min <88% | -5 | Additional penalty (stacks) |
| Resp rate ≤15 brpm | +2 | Low sympathetic arousal |
| Resp rate 16–18 brpm | +0 | Normal |
| Resp rate ≥19 brpm | -5 | Elevated; physiological stress marker |
| Fragmented sleep (≥4 awakenings) | -5 | |
| Early wake (waketime_num ≤ 300 min after midnight) | -3 | Proxy: wake before ~5:00 AM |
| Stress context = High or Extreme | -5 | Life stress counts as physiological load |
| Illness (via notes or flags) | -10 to -20 | Clinical judgment; not auto-scored |
| Soreness (via notes) | -3 | |

### Hard Gate Rules

Hard gates override the computed score regardless of modifiers:

| Condition | Override |
|---|---|
| `rhr_bpm` > 68 | Cannot score GREEN (cap zone at YELLOW) |
| `sleep_deep_min` < 35 | Cannot score GREEN |
| `hrv_sdnn_ms` < 40 AND `sleep_deep_min` < 35 | Force RED regardless of other metrics |

### Zone Mapping

| Score Range | Zone | Meaning |
|---|---|---|
| 75–100 | 🟢 GREEN | Full training cleared |
| 50–74 | 🟡 YELLOW | Moderate load only |
| 25–49 | 🟠 ORANGE | Light activity or active recovery |
| 0–24 | 🔴 RED | Rest day; no structured training |

### Calibration Note

Early testing found the algorithm significantly over-generous compared to Athlytic and Bevel on the same data (76% GREEN vs. Bevel's 20% and Athlytic's 28% on an equivalent day). The hard gate rules above are the primary correction mechanism. When re-testing:

- Use the "March crash" as a calibration reference: stacked load (high stress + poor sleep + elevated RHR) should produce RED regardless of HRV
- Compare output against Bevel and Athlytic for 7–14 days before trusting the scoring layer

---

## Flag TTL Tiers

Flags are health context annotations that carry different temporal weight in LLM coaching.

| Tier | Label | Duration | Fading Behavior |
|---|---|---|---|
| Tier 0 | Permanent | Indefinite | Never fades; always active |
| Tier 1 | Anchored | Multi-month (3–6+ months) | Does not fade unless explicitly cleared |
| Tier 2 | Seasonal | 4–8 weeks | Loses weight unless reinforced by new events |
| Tier 3 | Recent | 1–2 weeks | Fades unless pattern continues; low weight after 2 weeks |

**Examples by tier:**

- Tier 0: Diagnosis, baseline medication protocol
- Tier 1: Major stressor period, protocol change, significant health event
- Tier 2: Illness recovery period, seasonal training block, titration phase
- Tier 3: Single bad sleep night, single missed dose, transient stressor

**Logging semantics for flags:**

- `confirmed` — directly measured or clearly observed
- `inferred` — derived from proxy signals (e.g., high RHR + poor sleep → inferred illness)
- `deviation` — departure from established pattern (e.g., dose skipped, unusual wake time)

---

## HR Dip Formula and Categories

The nocturnal HR dip is a cardiovascular recovery marker. It is computed from the difference between daytime and sleep-window heart rate.

**Formula:**
```
hr_dip_pct = round(((hr_day_avg_bpm - hr_sleep_avg_bpm) / hr_day_avg_bpm) * 100)
```

**Category thresholds:**

| HR Dip % | Category | Interpretation |
|---|---|---|
| ≥15% | Normal dipper | Good autonomic recovery |
| 10–14% | Borderline dipper | Mild concern; watch trend |
| <10% | Non-dipper | Elevated cardiovascular risk marker; flag for coaching layer |

**Notion implementation:** `hr_dip_pct` is a formula field (confirmed working). `hr_dip_category` is also a formula using inline computation (no formula-to-formula reference — see `notion-api-notes.md`).

**Note on data availability:** `hr_sleep_avg_bpm` requires HAE to expose heart rate samples segmented by sleep window. This is not yet confirmed from a real payload. Until confirmed, both fields are populated manually or via Bevel/Athlytic comparison.

---

## Stimulant Titration Protocol

### Current Baseline Protocol

- **Vyvanse:** 60 mg (morning)
- **Booster 1:** Dextroamphetamine 5 mg at approximately 10:00 AM
- **Booster 2:** Dextroamphetamine 5 mg at approximately 1:00 PM

### Titration Ladder

| Step | Dose |
|---|---|
| Start | 2.5 mg booster only |
| Step 2 | 5 mg booster |
| Step 3 | 5 mg + 2.5 mg (two booster doses) |
| Step 4 | 5 mg + 5 mg (current protocol) |
| Step 5 | Further titration by clinical guidance only |

### Advancement Gates

To advance one step on the titration ladder, all of the following must be met for **7 consecutive days**:

- `sleep_deep_min` ≥ 50 min
- `hrv_sdnn_ms` ≈ 50 ms (within ~10% of baseline)
- `rhr_bpm` in range 61–66 bpm
- No morning heaviness (`morning_heaviness` = false)
- No afternoon crash (`afternoon_crash` = false)

### Daily Go/No-Go Decision Tree

For each booster dose, evaluate in order:

```
1. Is HRV today < 40 ms?
   → YES: Skip both boosters. Recovery day.

2. Is RHR today > 68 bpm?
   → YES: Skip both boosters.

3. Is deep sleep last night < 35 min?
   → YES: Skip both boosters.

4. Is deep sleep 35–50 min AND HRV 40–47 ms?
   → BORDERLINE: First booster only (Booster 1). Skip Booster 2.

5. Is deep sleep ≥50 min AND HRV ≥48 ms AND RHR ≤66?
   → GREEN: Both boosters cleared.
```

**Logging the decision:** Record outcome in `booster_decision` (Green light / Borderline – first only / Recovery day – skip) and `booster_status` (Baseline only / First only / Both doses / Skipped) each day.

---

## LLM Coaching Prompt Structure (Athlytic-Mimic)

### Role Definition

> You are a daily health coach interpreting Apple Watch biometric data and subjective inputs. You do not diagnose, treat, or prescribe. You provide interpretive summaries, trend observations, and actionable daily recommendations based on data provided.

### Input Specification

The following fields are provided as structured input to the LLM each day:

**Core recovery inputs:**
- `hrv_sdnn_ms` + `hrv_baseline_60d_ms`
- `rhr_bpm` + `rhr_baseline_60d_bpm`
- `sleep_deep_min`, `sleep_rem_min`, `sleep_awake_min`, `sleep_awakenings_count`
- `sleep_efficiency_pct`
- `spo2_avg_pct`, `spo2_min_pct`
- `resp_rate_brpm`

**Trend context:**
- `hrv_7d_avg_ms`, `rhr_7d_avg_bpm`, `deep_sleep_7d_avg_min`
- `hr_dip_pct`, `hr_dip_category`

**Subjective inputs:**
- `energy_1_5`, `day_quality_1_5`
- `morning_heaviness`, `afternoon_crash`
- `fatigue_level`, `stress_context`
- `notes`, `meds_notes`

**Protocol inputs:**
- `booster_decision`, `booster_status`

**Active flags:**
- All `flag_*` fields that are true

### Output Format

The LLM should produce a structured daily brief with sections in this order:

```
## RECOVERY
[Score 0–100] | [Zone: GREEN/YELLOW/ORANGE/RED] | [One-line summary]

## KEY METRICS
HRV: [value] ms ([+/-X]% vs baseline)
RHR: [value] bpm ([zone descriptor])
SpO2 avg/min: [value]% / [value]%
Resp rate: [value] brpm

## SLEEP
Total: [value] min | Deep: [value] min | REM: [value] min
Efficiency: [value]% | Awakenings: [count] | Longest wake: [value] min
Bedtime: [value] | Waketime: [value]

## YESTERDAY LOAD
[Workout summary if applicable, or "Rest day"]
Stress: [level] | Fatigue: [level]

## TODAY
Booster decision: [decision]
Exertion recommendation: [e.g., "Zone 2 only — cap at 45 min"]

## INTERPRETATION
[2–4 sentences connecting the metrics to the day's context. Reference trends and active flags.]

## RECOMMENDATIONS
1. [Specific, actionable recommendation]
2. [Specific, actionable recommendation]
3–5. [Additional recommendations as warranted]

## FLAGS TODAY
[List of active flags with brief plain-language explanations. Omit section if no flags are active.]
```

### Constraints and Design Principles

- **Keep Athlytic as the proprietary score engine.** The LLM is an interpretation and coaching layer, not a replacement for Athlytic's scoring. Compare outputs when divergent; do not assume LLM is correct.
- **Use fresh chats per session.** Do not accumulate context within a single project conversation. Fresh chats reduce token overhead and prevent stale context from contaminating interpretation.
- **Reference the "March crash" when calibrating load interpretation.** High stress + poor sleep + elevated RHR stacked over multiple days should produce RED and generate strong rest recommendations.
- **Life stress counts as physiological load.** A high `stress_context` value should always reduce recovery zone, even if biometrics are borderline GREEN.

---

## Model Tiering Strategy

| Use Case | Model | Notes |
|---|---|---|
| Daily check-in brief | Claude Haiku | Lowest cost; connector disabled unless needed |
| Weekly trend analysis | Claude Opus | Enable Apple Health connector; fresh chat |
| Handoff document generation | Claude Sonnet | Structured output; fresh chat |

---

## Claude Projects Configuration Checklist

When setting up a Claude project for health coaching:

- [ ] **Memory → OFF** for this project (Memory uses lossy summarization ~1,500–1,750 words; sensitive health data should not flow through Memory)
- [ ] **Training opt-out → verify** in Claude Settings → Privacy
- [ ] **Connectors → disable when not in use** (each connector adds 100–500 tokens per message overhead)
- [ ] **Apple Health data types → configure** in iOS Settings → Health → Data Access → Claude
- [ ] **Add to project knowledge:** This `coaching-layer.md`, the current `schema-plan.md`, and the daily Notion export

**HIPAA note:** Claude Pro (consumer) is NOT HIPAA-compliant. Do not enter protected health information (PHI) in this context. Use anonymized or de-identified data. HIPAA compliance requires Claude for Work or API with a Business Associate Agreement (BAA).

---

## Reference Events

### The March Crash

A calibration reference for stacked physiological load interpretation. During this event:
- High life stress (external stressor)
- Poor sleep (deep < 35 min for multiple consecutive nights)
- Elevated RHR (>68 bpm)
- Suppressed HRV (< 40 ms)
- Duration: approximately 5–7 days before recovery

**Coaching layer expectation:** This pattern should produce RED zone on all affected days, with recommendations to skip all boosters, prioritize sleep, and reduce all discretionary stress.

---

*Last updated: 2026-04-06 — Rescued from deprecated thread reports (Threads: April 5 am, April 5 Ap 5, April 5 to 6 inter, April 5 short, Apr 5 to 6 full)*
