# Coding Session Prompts

This file collects every required coding task for the Cornflower Health project, grouped by implementation phase. Each entry is written as a self-contained prompt for a focused coding session.

**Instructions for use:**
- Read `docs/runbook.md` and `docs/current-state.md` before starting any session.
- Use the exact field names from `docs/schema-plan.md` (not names from earlier deprecated thread reports).
- Do not start a Phase 2 task until all Phase 1 tasks are complete and verified in production.
- Save every HAE payload sample to `samples/` before the normalization layer session.

---

## Phase 0 — Pre-Coding: Payload Capture and Schema Verification

> These tasks are not coding tasks but are prerequisites for all Phase 1 coding. They must be completed before writing any normalization or Notion write logic.

### Task 0.1 — Capture a Real HAE JSON Payload ✅ COMPLETE

**Completed 2026-04-06.** Real payload saved to `samples/hae_sample_2026-04-05.json`. All field names, units, and structure verified. `source-payload-map.md` fully updated.

Key findings:
- Outer wrapper is an array: `payload[0]["data"]["metrics"]`
- `sleep_analysis` values are in **hours** — multiply by 60
- `blood_oxygen_saturation` is already in percent — no conversion
- `wrist_temp` is in `degF` — no conversion
- `heart_rate` uses capital `Avg`, `Min`, `Max`
- `hr_sleep_avg_bpm`, `spo2_min_pct`, `sleep_awakenings_count` are **not available in HAE** — manual only
- `inBed` and `asleep` keys in `sleep_analysis` are always `0` — derive `sleep_time_in_bed_min` from `inBedStart`/`inBedEnd` timestamps instead

**This task is no longer blocking.**

---

### Task 0.2 — Retrieve and Document Deployed Notion Formula Expressions

**Objective:** Extract the exact formula code for all formula properties in the Notion database and add them to `docs/notion-api-notes.md`.

**Prompt for coding session:**

```
Using the Notion API, query the database schema for database ID 339d7cd8-531f-819f-85b2-c769696ea27c.
For each property where "type" == "formula", retrieve the full "formula.expression" string.

The target formula properties are:
- sleep_efficiency_pct
- hr_dip_pct
- hr_dip_category
- day_of_week
- flag_deep_sleep_low
- flag_deep_gate_50
- flag_rhr_elevated
- flag_hrv_very_low
- flag_recovery_red_gate
- flag_resp_rate_high
- flag_spo2_low
- flag_sleep_fragmented
- flag_early_wake

Save the complete expression for each formula property to docs/notion-api-notes.md under the section
"Confirmed Working Formula Definitions". Replace any "Status: needs verification" notes with the 
confirmed expression.

API endpoint: GET /v1/databases/339d7cd8-531f-819f-85b2-c769696ea27c
Auth: Bearer $NOTION_TOKEN
Notion-Version: 2022-06-28
```

**Output:** Updated `docs/notion-api-notes.md` with exact formula expressions.

**Blocks:** Writing correct formula fields in future PATCH requests.

---

### Task 0.3 — Add Three Missing v1 Fields to Notion Database

**Objective:** Add `hr_day_min_bpm`, `hr_day_max_bpm`, and `sleep_core_min` to the existing Notion database via API PATCH.

**Prompt for coding session:**

```
Using the Notion API, add the following three Number properties to the existing database
339d7cd8-531f-819f-85b2-c769696ea27c via PATCH /v1/databases/{id}.

Properties to add:
1. hr_day_min_bpm — type: number, number_format: "number"
2. hr_day_max_bpm — type: number, number_format: "number"
3. sleep_core_min  — type: number, number_format: "number"

Send each as a separate PATCH request (do not combine in one request to avoid partial-application issues).
Write the JSON payload to a file before sending. Do NOT use inline JSON in the curl command.

Auth: Bearer $NOTION_TOKEN
Notion-Version: 2022-06-28
```

**Output:** Three new properties visible in the Notion database schema.

**Blocks:** Backend normalization layer for heart rate min/max and core sleep.

---

## Phase 1 — Core Backend Pipeline

> All Phase 1 tasks require Task 0.1 (real payload sample) to be complete. Tasks 1.1–1.4 can be developed in parallel once 0.1 is done.

### Task 1.1 — Backend: Webhook Endpoint (Logging Stub)

