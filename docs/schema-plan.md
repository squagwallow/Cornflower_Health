# Schema Plan

This document defines the canonical internal schema for the health data backend and the corresponding Notion database property layout.

The schema is the single source of truth for field names, types, and constraints. Both the backend normalization logic and the Notion database configuration must conform to it.

> **Important — audit finding (2026-04-06):** The Notion database (`339d7cd8-531f-819f-85b2-c769696ea27c`) already exists and was built substantially beyond the v1 set described at repo creation. Several field names in the existing database differ from the names listed in the original `schema-plan.md`. This document has been updated to reflect the actual deployed field names as authoritative. Where discrepancies were found, the Notion field name is treated as the canonical name and the backend must be written to match it. See the discrepancy table below.

---

## Design Principles

1. **One row per calendar day.** The `date` field is the primary key for deduplication.
2. **All field names are internal normalized names.** Raw HAE field names are never written to Notion.
3. **Numeric fields store the processed scalar.** Units are encoded in the field name suffix; they are not stored as separate fields.
4. **Null is acceptable.** If a metric was not recorded on a given day, the field is left null. The backend must not reject a row because optional fields are missing.
5. **Datetime fields use ISO 8601.** Timezone must be explicit or UTC-normalized.
6. **Source tracking is always written.** Every row includes `source_tags` to distinguish live webhook rows from backfill rows.

---

## Field Name Discrepancies: Original Plan vs. Actual Notion Database

The following discrepancies were found during the 2026-04-06 audit. The Notion field name is the canonical name going forward.

| Original schema-plan.md Name | Actual Notion Field Name | Discrepancy |
|---|---|---|
| `health_date` | `date` | Different name — use `date` |
| `hrv_sdnn_msc` | `hrv_sdnn_ms` | Typo in original (extra `c`) — use `hrv_sdnn_ms` |
| `resp_rate_bpm` | `resp_rate_brpm` | Different suffix — use `resp_rate_brpm` |
| `wrist_temp_absc` | `wrist_temp_abs` | Typo in original (extra `c`) — use `wrist_temp_abs` |
| `sleep_total_min` | `sleep_time_asleep_min` | Different name — use `sleep_time_asleep_min` |
| `sleep_start` (Date w/ time) | `sleep_bedtime` (Text) | Type changed to text in DB — use `sleep_bedtime` as text |
| `sleep_end` (Date w/ time) | `sleep_waketime` (Text) | Type changed to text in DB — use `sleep_waketime` as text |
| `ingest_timestamp` | `created_time` | Replaced by system-managed `created_time` auto-field |
| `source_tags` (Rich Text) | `source_tags` (Multi-select) | Type changed; options: Apple Health, Manual, Bevel, Athlytic |

---

## v1 Schema — Deployed Fields (HAE-Sourced)

These fields are sourced from the HAE webhook payload. The backend normalization layer must write these on every daily ingest.

| Notion Field Name | Notion Property Type | Constraints / Notes |
|---|---|---|
| `date` | Date | Required. Primary deduplication key. Format: `YYYY-MM-DD`. |
| `hrv_sdnn_ms` | Number | Nullable. SDNN in milliseconds. |
| `rhr_bpm` | Number | Nullable. Resting heart rate in bpm. |
| `resp_rate_brpm` | Number | Nullable. Respiratory rate in breaths/min. |
| `wrist_temp_abs` | Number | Nullable. Absolute nightly wrist temperature. **Unit (°C or °F) must be confirmed from real payload.** |
| `spo2_avg_pct` | Number (percent format) | Nullable. Stored as percent (0–100). Normalize at ingest if HAE sends decimal. |
| `spo2_min_pct` | Number | Nullable. Nightly minimum SpO2. Separate from average. |
| `hr_day_avg_bpm` | Number | Nullable. |
| `hr_sleep_avg_bpm` | Number | Nullable. See Phase 2 note below — field exists but source not confirmed. |
| `hr_sleep_min_bpm` | Number | Nullable. Same caveat as above. |
| `sleep_time_asleep_min` | Number | Nullable. Total sleep in minutes. |
| `sleep_time_in_bed_min` | Number | Nullable. Required for `sleep_efficiency_pct` formula. |
| `sleep_deep_min` | Number | Nullable. |
| `sleep_rem_min` | Number | Nullable. |
| `sleep_awake_min` | Number | Nullable. Time awake while in bed (minutes). |
| `sleep_awakenings_count` | Number | Nullable. See Phase 2 note — field exists but source not confirmed. |
| `sleep_longest_wake_min` | Number | Nullable. See Phase 2 note. |
| `sleep_bedtime` | Text | Nullable. Stored as text (e.g., "11:30 PM"). Datetime parsing deferred. |
| `sleep_waketime` | Text | Nullable. Stored as text (e.g., "6:45 AM"). |
| `sleep_waketime_num` | Number | Nullable. Wake time as minutes after midnight (for formula use). E.g., 6:00 AM = 360. |
| `source_tags` | Multi-select | Required. Options: `Apple Health`, `Manual`, `Bevel`, `Athlytic`. |

