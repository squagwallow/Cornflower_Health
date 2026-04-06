# Todo

Prioritized next actions for the health-data-automation project. Tasks are split into Now, Next, and Later. Update this file as items are completed or priorities change.

Move completed items to the "Done" section at the bottom with a completion date.

---

## Now

These are blocking or foundational. Nothing else should start until these are complete.

- [ ] **Capture a real HAE JSON payload sample**
  - Configure HAE to send a test webhook to a logging endpoint (e.g., [webhook.site](https://webhook.site))
  - Copy the raw JSON body
  - Save to `samples/hae_sample_YYYY-MM-DD.json` (redact any PII or tokens)
  - Review all field names against [`source-payload-map.md`](source-payload-map.md) and update any entries marked "needs verification"
  - Priority: highest — all backend work is blocked on this

- [ ] **Confirm Notion database property types**
  - Create (or verify) the Notion database with the v1 schema from [`schema-plan.md`](schema-plan.md)
  - Confirm each property name and type matches the schema plan table
  - Document the Notion database ID (store in `.env`, not in this repo)

- [ ] **Stand up a minimal backend endpoint (logging stub)**
  - A single HTTP POST endpoint that receives the HAE webhook and logs the raw payload
  - No transformation or Notion writing required yet
  - Goal: confirm HAE can reach the endpoint and that the raw payload is received correctly
  - Choose hosting (see options in [`architecture-plan.md`](architecture-plan.md))

---

## Next

These can start once the "Now" items are done.

- [ ] **Write the normalization layer**
  - Map raw HAE payload fields to internal field names per [`source-payload-map.md`](source-payload-map.md)
  - Handle missing/optional fields gracefully (null, not error)
  - Apply unit normalization (SpO2 decimal → percent; confirm wrist temp unit)
  - Derive `health_date` from `sleepEnd` or device timestamp
  - Set `source_tags = "hae_webhook"` and `ingest_timestamp`

- [ ] **Write the Notion write layer**
  - Accept a normalized record dict and write it to the Notion database
  - Check for existing row with matching `health_date` before writing (idempotency)
  - Handle Notion API errors (403, 400, 429) with appropriate logging and retry

- [ ] **End-to-end test: live daily webhook → Notion row**
  - Trigger a real HAE export to the backend
  - Verify the Notion row is created with correct field values
  - Verify a second trigger on the same day does not create a duplicate

- [ ] **Perform a test HAE historical export (1–2 weeks)**
  - Export in JSON format
  - Verify the export structure matches the live payload (or document differences)
  - Update [`backfill-plan.md`](backfill-plan.md) if the structure differs

- [ ] **Write the backfill script**
  - Read historical HAE JSON export
  - Use the same normalization layer as the live pipeline
  - Set `source_tags = "backfill_json"`
  - Idempotency: skip rows where `health_date` already exists in Notion
  - Rate limiting: 300–500ms between writes
  - Write a log file per run

---

## Later

These are blocked on earlier phases being stable, or are lower priority.

- [ ] **Run full historical backfill (6+ months)**
  - After test backfill (1–2 weeks) is verified clean
  - Follow QA checklist in [`backfill-plan.md`](backfill-plan.md)

- [ ] **Add `.env.example` file**
  - Document all required environment variables from [`runbook.md`](runbook.md)

- [ ] **Add webhook authentication**
  - Validate shared secret in request header
  - Reject requests without valid secret (return 401)

- [ ] **Set up basic error alerting**
  - If a daily webhook fires but no Notion row is written, send a notification (email, SMS, or push)
  - This is lower priority while the pipeline is still being validated

- [ ] **Investigate sleep-window HR segmentation**
  - Determine whether HAE can export HR samples filtered to the sleep window
  - If yes, add `hr_sleep_avg_bpm` and `hr_sleep_min_bpm` to the source map and schema
  - Update deferred fields in [`source-payload-map.md`](source-payload-map.md) and [`schema-plan.md`](schema-plan.md)

- [ ] **Investigate sleep awakening sub-events**
  - Determine whether HAE exports individual awakening events within sleep analysis
  - If yes, add `sleep_awakenings_count` and `sleep_longest_wake_min`

- [ ] **Implement rolling baselines (HRV 7d, HRV 30d)**
  - After 30+ days of clean v1 data in Notion
  - Decide: compute in backend at ingest, or compute in a separate scheduled job

- [ ] **Design LLM coaching prompt layer**
  - After v1 schema is stable and backfill is complete
  - Requires defining what questions the coaching layer should answer
  - Requires stable Notion fields as input — do not design prompts until schema is locked

---

## Done

| Date | Task |
|---|---|
| 2026-04-06 | Created initial documentation repository (README, 9 docs files) |

---

*Last updated: 2026-04-06*