**Prompt for coding session:**

```
Build a minimal HTTP server that:
1. Listens for POST requests at /webhook on port $BACKEND_PORT (default 8000)
2. Validates the request includes the shared secret from $HAE_WEBHOOK_SECRET in a request header
   (reject with 401 if missing or invalid)
3. Logs the raw request body (JSON) to a timestamped file in logs/ directory
4. Returns HTTP 200 {"status": "received"} on success
5. Returns HTTP 400 with a brief error message on malformed JSON

Language: Python with FastAPI (preferred) or Flask
Environment variables: load from .env using python-dotenv
Auth: read NOTION_TOKEN, NOTION_DATABASE_ID, HAE_WEBHOOK_SECRET, BACKEND_PORT, LOG_LEVEL from env

Do not write any Notion integration in this task. This is a logging stub only.
The goal is to confirm HAE can reach the endpoint and that the raw payload is captured correctly.

Save the implementation to src/webhook.py (or equivalent module structure).
```

**Output:** Running local server that accepts HAE webhooks and logs raw payloads.

**Blocks:** Tasks 1.2, 1.3.

---

### Task 1.2 — Backend: HAE Payload Normalization Layer

**Prompt for coding session:**

```
Write a Python module that accepts a raw HAE webhook payload and returns a normalized
record (dict) with Notion field names as keys.

Reference files to read first:
- docs/source-payload-map.md        (all field mappings, verified from real payload)
- docs/schema-plan.md               (canonical field names and Notion types)
- samples/hae_sample_2026-04-05.json  (real payload — use for all verification)


## PAYLOAD STRUCTURE (verified)

The payload is a JSON array. Index [0] to get the data object:
  payload[0]["data"]["metrics"]  →  list of metric dicts

Each metric dict:
  { "name": str, "units": str, "data": [ { "date": str, "qty": float, "source": str }, ... ] }

Build a lookup dict first for efficient access:
  metrics = { m["name"]: m["data"] for m in payload[0]["data"]["metrics"] }

To find today's record for a metric, match on the date string prefix (YYYY-MM-DD).


## FIELD MAPPINGS (all verified from real payload)

### Scalar metrics — access via data[date_match]["qty"]
  heart_rate_variability  → hrv_sdnn_ms         (ms, no conversion)
  resting_heart_rate      → rhr_bpm             (count/min = bpm, no conversion)
  respiratory_rate        → resp_rate_brpm      (count/min, no conversion)
  blood_oxygen_saturation → spo2_avg_pct        (%, already in percent — DO NOT multiply by 100)
  apple_sleeping_wrist_temperature → wrist_temp_abs  (degF — DO NOT convert to Celsius)

### Heart rate — access via data[date_match]["Avg"]/["Min"]/["Max"] (CAPITAL letters confirmed)
  heart_rate["Avg"]  → hr_day_avg_bpm
  heart_rate["Min"]  → hr_day_min_bpm   (note: may be float, e.g. 48.409 — round to int)
  heart_rate["Max"]  → hr_day_max_bpm

### Sleep analysis — UNITS ARE HOURS, multiply by 60 for minutes
  sleep_analysis["totalSleep"]  → sleep_time_asleep_min   (hours * 60)
  sleep_analysis["deep"]        → sleep_deep_min           (hours * 60)
  sleep_analysis["rem"]         → sleep_rem_min            (hours * 60)
  sleep_analysis["core"]        → sleep_core_min           (hours * 60)
  sleep_analysis["awake"]       → sleep_awake_min          (hours * 60)

  sleep_analysis["sleepStart"]  → sleep_bedtime            (store as text string as-is)
  sleep_analysis["sleepEnd"]    → sleep_waketime           (store as text string as-is)

  IMPORTANT: sleep_analysis["inBed"] is always 0 — do NOT use it.
  Compute sleep_time_in_bed_min from timestamps instead:
    from datetime import datetime
    fmt = "%Y-%m-%d %H:%M:%S %z"
    in_bed_min = (datetime.strptime(record["inBedEnd"], fmt) -
                  datetime.strptime(record["inBedStart"], fmt)).total_seconds() / 60

  Compute sleep_waketime_num from sleepEnd local time:
    wake_dt = datetime.strptime(record["sleepEnd"], fmt)
    sleep_waketime_num = wake_dt.hour * 60 + wake_dt.minute


## DERIVED FIELDS
  date:         parse from sleep_analysis record["date"] → YYYY-MM-DD prefix
                  record["date"].split(" ")[0]
  source_tags:  always ["Apple Health"] for live webhook rows


## DO NOT POPULATE (manual or computed fields — leave as None)
  hr_sleep_avg_bpm, hr_sleep_min_bpm  — HAE does not provide sleep-window HR
  spo2_min_pct                        — HAE only provides daily average, not nightly min
  sleep_awakenings_count              — HAE does not expose awakening sub-events
  sleep_longest_wake_min              — same
  hrv_baseline_60d_ms, rhr_baseline_60d_bpm, hrv_7d_avg_ms, rhr_7d_avg_bpm,
  deep_sleep_7d_avg_min, hr_dip_7d_avg_pct, recovery_score — all manual or Phase 3
  All booster_*, workout_*, stress_context, fatigue_level, morning_heaviness,
  afternoon_crash, energy_1_5, day_quality_1_5, meds_notes, notes — manual only


## OTHER REQUIREMENTS
- If any field is absent from the payload for a given date, set the normalized value to None
- Do not raise exceptions on missing fields
- Round all minute values to nearest integer after hours→minutes conversion
- Round hr_day_min_bpm and hr_day_max_bpm to nearest integer
- Write unit tests using samples/hae_sample_2026-04-05.json:
    Test the April 5 record specifically:
      hrv_sdnn_ms = 44.059 (round to 2 decimal places max)
      rhr_bpm = 67.5
      hr_day_avg_bpm = 87.049
      sleep_deep_min = round(0.477 * 60) = 29 min
      sleep_time_asleep_min = round(6.537 * 60) = 392 min
      wrist_temp_abs = 99.426 (degF)
      spo2_avg_pct = 92.6 (no conversion)

Save to src/normalize.py
```