---

## v1 Schema — Manually-Entered Fields

These fields have no automated source. They are entered manually by the user each day.

| Notion Field Name | Notion Property Type | Constraints / Notes |
|---|---|---|
| `energy_1_5` | Number | Subjective energy rating 1–5. Null if not entered. |
| `day_quality_1_5` | Number | Subjective day quality 1–5. Null if not entered. |
| `meds_notes` | Rich Text | Free-text medication notes. |
| `morning_heaviness` | Checkbox | Manual flag: morning heaviness or grogginess. |
| `afternoon_crash` | Checkbox | Manual flag: afternoon energy crash. |
| `stress_context` | Select | Options: Low / Moderate / High / Extreme. |
| `fatigue_level` | Select | Options: Low / Moderate / High / Extreme. |
| `notes` | Rich Text | General free-text notes. |
| `booster_status` | Select | Options: Baseline only (60mg) / First only (5mg) / Both doses (5+5mg) / Skipped. |
| `booster_decision` | Select | Options: 🟢 Green light / ⚠️ Borderline – first only / 🔴 Recovery day – skip. |
| `workout_rest_day` | Checkbox | True if rest day; no workout logged. |
| `workout_type` | Multi-select | Options: Walk, Strength, HIIT, Cycle, Swim, Rest, Other. |
| `workout_total_min` | Number | Total workout duration in minutes. |
| `workout_exertion_felt` | Select | Options: Low / Moderate / High. |
| `workout_z2_min` | Number | Zone 2 duration in minutes. |
| `workout_z3_min` | Number | Zone 3 duration in minutes. |
| `workout_z4_min` | Number | Zone 4 duration in minutes. |
| `workout_summary` | Rich Text | Free-text workout description. |
| `recovery_score` | Number | Manually entered or LLM-computed recovery score (0–100). See `coaching-layer.md`. |

---

## v1 Schema — Formula Fields

These fields are computed by Notion formulas. They require no backend write — they auto-compute from the fields above. See `notion-api-notes.md` for exact formula expressions and the formula-referencing-formula limitation.

