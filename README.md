# health-data-automation

Automated pipeline to collect daily Apple Health metrics and write structured daily summaries into a Notion database. Designed to support future LLM-based health coaching built on stable, normalized Notion fields.

---

## Current Recommended Architecture

```
Apple Health (device)
    └── Health Auto Export (HAE) app
            └── HTTP webhook (JSON payload)
                    └── Backend service (lightweight, self-hosted or cloud)
                            ├── Parse + normalize fields
                            ├── Write to Notion database (daily rows)
                            └── Deduplicate / idempotency logic
```

**Make.com is not the recommended long-term path.** See [`docs/architecture-plan.md`](docs/architecture-plan.md) for the full comparison and rationale.

---

## Repository Structure

```
health-data-automation/
├── README.md                   ← This file
├── docs/
│   ├── project-overview.md     ← Full project description and goals
│   ├── current-state.md        ← What is confirmed, failed, decided, uncertain
│   ├── source-payload-map.md   ← HAE raw metric → normalized field mapping table
│   ├── schema-plan.md          ← Canonical internal schema (v1 and future)
│   ├── architecture-plan.md    ← Make vs backend-first; ingestion + backfill flows
│   ├── backfill-plan.md        ← Strategy for loading 6+ months of historical data
│   ├── runbook.md              ← Operational runbook; future AI thread onboarding
│   ├── decision-log.md         ← Chronological log of key decisions
│   └── todo.md                 ← Prioritized next actions
├── samples/
│   └── (place raw HAE JSON payload samples here — no tokens or PII)
└── schema/
    └── (place JSON Schema or field definition files here when ready)
```

---

## Immediate Next Steps

1. **Stand up a minimal backend endpoint** that accepts the HAE webhook POST and logs the raw payload. No transformation required yet. See [`docs/todo.md`](docs/todo.md).
2. **Capture a real sample payload** from HAE and save it to `samples/`. See [`docs/runbook.md`](docs/runbook.md).
3. **Confirm the Notion database schema** matches the v1 field list in [`docs/schema-plan.md`](docs/schema-plan.md).
4. **Verify HAE field names** against the payload map in [`docs/source-payload-map.md`](docs/source-payload-map.md) using a real export.
5. **Plan the backfill run** following [`docs/backfill-plan.md`](docs/backfill-plan.md).

---

## Documentation-First Rationale

This project has accumulated substantial context across multiple AI-assisted work sessions. This repository is the authoritative project memory going forward. All future AI threads working on this project should be directed to read this repo before generating new work.

---

*Last updated: 2026-04-06*