**Output:** `src/normalize.py` with unit tests.

**Blocks:** Task 1.3.

---

### Task 1.3 — Backend: Notion Write Layer

**Prompt for coding session:**

```
Write a Python module that accepts a normalized record (output of normalize.py) and writes it
to the existing Notion database 339d7cd8-531f-819f-85b2-c769696ea27c.

Reference files to read first:
- docs/schema-plan.md         (field types for each Notion property)
- docs/notion-api-notes.md    (Notion API patterns, database ID, formula limitations)

Requirements:
1. Idempotency: before creating a new page, query the database for an existing page where
   date = the normalized record's "date" value. If found, skip (log "duplicate skipped").
   Do not update existing pages by default.
2. Build the Notion page payload:
   - For each normalized field that is not None, include it in the properties dict
   - Map Python types to Notion property types per schema-plan.md:
     - Number fields: {"number": value}
     - Date field (date): {"date": {"start": "YYYY-MM-DD"}}
     - Rich Text fields (meds_notes, notes, workout_summary): {"rich_text": [{"text": {"content": value}}]}
     - Multi-select (source_tags): {"multi_select": [{"name": v} for v in value]}
   - Skip formula fields — they auto-compute in Notion; do not attempt to write them
   - Skip manually-entered fields — the backend does not populate these
   - Set Entry (title) to the date string: {"title": [{"text": {"content": date_string}}]}
3. API call: POST /v1/pages with Authorization: Bearer $NOTION_TOKEN and Notion-Version: 2022-06-28
4. Handle errors: log 400/403/429 errors with field names and status codes; retry once on 429 after 1s
5. Return success/failure status per row

Manually-entered fields that the backend must NOT write (leave to the user):
  energy_1_5, day_quality_1_5, meds_notes, morning_heaviness, afternoon_crash,
  stress_context, fatigue_level, notes, booster_status, booster_decision,
  all workout_* fields, recovery_score, hrv_baseline_60d_ms, rhr_baseline_60d_bpm,
  hrv_7d_avg_ms, rhr_7d_avg_bpm, deep_sleep_7d_avg_min, hr_dip_7d_avg_pct

Save to src/notion_writer.py
```

**Output:** `src/notion_writer.py`.

**Blocks:** Task 1.4.

---

### Task 1.4 — Integration Test: End-to-End Webhook → Notion Row

**Prompt for coding session:**

