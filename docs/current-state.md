# Current State

This document is the ground-truth record of what has been confirmed, what has failed, what decisions have been made, and what remains uncertain. It should be updated whenever the project state changes.

---

## Confirmed

### Source App
- **Health Auto Export (HAE)** is the iOS app used to extract Apple Health data and send it via HTTP webhook as JSON.
- HAE is confirmed to support scheduled daily exports.
- HAE payload structure is nested JSON; some metric types (e.g., sleep analysis) contain arrays of sub-objects.

### Confirmed Source Metrics (Raw HAE Field Names)
These fields have been identified in HAE output and are mapped to v1 internal fields:

| Raw HAE Metric Name | Payload Field Used |
|---|---|
| `heart_rate_variability` | `data[].qty` (ms) |
| `resting_heart_rate` | `data[].qty` (bpm) |
| `respiratory_rate` | `data[].qty` (count/min) |
| `apple_sleeping_wrist_temperature` | `data[].qty` |
| `blood_oxygen_saturation` | `data[].qty` (%) |
| `heart_rate` | `Avg`, `Min`, `Max` (capitalization confirmed from thread testing; needs real-sample verification) |
| `sleep_analysis` | `deep`, `rem`, `awake`, `sleepStart`, `sleepEnd` (key names assumed; needs real-sample verification) |

Top-level payload structure confirmed from thread testing: `data.metrics[]` array.

### Confirmed Target
- **Notion** is the confirmed destination database.
- One row per calendar day is the target write pattern.
- The Notion integration API will be used (not native Notion automations).

### Confirmed Notion Database
**The Notion database already exists and is substantially built.**

- Database name: Daily Health Metrics
- Database ID: `339d7cd8-531f-819f-85b2-c769696ea27c`
- Database URL: `https://www.notion.so/339d7cd8531f819f85b2c769696ea27c`
- Parent page ID: `339d7cd8-531f-800b-b02d-efefaa086bf5` (Cornflower Health)

The database contains approximately 67 properties including all v1 HAE-sourced fields, manual entry fields, formula fields (10 flag formulas, `sleep_efficiency_pct`, `hr_dip_pct`, `hr_dip_category`, `day_of_week`), rolling baseline fields, and the full workout and stimulant protocol layers.

See [`schema-plan.md`](schema-plan.md) for the complete authoritative field list.

### Confirmed v1 Internal Fields
See [`source-payload-map.md`](source-payload-map.md) for the full mapping table.

---

## Notion Database Audit Findings (2026-04-06)

The database was audited on 2026-04-06 against `schema-plan.md`. Key findings:

### Field Name Discrepancies (Schema Plan vs. Actual Notion)

| Original schema-plan.md Name | Actual Notion Field Name | Action |
|---|---|---|
| `health_date` | `date` | Backend must use `date` |
| `hrv_sdnn_msc` | `hrv_sdnn_ms` | Typo corrected in Notion |
| `resp_rate_bpm` | `resp_rate_brpm` | Suffix differs; use `resp_rate_brpm` |
| `wrist_temp_absc` | `wrist_temp_abs` | Typo corrected in Notion |
| `sleep_total_min` | `sleep_time_asleep_min` | Name differs; use `sleep_time_asleep_min` |
| `sleep_start` (datetime) | `sleep_bedtime` (text) | Type changed; use text |
| `sleep_end` (datetime) | `sleep_waketime` (text) | Type changed; use text |
| `ingest_timestamp` | `created_time` (system field) | Replaced by auto-managed system field |

### Fields in v1 Plan Missing From Notion
The following original v1 fields were not found in the deployed database and must be added:

- `hr_day_min_bpm` — add via API PATCH
- `hr_day_max_bpm` — add via API PATCH
- `sleep_core_min` — add via API PATCH

### Phase 2 Fields Already Deployed
The following fields were listed as Phase 2/future in the original schema plan but are already present in the Notion database:

- `hr_sleep_avg_bpm`, `hr_sleep_min_bpm` — present; HAE source not yet confirmed
- `hr_dip_pct`, `hr_dip_category` — formula fields, confirmed deployed
- `sleep_awakenings_count`, `sleep_longest_wake_min` — present; HAE source not yet confirmed
- `wrist_temp_delta` — present; computation logic not yet implemented

### Net-New Fields (Not in Any Prior Schema Plan)
The deployed database contains several layers of fields that were never in the original schema plan:

