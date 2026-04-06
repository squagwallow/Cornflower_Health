# Runbook

This document is the operational guide for maintaining, debugging, and extending this project. It is written for both human reviewers and future AI threads.

---

# For Future AI Threads: Read This First

If you are an AI assistant being asked to work on this project, follow this checklist before generating any code, configuration, or schema changes:

1. **Read [`README.md`](../README.md)** — understand the project scope and repo structure.
2. **Read [`docs/current-state.md`](current-state.md)** — understand what is confirmed, what has failed, and what is uncertain. Do not re-propose Make.com.
3. **Read [`docs/source-payload-map.md`](source-payload-map.md)** — use only the confirmed field names. Do not invent new internal field names without adding them here.
4. **Read [`docs/schema-plan.md`](schema-plan.md)** — do not write code that targets future/deferred fields unless the user explicitly requests it.
5. **Read [`docs/architecture-plan.md`](architecture-plan.md)** — the backend-first approach is the current direction. Do not propose Make.com or other no-code middleware.
6. **Read [`docs/coaching-layer.md`](coaching-layer.md)** — understand the product logic (recovery scoring, flag tiers, stimulant protocol, LLM prompt structure) that the pipeline is being built to serve.
7. **Read [`docs/notion-api-notes.md`](notion-api-notes.md)** — the Notion database already exists. Do not create a new one. Reference the API patterns and formula definitions here before writing any Notion-related code.
8. **Check [`docs/todo.md`](todo.md)** — understand what is being worked on now and what is queued.
9. **Check `samples/*`** — if a real HAE JSON payload is present, use it to verify field names and structure. If not, note that unverified fields are marked as assumptions.
10. **Add to [`docs/decision-log.md`](decision-log.md)** — if you make a decision that affects architecture, schema, or approach, log it.

---

# Troubleshooting: Missing Metrics

If a Notion row is missing expected field values, work through the following:

## Step 1: Check the raw payload log
- Does the backend log raw incoming payloads? If yes, find the log entry for the date in question.
- Was the HAE metric present in the raw payload for that date?
- If absent from the payload: the metric was not recorded on that day by Apple Health. This is expected for some metrics (e.g., SpO2 may not record every night if the watch was not worn).

## Step 2: Check the normalization layer
- Was the metric present in the payload but not written to Notion?
- Check the backend normalization code for the field's mapping.
- Check whether the HAE field name or nesting path has changed (HAE app updates can change payload structure).
- Verify against the latest field mapping in [`source-payload-map.md`](source-payload-map.md).

## Step 3: Check the Notion write
- Was the Notion page created for that date? If no page exists, the write may have failed entirely.
- Check the backend error log for Notion API errors (403 permission, 400 bad request, 429 rate limit).
- Check the Notion integration permissions — the integration must have write access to the target database.

## Step 4: Check HAE configuration
- Is HAE configured to export all required metrics?
- Is the scheduled export running? (HAE requires the app to be active; check iOS Background App Refresh settings.)
- Has the HAE webhook URL changed or expired?

---

# How to Preserve Sample Payloads

Sample payloads are critical for testing and debugging. Whenever the HAE payload structure changes or a new metric is added, save a redacted sample.

**Where to save:** `samples/hae_sample_YYYY-MM-DD.json`

**What to redact before saving:**
- Remove any user-identifiable information if present (HAE payloads typically do not include PII, but verify)
- Do not include device identifiers or account tokens
- Do not include the webhook endpoint URL or authentication headers

**How to capture:**
- Option A: Configure HAE to send to a request-logging service (e.g., webhook.site) temporarily and copy the raw body.
- Option B: Add a raw payload logging step to the backend that writes incoming payloads to a local file (with a flag to disable in production).
- Option C: Use HAE's manual export feature to generate a JSON file for a specific date range.

**After saving a sample:**
- Review [`source-payload-map.md`](source-payload-map.md) and verify all assumed field paths against the real sample.
- Update any fields marked "needs verification" or "assumed."
- Note the HAE app version and iOS version at the time of capture (payload structure may vary by version).

---

# How to Document Future Changes

## Adding a new metric
1. Verify the raw HAE field name and payload path from a real sample.
2. Add a row to the mapping table in [`source-payload-map.md`](source-payload-map.md).
3. Add the internal field name to the appropriate section of [`schema-plan.md`](schema-plan.md).
4. If promoting a future field to v1, move it from the future table to the v1 table in both documents.
5. Add a backend normalization step for the new field.
6. Add the new Notion property to the database via `PATCH /v1/databases/{id}` (see [`notion-api-notes.md`](notion-api-notes.md)).
7. Log the change in [`decision-log.md`](decision-log.md).
8. Test against a real payload sample before deploying.

