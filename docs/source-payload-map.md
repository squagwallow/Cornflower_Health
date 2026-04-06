# Source Payload Map

This document maps raw Health Auto Export (HAE) metric names to normalized internal field names used by the backend and stored in Notion.

**Status as of 2026-04-06:** A real HAE payload has been captured and verified. All fields previously marked "assumed" or "needs verification" have been updated. See `samples/hae_sample_2026-04-05.json`.

---

## Confirmed HAE Payload Structure

```
[                                          ← outer array (always one element in practice)
  {
    "data": {
      "metrics": [                         ← array of metric objects
        {
          "name": "metric_name",           ← string identifier
          "units": "unit_string",          ← e.g. "ms", "count/min", "degF", "hr"
          "data": [                        ← array of daily records
            {
              "date": "YYYY-MM-DD HH:MM:SS ±HHMM",
              "qty": <number>,             ← for scalar metrics (HRV, RHR, resp rate, SpO2, wrist temp)
              "source": "device string"
            }
          ]
        }
      ]
    }
  }
]
```

**Special cases confirmed from real payload:**

- `heart_rate` uses `Avg`, `Min`, `Max` instead of `qty` — **capitalization confirmed: capital A, capital M**
- `sleep_analysis` uses a flat object per day with named stage keys (not a `qty` field) — **units are HOURS, not minutes**
- `inBed` and `asleep` keys exist in `sleep_analysis` but are always `0` — **do not use these**
- `blood_oxygen_saturation` is in percent (91–93 range) — **no decimal normalization needed**
- `apple_sleeping_wrist_temperature` is in `degF` — **confirmed, not °C**
- Outer array wrapper: the payload is `[ { "data": { "metrics": [...] } } ]` — index `[0]` to get the data object

---

## Mapping Table — v1 Fields (HAE-Sourced)

All entries below are **verified from `samples/hae_sample_2026-04-05.json`** unless noted.

| HAE Metric Name | HAE Payload Path | Notion Field Name | Unit In | Unit Stored | Notes |
|---|---|---|---|---|---|
| `heart_rate_variability` | `[0].data.metrics[name="heart_rate_variability"].data[date].qty` | `hrv_sdnn_ms` | ms | ms | Not present every day — null if missing |
| `resting_heart_rate` | `...data[date].qty` | `rhr_bpm` | count/min | bpm | Present every day in sample |
| `respiratory_rate` | `...data[date].qty` | `resp_rate_brpm` | count/min | brpm | Present every day |
| `apple_sleeping_wrist_temperature` | `...data[date].qty` | `wrist_temp_abs` | **degF** | degF | Unit confirmed °F. No conversion needed. |
| `blood_oxygen_saturation` | `...data[date].qty` | `spo2_avg_pct` | % | % | Already in percent (91–93 range). **No decimal→percent conversion needed.** |
| `heart_rate` | `...data[date].Avg` | `hr_day_avg_bpm` | count/min | bpm | Capital `Avg` confirmed |
| `heart_rate` | `...data[date].Min` | `hr_day_min_bpm` | count/min | bpm | Capital `Min` confirmed. Note: Min is a float (e.g. 48.409) |
| `heart_rate` | `...data[date].Max` | `hr_day_max_bpm` | count/min | bpm | Capital `Max` confirmed |
| `sleep_analysis` | `...data[date].totalSleep` | `sleep_time_asleep_min` | **hours** | minutes | **Multiply by 60** |
| `sleep_analysis` | derived from `inBedStart`/`inBedEnd` | `sleep_time_in_bed_min` | — | minutes | `inBed` key is always 0 — **compute from timestamps instead**: `(inBedEnd - inBedStart)` in minutes |
| `sleep_analysis` | `...data[date].deep` | `sleep_deep_min` | **hours** | minutes | **Multiply by 60** |
| `sleep_analysis` | `...data[date].rem` | `sleep_rem_min` | **hours** | minutes | **Multiply by 60** |
| `sleep_analysis` | `...data[date].core` | `sleep_core_min` | **hours** | minutes | **Multiply by 60** |
| `sleep_analysis` | `...data[date].awake` | `sleep_awake_min` | **hours** | minutes | **Multiply by 60** |
| `sleep_analysis` | `...data[date].sleepStart` | `sleep_bedtime` | datetime string | text | Store as-is or format to "HH:MM AM/PM" |
| `sleep_analysis` | `...data[date].sleepEnd` | `sleep_waketime` | datetime string | text | Also use for deriving `date` and `sleep_waketime_num` |

### `sleep_waketime_num` Derivation

Parse `sleepEnd` timestamp, extract local hour and minute, convert to minutes after midnight:
```python
sleep_waketime_num = hour * 60 + minute
# e.g. "2026-04-05 04:31:08 -0600" → 4*60+31 = 271
```

