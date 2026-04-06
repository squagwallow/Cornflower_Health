# Todo

Prioritized next actions for the health-data-automation project. Tasks are split into Now, Next, and Later. Update this file as items are completed or priorities change.

Move completed items to the "Done" section at the bottom with a completion date.

---

## Now

These are blocking or foundational. Nothing else should start until these are complete.

- [ ] **Verify live HAE → Render → Notion pipeline**
  - Trigger an HAE sync and confirm a new row appears in the Notion DB
  - Confirm field values are correct (date, numeric values, source_tags)
  - HAE configured with webhook URL `https://cornflower-health.onrender.com/webhook` and secret header

---

## Later

These are blocked on earlier phases being stable, or are lower priority.

- [ ] **Webhook authentication hardening (Task 3.2)**
  - HMAC-SHA256 or bearer token validation
  - Rate limiting (10 req/min per IP)

- [ ] **Basic error alerting (Task 3.3)**
  - If a daily webhook fires but no Notion row is written, send a notification

- [ ] **Investigate sleep-window HR segmentation**
  - Determine whether HAE can export HR samples filtered to the sleep window
  - If yes, add `hr_sleep_avg_bpm` and `hr_sleep_min_bpm` to the source map and schema

- [ ] **Investigate sleep awakening sub-events**
  - Determine whether HAE exports individual awakening events within sleep analysis
  - If yes, add `sleep_awakenings_count` and `sleep_longest_wake_min`

- [ ] **Implement rolling baselines — Task 4.1 (HRV 7d, HRV 30d)**
  - After 30+ days of clean v1 data in Notion
  - Decide: compute in backend at ingest, or compute in a separate scheduled job

- [ ] **LLM coaching prompt integration — Task 4.2**
  - After v1 schema is stable and backfill is complete
  - Requires stable Notion fields as input — do not design prompts until schema is locked

---

## Done

| Date | Task |
|---|---|
| 2026-04-06 | Created initial documentation repository (README, 9 docs files) |
| 2026-04-06 | Task 0.1 — Captured real HAE payload (`samples/hae_sample_2026-04-05.json`) |
| 2026-04-06 | Task 0.2 — Retrieved and documented all 13 Notion formula expressions |
| 2026-04-06 | Task 0.3 — Added `hr_day_min_bpm`, `hr_day_max_bpm`, `sleep_core_min` to Notion DB |
| 2026-04-06 | Task 1.1 — Webhook endpoint (`src/webhook.py`) — FastAPI, secret validation, payload logging |
| 2026-04-06 | Task 1.2 — Normalization layer (`src/normalize.py`) — 29/29 tests passing |
| 2026-04-06 | Task 1.3 — Notion write layer (`src/notion_writer.py`) — idempotent upsert |
| 2026-04-06 | Task 1.4 — End-to-end integration test — 5/5 tests passing (37 total) |
| 2026-04-06 | Task 3.1 — Deployed to Render free tier (`https://cornflower-health.onrender.com`) |
| 2026-04-06 | `.env.example` file created |
| 2026-04-06 | Webhook authentication (shared secret via `X-Webhook-Secret` header) — implemented in Task 1.1 |
| 2026-04-06 | Task 2.1 — HAE historical export structure verified (dict format matches live webhook) |
| 2026-04-06 | Task 2.2 — Backfill script (`scripts/backfill.py`) — 29/29 tests passing |
| 2026-04-06 | Task 2.3 — Full historical backfill: 218 dates processed, 217 written, 1 skipped, 0 errors (Sept 2025 – April 2026) |

---

*Last updated: 2026-04-06 — Phase 2 complete. Moved Tasks 2.1, 2.2, 2.3 to Done.*