```
Wire together the logging stub (Task 1.1), normalization layer (Task 1.2), and Notion write layer
(Task 1.3) into a single end-to-end pipeline within src/webhook.py.

Flow:
  POST /webhook
    → validate secret
    → log raw payload
    → normalize(raw_payload)
    → notion_writer.write(normalized_record)
    → return 200 with {"status": "written", "date": date_string}

Then perform a live end-to-end test:
1. Start the server locally
2. Use a real captured HAE payload from samples/ and POST it to http://localhost:8000/webhook
3. Verify a new Notion row appears at https://www.notion.so/339d7cd8531f819f85b2c769696ea27c
4. Check that: date field is correct, numeric fields match the payload values, source_tags = Apple Health
5. Trigger the same payload a second time and verify no duplicate row is created
6. Document any field discrepancies in docs/current-state.md

Save integration test script to tests/test_end_to_end.py
```

**Output:** Passing end-to-end test; verified Notion row.

**Blocks:** Backfill phase (Phase 2), live HAE deployment.

---

## Phase 2 — Backfill

> Phase 2 requires Phase 1 to be verified in production with at least one successful live webhook row.

### Task 2.1 — HAE Historical Export: Structure Verification

**Prompt for coding session:**

```
Perform a test HAE historical export for a short date range (1–2 weeks) and compare the
JSON structure against the live webhook payload saved in samples/.

Steps:
1. Use HAE's manual export feature to export data for a 1–2 week range as JSON.
2. Save to samples/hae_backfill_test_YYYY-MM-DD_to_YYYY-MM-DD.json
3. Compare the structure against samples/hae_sample_YYYY-MM-DD.json (live webhook payload):
   - Is the top-level structure the same? (data.metrics[])
   - Are field names identical?
   - Are value formats the same (units, date strings, sub-keys)?
   - Any fields present in one but not the other?
4. Update docs/decision-log.md with findings (confirm or revise the provisional decision that
   JSON export mirrors the live webhook structure).
5. Update docs/backfill-plan.md if the structure differs.
```

**Output:** Updated `decision-log.md`; confirmed backfill payload structure.

**Blocks:** Task 2.2.

---

### Task 2.2 — Backfill Script

**Prompt for coding session:**

```
Write a backfill script that reads a HAE JSON historical export and writes rows to Notion,
reusing the normalization and Notion write layers from Phase 1.

Read first:
- docs/backfill-plan.md (QA checklist, strategy)
- src/normalize.py
- src/notion_writer.py

Requirements:
1. Accept input file path as a command-line argument
2. Parse the historical HAE JSON export (structure confirmed in Task 2.1)
3. For each day's record:
   a. Normalize using normalize() — same function as Phase 1
   b. Override source_tags = ["backfill_json"]  (not "Apple Health")
   c. Check Notion for an existing row with the same date — if found, SKIP (do not overwrite live data)
   d. Write to Notion using notion_writer.write()
   e. Rate limit: sleep 300–500ms between writes
4. Write a log file (logs/backfill_YYYY-MM-DD_HHMMSS.log) with:
   - Each date processed
   - Outcome: "written", "skipped (duplicate)", "error: [message]"
   - Final summary: N written, N skipped, N errors
5. Support a --dry-run flag that prints what would be written without actually calling Notion

Save to src/backfill.py
```

**Output:** `src/backfill.py`.

**Blocks:** Full historical backfill run (Task 2.3).

---

### Task 2.3 — Full Historical Backfill Run

**Prompt for coding session:**

```
Execute the full historical backfill for 6+ months of data using the verified backfill script.

Before running:
- Verify Tasks 2.1 and 2.2 are complete and the test backfill passed QA
- Review docs/backfill-plan.md QA checklist
- Confirm no duplicate rows exist in Notion for the target date range (query Notion first)

Steps:
1. Export 6+ months of HAE data as JSON
2. Run: python src/backfill.py --dry-run path/to/export.json  (verify output looks correct)
3. Run: python src/backfill.py path/to/export.json
4. Review the log file for errors or unexpected skips
5. In Notion, spot-check 5–10 rows against Apple Health app values for the same dates
6. Verify no duplicates (query Notion for dates appearing more than once)
7. Update docs/todo.md to mark backfill complete
```

**Output:** Populated Notion database with 6+ months of historical data.