- Full stimulant protocol layer: `booster_status`, `booster_decision`
- Symptom tracking: `morning_heaviness`, `afternoon_crash`, `fatigue_level`, `stress_context`
- Full workout layer: `workout_type`, `workout_rest_day`, `workout_total_min`, `workout_exertion_felt`, `workout_z2_min`, `workout_z3_min`, `workout_z4_min`, `workout_summary`
- Rolling baselines: `hrv_baseline_60d_ms`, `rhr_baseline_60d_bpm`, `hrv_7d_avg_ms`, `rhr_7d_avg_bpm`, `deep_sleep_7d_avg_min`, `hr_dip_7d_avg_pct`
- `recovery_score` (number field for coaching layer output)
- `spo2_min_pct` (nightly minimum SpO2, separate from average)
- `sleep_waketime_num` (numeric wake time for formula use)
- Subjective fields: `energy_1_5`, `day_quality_1_5`, `meds_notes`

---

## What Has Failed

### Make.com Integration
- **Attempted:** Using Make.com as the middleware layer to receive HAE webhooks, parse nested JSON, and write to Notion.
- **Failures:**
  - Make's JSON parser required manual iterator configuration for nested arrays (e.g., sleep stage breakdown).
  - Expression syntax errors were difficult to debug within the Make UI.
  - No reliable way to handle conditional field presence (some metrics may be absent on a given day).
  - Context about the HAE payload structure was lost between AI-assisted sessions, requiring repeated re-explanation.
  - The scenario became fragile enough that a payload format change would likely break it silently.
- **Conclusion:** Make.com is not the preferred long-term solution. A lightweight backend is a better fit. Do not re-propose Make.com.

### Claude Projects as Log Storage
- **Attempted:** Using Claude Projects to store daily health data and provide continuity across sessions.
- **Finding:** Claude Projects uses RAG-based retrieval, not structured storage. It cannot serve as a queryable database or a reliable daily log.
- **Conclusion:** Notion is the correct destination. Claude Projects is the coaching interface, not the storage layer.

---

## Decisions Made

1. **Move away from Make.com** for the core ingestion pipeline. A backend-first architecture is preferred.
2. **One row per calendar day** in Notion. The `date` field is the deduplication key.
3. **Normalize all field names** to snake_case internal names before writing to Notion. Do not write raw HAE field names as Notion property keys.
4. **Defer certain fields** until v1 is stable. See [`schema-plan.md`](schema-plan.md) for current status of all fields.
5. **Historical backfill is a first-class phase**, not an afterthought. It will be planned and executed deliberately.
6. **This repository is the authoritative project memory.** Future AI threads must read it before generating new work.
7. **JSON export preferred over CSV** for backfill (provisional — confirm after test export).
8. **The Notion database already exists** — do not create a new one. The database `339d7cd8-531f-819f-85b2-c769696ea27c` is the target.

---

## What Remains Uncertain

| Item | Status | Notes |
|---|---|---|
| Backend hosting environment | Undecided | Options: local Python, Vercel/Railway serverless, Fly.io, or VPS |
| HAE exact payload structure | **Confirmed — 2026-04-06** | Real payload captured in `samples/hae_sample_2026-04-05.json`. All field names, units, and nesting verified. |
| HAE sleep-window HR segmentation | **Confirmed absent** | HAE does not segment heart rate by sleep window. `hr_sleep_avg_bpm` must be populated manually (from Bevel/Athlytic) or not at all. |
| HAE awakening sub-events | **Confirmed absent** | HAE does not expose individual awakening events. `sleep_awakenings_count` and `sleep_longest_wake_min` are manual-only fields. |
| Wrist temperature unit | **Confirmed — degF** | `apple_sleeping_wrist_temperature` is in degrees Fahrenheit. No conversion needed at ingest. |
| SpO2 unit normalization | **Confirmed — no conversion needed** | `blood_oxygen_saturation` is already in percent (91–93 range in sample). Do NOT multiply by 100. |
| Exact Notion formula expressions | Partially recovered | Several flag formulas exist in Notion but exact expressions not captured in docs. See `notion-api-notes.md` |
| Rolling baseline computation logic | Not designed | 7d and 60d rolling averages for HRV, RHR, deep sleep need implementation design |

---

## Known Gaps

- ~~No sample HAE JSON payload has been saved~~ — **Resolved 2026-04-06.** Real payload saved to `samples/hae_sample_2026-04-05.json`.
- No backend endpoint exists yet (not even a logging stub).
- Three v1 fields from the original schema plan are missing from the Notion database: `hr_day_min_bpm`, `hr_day_max_bpm`, `sleep_core_min`.
- Exact formula expressions for 8 of 10 flag formulas are not documented (they exist in Notion but were not captured in the repo during database creation).
- The Notion integration token seen in thread reports is likely compromised. Regenerate before any further API use.

---

*Last updated: 2026-04-06 — Updated with Notion database audit results (P3 from integration report). Corrected "Known Gaps" to reflect that the database exists. Added audit findings section.*
