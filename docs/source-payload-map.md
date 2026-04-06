# Source Payload Map

This document maps raw Health Auto Export (HAE) metric names to normalized internal field names used by the backend and stored in Notion.

**Important:** Field names and payload structures marked as "assumed" or "needs verification" must be confirmed against a real captured HAE JSON payload before production use. Save a real payload to `samples/` and update this document.

---

## Mapping Table

### v1 Fields (Supported in Phase 1)

| HAE Metric Name | HAE Payload Key | Internal Field Name | Type | Unit | Notes |
|---|---|---|---|---|---|
| `heart_rate_variability` | `qty` | `hrv_sdnn_ms` | number | ms | SDNN metric; HAE reports as a single daily value |
| `resting_heart_rate` | `qty` | `rhr_bpm` | number | bpm | Single daily value from Apple Health |
| `respiratory_rate` | `qty` | `resp_rate_brpm` | number | breaths/min | Single daily value |
| `apple_sleeping_wrist_temperature` | `qty` | `wrist_temp_abs` | number | °C or °F (TBD) | **Unit must be confirmed from real payload.** Absolute nightly value. Delta (deviation from baseline) is deferred. |
| `blood_oxygen_saturation` | `qty` | `spo2_avg_pct` | number | % | Daily average; HAE may report as decimal (0–1) or percent (0–100); **verify and normalize** |
| `heart_rate` | `Avg` | `hr_day_avg_bpm` | number | bpm | Daily average; field key capitalization (`Avg`) must be verified |
| `heart_rate` | `Min` | `hr_day_min_bpm` | number | bpm | Daily minimum |
| `heart_rate` | `Max` | `hr_day_max_bpm` | number | bpm | Daily maximum |
| `sleep_analysis` | `totalSleep` | `sleep_total_min` | number | minutes | Total sleep duration |
| `sleep_analysis` | `deep` | `sleep_deep_min` | number | minutes | Deep sleep stage |
| `sleep_analysis` | `rem` | `sleep_rem_min` | number | minutes | REM sleep stage |
| `sleep_analysis` | `core` | `sleep_core_min` | number | minutes | Core (light) sleep stage |
| `sleep_analysis` | `awake` | `sleep_awake_min` | number | minutes | Time awake while in bed |
| `sleep_analysis` | `sleepStart` | `sleep_start` | datetime | ISO 8601 | Bedtime / sleep onset |
| `sleep_analysis` | `sleepEnd` | `sleep_end` | datetime | ISO 8601 | Wake time |
| *(derived)* | *(record-level)* | `health_date` | date | YYYY-MM-DD | Calendar date this record represents; derived from `sleepEnd` or device timestamp |
| *(derived)* | *(record-level)* | `source_tags` | string | — | Free-form tag for data source, e.g., `"hae_webhook"` or `"backfill_csv"` |

---

### Future Fields (Phase 2 or Later)

These fields are deferred because they require either additional source data that is not yet confirmed available in HAE, baseline history that does not yet exist, or additional derivation logic.

| Internal Field Name | Depends On | Reason Deferred |
|---|---|---|
| `hr_sleep_avg_bpm` | `heart_rate` during sleep window | HAE may not segment HR by sleep window cleanly; requires verification |
| `hr_sleep_min_bpm` | `heart_rate` during sleep window | Same as above |
| `hr_dip_pct` | `hr_day_avg_bpm`, `hr_sleep_avg_bpm` | Requires sleep HR; formula: `((day_avg - sleep_avg) / day_avg) * 100` |
| `sleep_awakenings_count` | `sleep_analysis` sub-events | HAE may not expose individual awakening events; needs verification |
| `sleep_longest_wake_min` | `sleep_analysis` sub-events | Same as above |
| `wrist_temp_delta` | `wrist_temp_abs` + rolling baseline | Requires ≥14 days of baseline history before meaningful delta can be computed |
| `hrv_baseline_7d` | `hrv_sdnn_ms` history | Rolling baseline; requires v1 to be stable and populated |
| `hrv_baseline_30d` | `hrv_sdnn_ms` history | Same |
| `recovery_flag` | Multiple fields + baselines | Category or score derived from HRV, RHR, sleep; deferred until baselines are stable |

---

## Notes on HAE Payload Structure

- HAE sends data as JSON via HTTP POST to a configured webhook URL.
- The top-level structure is a dictionary keyed by metric name.
- For metrics with a single daily value (HRV, RHR, respiratory rate, SpO2, wrist temp), the value is typically nested under a `data` array with a `qty` field.
- For `heart_rate`, the payload likely contains `Avg`, `Min`, and `Max` sub-keys — **capitalization must be verified against a real payload sample.**
- For `sleep_analysis`, the structure is more complex and may contain an array of sleep session objects, each with stage breakdowns. The exact nesting depth must be verified.
- **Action required:** Capture a real HAE payload and save it to `samples/hae_sample_YYYY-MM-DD.json`. Update this document with verified field paths.

---

## Field Naming Conventions

Internal field names follow these rules:
- `snake_case` throughout
- Metric category prefix where helpful (`sleep_`, `hr_`, `hrv_`, `resp_`, `spo2_`, `wrist_`)
- Unit suffix for numeric fields (`_ms`, `_bpm`, `_min`, `_pct`)
- No raw HAE field names are exposed in the Notion schema

---

*Last updated: 2026-04-06*