---

## Phase 3 — Infrastructure and Observability

> Phase 3 tasks can be parallelized once Phase 1 is verified.

### Task 3.1 — Deploy Backend to Hosting Platform

**Prompt for coding session:**

```
Deploy the webhook backend (src/webhook.py) to a cloud hosting platform.

Recommended option: Railway or Fly.io (see docs/architecture-plan.md for full comparison).

Steps:
1. Containerize the backend using a minimal Dockerfile (Python 3.11+ slim base)
2. Set environment variables in the hosting platform dashboard (do not commit .env):
   NOTION_TOKEN, NOTION_DATABASE_ID, HAE_WEBHOOK_SECRET, BACKEND_PORT, LOG_LEVEL
3. Deploy and obtain the public webhook URL
4. Update HAE configuration to point to the new URL
5. Send a test POST and verify a Notion row is created
6. Update docs/runbook.md with the deployed URL (as an environment-specific note, not hardcoded)

Deliverables: Deployed URL; updated docs/runbook.md.
```

---

### Task 3.2 — Webhook Authentication Hardening

**Prompt for coding session:**

```
Harden the webhook endpoint authentication (Task 1.1 implemented a basic version).

Requirements:
1. Validate HAE_WEBHOOK_SECRET using HMAC-SHA256 signature verification if HAE supports it,
   or header-based bearer token if not.
2. Reject requests without valid authentication with HTTP 401 (do not log the raw payload on 401).
3. Add rate limiting: reject more than 10 requests per minute from the same IP with HTTP 429.
4. Log authentication failures (without logging the secret or raw body) for monitoring.
5. Write a test that confirms unauthorized requests are rejected.
```

---

### Task 3.3 — Basic Error Alerting

**Prompt for coding session:**

```
Implement a simple alerting mechanism that notifies when the daily pipeline fails.

Trigger condition: It is after 10:00 AM local time and no Notion row exists for today's date.

Implementation options (choose simplest):
A. A scheduled script (cron, daily at 10:00 AM) that queries Notion and sends an email/push if missing
B. A health check endpoint on the backend that returns "healthy" if today's row exists, "missing" otherwise
   — pair with an external uptime monitor (e.g., UptimeRobot free tier)

Whichever approach is chosen:
- Do not add heavy dependencies
- Log the check result regardless of alert status
- Document the alerting setup in docs/runbook.md under "Operational Health Checks"
```

---

## Phase 4 — Coaching Layer (After Phase 1 + Full Backfill)

> Phase 4 tasks require: v1 schema stable, backfill complete, at least 30 days of clean data in Notion.

### Task 4.1 — Rolling Baseline Computation

**Prompt for coding session:**

```
Implement rolling baseline computation for the following fields:
  hrv_7d_avg_ms, rhr_7d_avg_bpm, deep_sleep_7d_avg_min, hr_dip_7d_avg_pct,
  hrv_baseline_60d_ms (60-day), rhr_baseline_60d_bpm (60-day)

Approach decision required before implementation:
A. Compute at ingest time: the backend calculates the rolling average using the last N rows from Notion
   before writing today's row. Simple but adds Notion API calls per ingest.
B. Separate scheduled job: a daily script that runs after ingest and updates rolling baseline fields
   for the most recent row. More complex but separates concerns.

Recommend Option B for v1. Implement as:
1. A script (src/compute_baselines.py) that:
   a. Queries Notion for the last 60 rows ordered by date descending
   b. Computes 7-day and 60-day rolling averages for each target metric
   c. Writes the computed values back to the most recent row via PATCH /v1/pages/{page_id}
2. Schedule to run daily at ~09:00 AM local time (after HAE export)
3. Write a dry-run flag for safe testing

Note: hrv_baseline_60d_ms is also a user-calibration input (manually seeded from Athlytic/Bevel).
The script should NOT overwrite manually-entered baseline values if they are more recent than 60 days of data.
```

---

### Task 4.2 — LLM Coaching Prompt Integration

**Prompt for coding session:**