### `date` Field Derivation

Derive from `sleep_analysis[date]` field (the record's `date` key), parsed to `YYYY-MM-DD`:
```python
date = record["date"].split(" ")[0]  # "2026-04-05 00:00:00 -0600" → "2026-04-05"
```

---

## Fields NOT Available in HAE Payload (Confirmed Absent)

| Field | Status | Implication |
|---|---|---|
| `hr_sleep_avg_bpm` | **Not in payload** | No sleep-window HR segmentation in HAE. Must be populated from Bevel/Athlytic or manual entry only. |
| `hr_sleep_min_bpm` | **Not in payload** | Same as above |
| `sleep_awakenings_count` | **Not in payload** | HAE does not expose individual awakening events. Field remains manual-only. |
| `sleep_longest_wake_min` | **Not in payload** | Same as above |
| `spo2_min_pct` | **Not in payload** | HAE only provides daily average SpO2, not nightly minimum. Manual-only from Bevel/Athlytic. |

This resolves the Phase 2 uncertainty: `hr_sleep_avg_bpm`, `hr_dip_pct`, and `hr_dip_category` **cannot be auto-populated from HAE**. These fields stay manual unless a separate HR segmentation approach is developed.

---

## Manually-Entered Fields (No HAE Source)

| Notion Field Name | Source |
|---|---|
| `energy_1_5`, `day_quality_1_5` | Manual daily entry |
| `meds_notes`, `notes`, `workout_summary` | Manual |
| `morning_heaviness`, `afternoon_crash`, `workout_rest_day` | Manual checkboxes |
| `stress_context`, `fatigue_level`, `workout_type`, `workout_exertion_felt` | Manual selects |
| `booster_status`, `booster_decision` | Manual selects |
| `workout_total_min`, `workout_z2_min`, `workout_z3_min`, `workout_z4_min` | Manual |
| `recovery_score` | Manual or LLM coaching layer output |
| `hr_sleep_avg_bpm`, `hr_sleep_min_bpm` | Manual (from Bevel/Athlytic) |
| `spo2_min_pct` | Manual (from Bevel/Athlytic) |
| `sleep_awakenings_count`, `sleep_longest_wake_min` | Manual |
| `hrv_baseline_60d_ms`, `rhr_baseline_60d_bpm` | Manual seed; rolling computation (Phase 3) |
| `hrv_7d_avg_ms`, `rhr_7d_avg_bpm`, `deep_sleep_7d_avg_min`, `hr_dip_7d_avg_pct` | Computed (Phase 3 script) |

---

## Metrics in Payload Not Mapped to Notion

The following metrics are present in the HAE payload but are not written to the Notion database (not in scope for v1 or coaching layer):

| HAE Metric | Units | Notes |
|---|---|---|
| `apple_stand_time` | min | Activity ring metric; not health-relevant for coaching |
| `apple_stand_hour` | count | Same |
| `apple_exercise_time` | min | Apple's move ring; less granular than manual workout logging |
| `active_energy` | kcal | Available if needed for future exertion scoring |
| `basal_energy_burned` | kcal | Available if needed |
| `step_count` | count | Available if needed |
| `flights_climbed` | count | Available if needed |
| `walking_running_distance` | mi | Available if needed |
| `walking_heart_rate_average` | count/min | Potentially useful for future exertion context |
| `walking_speed`, `walking_step_length`, `walking_asymmetry_percentage`, `walking_double_support_percentage` | various | Gait metrics; not in scope |
| `vo2_max` | ml/(kg·min) | Useful future field — add to Phase 2 consideration |
| `cardio_recovery` | count/min | Potentially useful; add to Phase 2 consideration |
| `atrial_fibrillation_burden` | % | Clinical; not in scope |
| `stair_speed_up`, `stair_speed_down` | ft/s | Not in scope |
| `six_minute_walking_test_distance` | m | Not in scope |
| `physical_effort` | kcal/hr·kg | Available if needed |
| `environmental_audio_exposure`, `headphone_audio_exposure` | dBASPL | Not in scope |
| `time_in_daylight` | min | Potentially useful for circadian context; add to Phase 2 consideration |

---

## Field Naming Conventions

- `snake_case` throughout
- Metric category prefix: `sleep_`, `hr_`, `hrv_`, `resp_`, `spo2_`, `wrist_`
- Unit suffix for numeric fields: `_ms`, `_bpm`, `_min`, `_pct`, `_brpm`
- No raw HAE field names exposed in Notion

---

*Last updated: 2026-04-06 — Fully verified against `samples/hae_sample_2026-04-05.json`. Removed all "assumed" and "needs verification" flags. Added confirmed unit, structure, and absence findings.*