## Changing a field name
- Do not rename deployed fields that already have data written to Notion. Renaming breaks historical consistency.
- If a rename is necessary, write a migration plan: create the new field, backfill it from the old field, verify, then retire the old field.
- Log the migration in [`decision-log.md`](decision-log.md).

## Changing the backend
- Update [`architecture-plan.md`](architecture-plan.md) to reflect the new architecture.
- Update [`../README.md`](../README.md) if the high-level flow changes.
- Update [`todo.md`](todo.md) to remove completed tasks and add any new work.

## Changing the Notion schema
- Update [`schema-plan.md`](schema-plan.md).
- Note any Notion property type changes that would require data migration.
- Test with a single row before migrating all data.

---

# LLM Coaching Layer Configuration

This section covers how to configure the Claude-based coaching layer that interprets Notion data and generates the daily health brief. The full product logic is in [`coaching-layer.md`](coaching-layer.md).

## Model Tiering

| Task | Model | Connector State |
|---|---|---|
| Daily check-in brief | Claude Haiku | Disabled (manual data input) |
| Weekly trend analysis | Claude Opus | Enable Apple Health connector |
| Handoff document generation | Claude Sonnet | No connector needed; structured output |

Using Haiku for daily check-ins reduces cost substantially (approximately 30% of Sonnet's token cost) without meaningful quality loss for routine interpretation. Reserve Opus for weekly sessions where trend reasoning matters.

## Claude Projects Configuration Checklist

When setting up or resetting the Claude health project:

- [ ] **Memory → OFF** for this project. Claude Memory uses lossy summarization (~1,500–1,750 words); sensitive health data must not flow through it.
- [ ] **Training opt-out → verify** in Claude Settings → Privacy → Improve Claude for everyone. Disable this for health-sensitive projects.
- [ ] **Connectors → disable when not in use.** Each active connector costs 100–500 tokens per message. Enable Apple Health only during weekly analysis sessions; disable between uses.
- [ ] **Apple Health data types → configure globally** in iOS Settings → Health → Data Access & Devices → Claude. Only enable the categories needed for coaching (heart rate, HRV, sleep, respiratory rate, SpO2, wrist temperature).
- [ ] **Add to project knowledge:** `coaching-layer.md` (recovery algorithm, flags, prompt template), `schema-plan.md` (current field definitions), and a current Notion export snippet for context.

## Token Optimization Practices

- Start each coaching session with a fresh chat (not a continuation of a previous thread). Fresh chats reduce context overhead.
- Knowledge files are cached by Claude Projects; repeated queries against cached files do not re-consume usage.
- Disable unused connectors before starting a session.
- For daily check-ins, paste the current day's Notion row as structured text rather than asking Claude to fetch from Notion — this is more token-efficient.

## iOS Apple Health Permissions Path

```
iOS Settings → Health → Data Access & Devices → Claude → [select data types]
```

Enable: Heart Rate, Heart Rate Variability, Resting Heart Rate, Respiratory Rate, Blood Oxygen, Wrist Temperature, Sleep.

## HIPAA Warning

Claude Pro (consumer) is **NOT HIPAA-compliant.** Do not enter protected health information (PHI) — full name, date of birth, specific diagnosis codes, insurance information — in this context.

For PHI-safe use, HIPAA compliance requires Claude for Work (Teams or Enterprise plan) with a signed Business Associate Agreement (BAA) from Anthropic, or the Anthropic API with a BAA.

For this project, the risk is low because the data is self-tracked biometrics without clinical PHI. De-identify any content before entering it.

---

# Operational Health Checks

Run these checks periodically (e.g., weekly) once the pipeline is live:

| Check | How |
|---|---|
| New rows are being written daily | Query Notion for rows where `date` = today or yesterday |
| No unexpected null fields | Review recent rows for fields that should always have values (e.g., `rhr_bpm`, `sleep_time_asleep_min`) |
| No duplicate rows | Query Notion for any `date` values that appear more than once |
| Backend is reachable | Send a test POST to the webhook endpoint and verify the response |
| HAE is exporting | Check HAE app for last successful export timestamp |

---

# Environment Variables Reference

> Do not commit actual values. Use `.env.example` with placeholder values.

| Variable Name | Description |
|---|---|
| `NOTION_TOKEN` | Notion integration secret token |
| `NOTION_DATABASE_ID` | ID of the target Notion database (`339d7cd8-531f-81f5-be5d-000bc78ce4eb`) |
| `HAE_WEBHOOK_SECRET` | Shared secret used to authenticate incoming HAE requests |
| `BACKEND_PORT` | Webhook endpoint port (default: 8000) |
| `LOG_LEVEL` | Logging verbosity (`INFO`, `DEBUG`) |
| `BACKFILL_MODE` | Set to `true` to enable backfill behavior (skip existing rows) |

---

*Last updated: 2026-04-06 — Added LLM Coaching Layer Configuration section (P4 from integration report). Updated field references to match deployed Notion schema.*
