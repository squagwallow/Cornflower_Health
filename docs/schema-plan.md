# Schema Plan

This document defines the canonical internal schema for the health data backend and the corresponding Notion database property layout.

The schema is the single source of truth for field names, types, and constraints. Both the backend normalization logic and the Notion database configuration must conform to it.

---

## Design Principles

1. **One row per calendar day.** The `health_date` field is the primary key for deduplication.
2. **All field names are internal normalized names.** Raw HAE field names are never written to Notion.
3. **Numeric fields store the processed scalar.** Units are encoded in the field name suffix; they are not stored as separate fields.
4. **Null is acceptable.** If a metric was not recorded on a given day, the field is left null. The backend must not reject a row because optional fields are missing.
5. **Datetime fields use ISO 8601.** Timezone must be explicit or UTC-normalized.
6. **Source tracking is always written.** Every row includes `source_tags` to distinguish live webhook rows from backfill rows.

---

## v1 Schema (Phase 1 — Supported Now)

### Notion Property Types

| Internal Field Name | Notion Property Type | Constraints / Notes |
|---|---|---|
| `health_date` | Date | Required. Primary deduplication key. Format: `YYYY-MM-DD`. |
| `hrv_sdnn_ms` | Number | Nullable. SDNN in milliseconds. |
| `rhr_bpm` | Number | Nullable. Resting heart rate in bpm. |
| `resp_rate_brpm` | Number | Nullable. Respiratory rate in breaths/min. |
| `wrist_temp_abs` | Number | Nullable. Absolute nightly wrist temperature. **Unit (°C or °F) must be confirmed before writing.** |
| `spo2_avg_pct` | Number | Nullable. Stored as percentage (0–100), not decimal (0–1). Normalize at ingest if HAE sends decimal. |
| `hr_day_avg_bpm` | Number | Nullable. |
| `hr_day_min_bpm` | Number | Nullable. |
| `hr_day_max_bpm` | Number | Nullable. |
| `sleep_total_min` | Number | Nullable. Total sleep in minutes. |
| `sleep_deep_min` | Number | Nullable. |
| `sleep_rem_min` | Number | Nullable. |
| `sleep_core_min` | Number | Nullable. |
| `sleep_awake_min` | Number | Nullable. Time awake while in bed (minutes). |
| `sleep_start` | Date (with time) | Nullable. ISO 8601. Timezone must be stored or normalized. |
| `sleep_end` | Date (with time) | Nullable. ISO 8601. |
| `source_tags` | Rich Text or Select | Required. Values: `hae_webhook`, `backfill_csv`, `backfill_json`, `manual`. |
| `ingest_timestamp` | Date (with time) | Auto-set at write time. ISO 8601 UTC. Useful for debugging. |

---

## Future Schema Fields (Phase 2+)

These fields are not written in v1. The Notion database may include them as empty columns in preparation, but no backend logic should reference them until they are promoted.

| Internal Field Name | Expected Notion Type | Condition for Promotion |
|---|---|---|
| `hr_sleep_avg_bpm` | Number | HAE sleep-window HR parsing confirmed and tested |
| `hr_sleep_min_bpm` | Number | Same |
| `hr_dip_pct` | Number | `hr_sleep_avg_bpm` is stable and populated |
| `sleep_awakenings_count` | Number | HAE sub-event structure confirmed |
| `sleep_longest_wake_min` | Number | HAE sub-event structure confirmed |
| `wrist_temp_delta` | Number | ≥14 days of `wrist_temp_abs` populated; baseline formula defined |
| `hrv_baseline_7d` | Number | v1 stable; rolling calc logic written |
| `hrv_baseline_30d` | Number | Same |
| `recovery_flag` | Select | Baselines stable; recovery logic defined and reviewed |

---

## Why Future Fields Are Deferred

### Fields dependent on HAE sub-event data
`sleep_awakenings_count` and `sleep_longest_wake_min` require HAE to expose individual awakening events within the sleep analysis payload. It is not confirmed that HAE provides this level of granularity. These fields should only be added once a real payload is captured and the sub-event structure is verified.

### Fields dependent on sleep-window HR segmentation
`hr_sleep_avg_bpm`, `hr_sleep_min_bpm`, and `hr_dip_pct` require isolating heart rate samples that occurred during the sleep window. HAE may or may not support this segmentation. If it does not, these fields would require a separate processing step (e.g., cross-referencing raw HR samples with sleep timestamps).

### Fields dependent on historical baselines
`wrist_temp_delta`, `hrv_baseline_7d`, `hrv_baseline_30d`, and `recovery_flag` require multiple days of clean v1 data before they can be computed. Attempting to compute them before v1 is stable and backfilled would produce meaningless results.

---

## Schema Versioning

When the schema changes, the following must be updated:
- This file (`schema-plan.md`) — promote fields from future to v1 table as appropriate
- [`source-payload-map.md`](source-payload-map.md) — add any new source mappings
- [`decision-log.md`](decision-log.md) — record the change and rationale
- The Notion database — add new property columns
- The backend normalization logic — add parsing and mapping for new fields

Do not rename existing v1 fields without a migration plan. Renames break historical consistency.

---

*Last updated: 2026-04-06*