| Notion Field Name | Formula Summary | Depends On |
|---|---|---|
| `sleep_efficiency_pct` | `round((sleep_time_asleep_min / sleep_time_in_bed_min) * 100)` | `sleep_time_asleep_min`, `sleep_time_in_bed_min` |
| `hr_dip_pct` | `round(((hr_day_avg_bpm - hr_sleep_avg_bpm) / hr_day_avg_bpm) * 100)` | `hr_day_avg_bpm`, `hr_sleep_avg_bpm` |
| `hr_dip_category` | Inline: Normal / Borderline / Non-dipping | `hr_day_avg_bpm`, `hr_sleep_avg_bpm` |
| `day_of_week` | `formatDate(date, "dddd")` | `date` |
| `flag_deep_sleep_low` | `sleep_deep_min < 35` | `sleep_deep_min` |
| `flag_deep_gate_50` | `sleep_deep_min < 50` | `sleep_deep_min` |
| `flag_rhr_elevated` | `rhr_bpm > 68` | `rhr_bpm` |
| `flag_hrv_very_low` | `hrv_sdnn_ms < 40` | `hrv_sdnn_ms` |
| `flag_recovery_red_gate` | `hrv_sdnn_ms < 40 AND sleep_deep_min < 35` | `hrv_sdnn_ms`, `sleep_deep_min` |
| `flag_resp_rate_high` | `resp_rate_brpm >= 19` | `resp_rate_brpm` |
| `flag_spo2_low` | `spo2_avg_pct < 92` (threshold TBC — see unit note) | `spo2_avg_pct` |
| `flag_sleep_fragmented` | `sleep_awakenings_count >= 4 OR sleep_awake_min >= 60` | `sleep_awakenings_count`, `sleep_awake_min` |
| `flag_early_wake` | `sleep_waketime_num > 0 AND sleep_waketime_num <= 300` | `sleep_waketime_num` |

**Note on exact formula expressions:** Several flag formulas above are "probable" definitions reconstructed from threshold documentation in deprecated thread reports. They are implemented in Notion but exact expressions were not captured. A coding task exists to retrieve the actual deployed formula code. See `coding-session-prompts.md`.

---

## v1 Schema — Rolling Baseline Fields

These fields exist in the Notion database but are currently empty. They are intended for rolling averages and baselines. Population logic has not been implemented.

| Notion Field Name | Type | When Populated |
|---|---|---|
| `hrv_7d_avg_ms` | Number | After 7 days of clean `hrv_sdnn_ms` data |
| `rhr_7d_avg_bpm` | Number | After 7 days of clean `rhr_bpm` data |
| `deep_sleep_7d_avg_min` | Number | After 7 days of clean `sleep_deep_min` data |
| `hr_dip_7d_avg_pct` | Number | After 7 days of clean `hr_dip_pct` data |
| `hrv_baseline_60d_ms` | Number | After 60 days, or set manually from Athlytic/Bevel |
| `rhr_baseline_60d_bpm` | Number | After 60 days, or set manually |

---

## Fields Missing From the Actual Notion Database

The following fields from the original `schema-plan.md` v1 were NOT found in the deployed Notion database. They need to be added via API PATCH before the backend can write them.

| Field | Original Type | Action Required |
|---|---|---|
| `hr_day_min_bpm` | Number | Add via PATCH |
| `hr_day_max_bpm` | Number | Add via PATCH |
| `sleep_core_min` | Number (Core/light sleep stage) | Add via PATCH |
| `wrist_temp_delta` | Number | Already added — confirmed present in DB |

> **Note:** `wrist_temp_delta` is present in the DB. Only `hr_day_min_bpm`, `hr_day_max_bpm`, and `sleep_core_min` are genuinely missing.

---

## Conditional Phase 2 Fields — HR Sleep Segmentation

The following fields are in the Notion database but depend on HAE exposing heart rate samples segmented by sleep window. This is **not yet confirmed from a real payload sample**.

- `hr_sleep_avg_bpm`
- `hr_sleep_min_bpm`
- `hr_dip_pct` (formula)
- `hr_dip_category` (formula)

**Investigation required:** Capture a real HAE payload and verify whether `heart_rate` samples include a sleep-window segment. If not, these fields must be populated via alternative means (manual entry from Bevel/Athlytic, or cross-referencing raw HR samples with sleep timestamps). Update this section after investigation.

---

## Schema Versioning

When the schema changes, the following must be updated:
- This file (`schema-plan.md`) — promote fields as appropriate
- [`source-payload-map.md`](source-payload-map.md) — add any new source mappings
- [`decision-log.md`](decision-log.md) — record the change and rationale
- The Notion database — add new property columns via API PATCH (see `notion-api-notes.md`)
- The backend normalization logic — add parsing and mapping for new fields

Do not rename existing deployed fields without a migration plan.

---

*Last updated: 2026-04-06 — Substantially revised based on Notion database audit. Previous version underrepresented deployed schema.*
