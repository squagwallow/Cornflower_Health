# Backfill Plan

This document describes the strategy for loading 6+ months of historical Apple Health data into the Notion database.

Backfill is a first-class phase of this project, not an afterthought. It must be planned and executed with the same rigor as the live ingestion pipeline.

---

## Context

- The user has at least 6 months of Apple Health data on-device.
- This data exists prior to any automated pipeline.
- The historical data must be loaded into the same Notion database as live data, using the same normalized schema.
- Backfill rows must be distinguishable from live rows via `source_tags`.
- Backfill must not overwrite or corrupt live rows that are already written.

---

## Export Method

Health Auto Export (HAE) supports exporting historical data in multiple formats. The export format for backfill must be chosen before writing the backfill script.

| Format | Pros | Cons |
|---|---|---|
| JSON | Closest to the live webhook payload structure; same field names | Larger files; may need to be split by date range |
| CSV | Easier to inspect and debug in a spreadsheet | May flatten nested structures (e.g., sleep stages) differently; field names may differ |

> **Assumption:** JSON export is preferred because it mirrors the live webhook payload structure and allows the same normalization logic to be reused. This must be confirmed once a test export is performed.

**Action:** Perform a test export of 1–2 weeks of data in both formats, inspect the structure, and confirm which format to use for backfill.

---

## Backfill Principles

### 1. Idempotency
The backfill process must be safe to re-run. Running it twice should not create duplicate rows or overwrite correct data.

Implementation:
- Before writing each row, query Notion for an existing page where `health_date` matches the record date.
- If a row exists, skip it (do not update).
- If no row exists, write it.
- Log every skip and write.

### 2. Ordered Processing
Process records in chronological order (oldest first). This ensures that if the process is interrupted, the earliest data is already loaded and the run can be resumed from the last written date.

### 3. Rate Limiting
The Notion API has rate limits (approximately 3 requests per second as of the current API version). Writes must be throttled to stay within limits.

Recommended approach:
- Insert a delay of 300–500ms between writes (approximately 2–3 writes/sec).
- If a 429 (rate limit) response is received, implement exponential backoff before retrying.
- Do not parallelize write operations.

### 4. Source Tagging
All backfill rows must have `source_tags` set to indicate their origin:
- `backfill_json` — loaded from a HAE JSON historical export
- `backfill_csv` — loaded from a HAE CSV historical export
- `hae_webhook` — written by the live daily pipeline

This allows future queries to distinguish backfill data from live data if behavioral differences emerge.

### 5. Logging
The backfill script must produce a log file (not just console output) with:
- Each date processed
- Whether the row was written, skipped (duplicate), or failed
- Any field-level errors (e.g., a field that could not be parsed)
- Total counts at the end: written, skipped, failed

### 6. QA Checks
After backfill is complete, perform the following checks:

| Check | Method |
|---|---|
| Row count | Count rows in Notion; compare to number of days in the backfill range |
| Date coverage | Identify any gaps in `health_date` sequence; investigate missing dates |
| Null field audit | For each v1 field, calculate what percentage of rows have a null value; flag anomalies |
| Spot check | Manually verify 5–10 random rows against the raw HAE export |
| Duplicate check | Query Notion for any `health_date` values that appear more than once |

---

## Backfill Phases

### Phase 0: Preparation
- [ ] Perform a test HAE export (1–2 weeks) and inspect format
- [ ] Confirm export format (JSON preferred)
- [ ] Confirm all v1 field mappings are correct against the test export (update [`source-payload-map.md`](source-payload-map.md) if needed)
- [ ] Ensure the Notion database exists with the v1 schema
- [ ] Ensure the live ingestion pipeline is working (or at least has been tested with a stub endpoint)

### Phase 1: Partial Backfill (Test Run)
- [ ] Export 4 weeks of historical data
- [ ] Run the backfill script against the Notion database
- [ ] Perform QA checks on the 4-week set
- [ ] Fix any issues found before proceeding

### Phase 2: Full Backfill
- [ ] Export all available historical data (6+ months)
- [ ] Run the backfill script
- [ ] Perform full QA checks
- [ ] Log the date range covered and store the log in this repository or a `logs/` folder

### Phase 3: Verify Continuity
- [ ] Confirm that the most recent backfill date and the earliest live webhook date form a contiguous sequence (no gap)
- [ ] If a gap exists, identify the missing dates and fill manually if needed

---

## Known Risks

| Risk | Mitigation |
|---|---|
| HAE historical export format differs from live webhook format | Test export before writing backfill script; do not assume identical field structure |
| Notion API rate limits cause partial run failure | Implement rate limiting and exponential backoff; script must be resumable from last successful date |
| Some historical days have missing metrics | Handle nulls gracefully; do not fail the entire row if one field is absent |
| Duplicate writes if script is run twice | Implement idempotency check before every write |
| Sleep stages absent for older dates | Apple Watch sleep stage tracking was introduced in watchOS 9 (2022); data before that date may lack `deep`, `rem`, `core` fields |

---

*Last updated: 2026-04-06*
