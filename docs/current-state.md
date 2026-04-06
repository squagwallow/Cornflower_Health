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

| Raw HAE Metric Name              | Payload Field Used      |
|----------------------------------|-------------------------|
| `heart_rate_variability`         | `qty` (ms)              |
| `resting_heart_rate`             | `qty` (bpm)             |
| `respiratory_rate`               | `qty` (count/min)       |
| `apple_sleeping_wrist_temperature` | `qty`                 |
| `blood_oxygen_saturation`        | `qty` (%)               |
| `heart_rate`                     | `Avg`, `Min`, `Max`     |
| `sleep_analysis`                 | `totalSleep`, `deep`, `rem`, `core`, `awake`, `sleepStart`, `sleepEnd` |

### Confirmed Target
- **Notion** is the confirmed destination database.
- One row per calendar day is the target write pattern.
- The Notion integration API will be used (not native Notion automations).

### Confirmed v1 Internal Fields
See [`source-payload-map.md`](source-payload-map.md) for the full mapping table.

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
- **Conclusion:** Make.com is not the preferred long-term solution. A lightweight backend is a better fit.

---

## Decisions Made

1. **Move away from Make.com** for the core ingestion pipeline. A backend-first architecture is preferred.
2. **One row per calendar day** in Notion. Date is the deduplication key.
3. **Normalize all field names** to snake_case internal names before writing to Notion. Do not write raw HAE field names as Notion property keys.
4. **Defer deferred fields** (e.g., HR during sleep, wrist temp delta, rolling baselines) until v1 is stable. See [`schema-plan.md`](schema-plan.md).
5. **Historical backfill is a first-class phase**, not an afterthought. It will be planned and executed deliberately.
6. **This repository is the authoritative project memory.** Future AI threads must read it before generating new work.

---

## What Remains Uncertain

| Item | Status | Notes |
|------|--------|-------|
| Backend hosting environment | Undecided | Options include local (e.g., Python/Flask on Mac), cloud function (e.g., Vercel, Railway, Fly.io), or containerized service |
| HAE exact payload structure | Partially confirmed | Raw field names are confirmed; full nested structure (especially sleep stages) needs a real captured sample to verify |
| Notion database property types | Not finalized | Need to confirm which Notion property types map to each v1 field (number, date, rich text, etc.) |
| HAE export format for backfill | Undecided | HAE supports CSV and JSON export; which format is more tractable for batch processing is not confirmed |
| `sleep_analysis` sub-field structure | Partially confirmed | Field names (`deep`, `rem`, `core`, etc.) are expected but must be verified against a real HAE payload |
| Whether HAE sends one record per day or multiple | Not confirmed | HRV and RHR may average to one value, but `heart_rate` may include multiple samples; ingestion logic must handle both cases |
| Wrist temperature unit | Not confirmed | `qty` is confirmed but absolute vs. relative (delta) unit is unclear without a real sample |

---

## Known Gaps

- No sample HAE JSON payload has been saved to this repository yet. This is the highest-priority gap.
- No backend endpoint exists yet (not even a logging stub).
- No Notion database has been created with the v1 schema yet.

---

*Last updated: 2026-04-06*