```
Implement a script that retrieves today's Notion row and formats it as a structured daily brief prompt
for the Claude API (or clipboard paste).

Read first:
- docs/coaching-layer.md  (full prompt structure, section order, model tiering strategy)

Requirements:
1. Query Notion for today's date row
2. Format the retrieved fields into the mobile dashboard structure defined in coaching-layer.md:
   RECOVERY → KEY METRICS → SLEEP → YESTERDAY LOAD → TODAY → INTERPRETATION → RECOMMENDATIONS → FLAGS TODAY
3. Apply the recovery score algorithm (coaching-layer.md §Recovery Scoring Algorithm) to compute
   a preliminary score if recovery_score is null in Notion
4. Output format options (accept as --format argument):
   a. "prompt": formatted text block ready to paste into Claude
   b. "json": structured JSON for Claude API input
5. Include only non-null fields in the prompt; omit sections where all fields are null

Save to src/daily_brief.py

Note: Do not hard-code model or API keys. The initial implementation may output a text block for
manual paste rather than calling the Claude API directly.
```

---

*Last updated: 2026-04-06 — Initial version. All tasks are unstarted. Complete phases in order.*

---

## Thread Handoff Brief — April 6, 2026

> Read this if you are a new AI thread picking up this project.

### Start here

1. Read `docs/runbook.md` — follow the AI onboarding checklist at the top before doing anything else
2. Read `docs/current-state.md` — ground truth on what exists and what doesn't
3. Read `docs/schema-plan.md` — canonical field names (the Notion DB is the authority, not older docs)
4. Read `docs/notion-api-notes.md` — the DB already exists; do not create a new one
5. Read `docs/coaching-layer.md` — understand what the pipeline is being built to serve

### Phase 0 status — fully complete

| Task | Status | Output |
|---|---|---|
| 0.1 — Capture real HAE payload | ✅ Complete | `samples/hae_sample_2026-04-05.json` |
| 0.2 — Retrieve formula expressions from live Notion DB | ✅ Complete | `docs/notion-api-notes.md` (all 13 formulas confirmed) |
| 0.3 — Add 3 missing fields to Notion DB | ✅ Complete | `hr_day_min_bpm`, `hr_day_max_bpm`, `sleep_core_min` added via API PATCH |

### What to work on next — Phase 1

Tasks 1.1 and 1.2 are both 🟡 Ready and can be started in parallel. See the full prompts earlier in this file.

**Task 1.1** — Webhook logging stub (`src/webhook.py`)
**Task 1.2** — HAE normalization layer (`src/normalize.py`) — prompt has exact field paths, unit conversions, and expected test values for the April 5 record

### Three formula discrepancies to flag before coding

The live Notion formulas differ from what was originally documented. The formulas in the DB are correct — the docs that reference them need updating, but do not change the formulas themselves.

| Formula | What docs said | What the DB actually has |
|---|---|---|
| `flag_spo2_low` | Uses `spo2_avg_pct`, threshold < 92 | Uses `spo2_min_pct`, threshold < 90 |
| `flag_sleep_fragmented` | ≥4 awakenings OR awake_min ≥ 60 | ≥5 awakenings OR `sleep_longest_wake_min` > 15 |
| `flag_recovery_red_gate` | (HRV<40 AND deep<35) OR RHR>68 | Same, PLUS `spo2_min_pct` < 90 as additional trigger |
| `flag_early_wake` | Wake before ~5:00 AM | Triggers between 5:30–7:25 AM (target window, not early-wake) — confirm intent |

### Notion credentials

- **Database ID:** `339d7cd8-531f-819f-85b2-c769696ea27c`
- **Token:** `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` (currently in use; treat as semi-public — rotation is planned post-MVP)
- **Parent page:** `339d7cd8-531f-800b-b02d-efefaa086bf5` (Cornflower Health)

### Key payload facts (verified from `samples/hae_sample_2026-04-05.json`)

- Outer wrapper is an array: `payload[0]["data"]["metrics"]`
- `sleep_analysis` values are in **hours** — multiply by 60 for minutes
- `heart_rate` uses capital `Avg`, `Min`, `Max`
- `blood_oxygen_saturation` is already in percent — do NOT multiply by 100
- `wrist_temp` is in `degF` — do NOT convert
- `inBed` and `asleep` keys in `sleep_analysis` are always 0 — derive `sleep_time_in_bed_min` from `inBedStart`/`inBedEnd` timestamps
- `hr_sleep_avg_bpm`, `spo2_min_pct`, `sleep_awakenings_count` are **not in the HAE payload** — manual-only fields

