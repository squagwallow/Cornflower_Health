# Implementation Backlog

This document tracks all implementation tasks with their dependencies, blockers, and current status. It is a companion to `docs/coding-session-prompts.md`, which contains the detailed prompts for each task.

Use this document to answer: "What can I work on right now, and what is blocked?"

---

## Legend

| Symbol | Meaning |
|---|---|
| 🔴 Blocked | Cannot start — dependency not met |
| 🟡 Ready | Dependencies met; can start now |
| 🟢 In Progress | Actively being worked |
| ✅ Complete | Done and verified |
| ⏸ Deferred | Not blocked but intentionally postponed |

---

## Phase 0 — Pre-Coding Prerequisites

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **0.1** — Capture real HAE JSON payload sample | ✅ Complete | — | — |
| **0.2** — Retrieve and document deployed Notion formula expressions | ✅ Complete | — | — |
| **0.3** — Add 3 missing Notion fields (`hr_day_min_bpm`, `hr_day_max_bpm`, `sleep_core_min`) | ✅ Complete | — | — |

---

## Phase 1 — Core Backend Pipeline

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **1.1** — Webhook endpoint (`src/webhook.py`) | ✅ Complete | — | — |
| **1.2** — HAE normalization layer (`src/normalize.py`) | ✅ Complete | — | — |
| **1.3** — Notion write layer (`src/notion_writer.py`) | ✅ Complete | — | — |
| **1.4** — End-to-end integration test (37/37 tests passing) | ✅ Complete | — | — |

---

## Phase 2 — Backfill

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **2.1** — HAE historical export structure verification | ✅ Complete | Phase 1 complete ✅ | Task 2.2 |
| **2.2** — Backfill script | ✅ Complete | Task 2.1 | Task 2.3 |
| **2.3** — Full historical backfill run (6+ months) | ✅ Complete | Task 2.2; test backfill verified clean | Phase 4 (coaching layer requires historical data) |

**Notes:**
- Task 2.1: Historical export structure confirmed — dict format matching live webhook.
- Task 2.2: 29/29 tests passing.
- Task 2.3: 218 dates processed, 217 written, 1 skipped (April 5 already existed from live pipeline), 0 errors. Data range: 2025-09-01 to 2026-04-06.

---

## Phase 3 — Infrastructure and Observability

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **3.1** — Deploy backend to Render | ✅ Complete | — | — |
| **3.2** — Webhook authentication hardening | ✅ Complete | Task 3.1 ✅ | — |
| **3.3** — Gap detection endpoint | ✅ Complete (detection only) | Task 3.1 ✅ | — |
| **3.3b** — Push alert on missing day | 🟡 Ready | Task 3.3 ✅ | Nothing (add email/Slack notification) |

---

## Phase 4 — Coaching Layer

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **4.1** — Rolling baseline computation | 🟡 Ready | Task 2.3 ✅ (backfill complete; 7 months of data available) | Task 4.2 (recovery score depends on baselines) |
| **4.2** — LLM coaching prompt integration | 🔴 Blocked | Task 4.1; `docs/coaching-layer.md` (complete — no blocker on docs) | Nothing downstream |

---

## Dependency Graph

```
0.1 (payload sample) ──────────────┐
                                   ├──► 1.1 ──► 1.3 ──┐
0.3 (add missing fields) ──────────┤                   ├──► 1.4 ──► 2.1 ──► 2.2 ──► 2.3 ──► 4.1 ──► 4.2
                                   └──► 1.2 ──► 1.3 ──┘              │
0.2 (formula expressions) ─────────────────────────────────────────────────── (docs only; independent)
                                                                      └──► 3.1 ──► 3.2
                                                                               └──► 3.3
```

---

## Current Blockers Summary

No hard blockers remain. Phases 0, 1, and 2 are complete. The backend is deployed and live. Historical backfill is done (7 months of data).

### Remaining decisions:

1. **Token rotation** — The Notion token was rotated on 2026-04-06.

---

## Scope Boundaries

The following items are intentionally NOT in this backlog. They are documented in `docs/coaching-layer.md` but are product/configuration tasks, not coding tasks:

| Item | Location |
|---|---|
| Recovery scoring calibration (tuning thresholds) | `docs/coaching-layer.md` — requires real data; revisit after Phase 2 |
| Claude Projects setup and configuration | `docs/coaching-layer.md` + `docs/runbook.md` |
| Titration advancement gate tracking | Manual Notion review; no automation yet |
| Flag TTL fading logic | Deferred — not yet designed for automation |
| iOS Apple Health permissions configuration | User action; `docs/runbook.md` |

---

## Non-Coding Tasks Completed (Integration Report Scope)

These tasks were part of the integration report's non-coding priorities and are now done:

| Task | Completed |
|---|---|
| Create `docs/coaching-layer.md` (P1 — domain logic rescue) | ✅ 2026-04-06 |
| Extend `docs/schema-plan.md` with missing fields + audit findings | ✅ 2026-04-06 |
| Create `docs/notion-api-notes.md` | ✅ 2026-04-06 |
| Audit existing Notion database against v1 schema | ✅ 2026-04-06 |
| Update `docs/runbook.md` with LLM coaching layer configuration (P4) | ✅ 2026-04-06 |
| Update `docs/source-payload-map.md` with thread-confirmed payload structure (P5) | ✅ 2026-04-06 |
| Create `.env.example` with security warning (P6) | ✅ 2026-04-06 |
| Update `docs/current-state.md` with Notion audit findings (P3) | ✅ 2026-04-06 |
| Create `docs/coding-session-prompts.md` | ✅ 2026-04-06 |
| Create `docs/implementation-backlog.md` (this file) | ✅ 2026-04-06 |

---

*Last updated: 2026-04-07 — Phase 3 complete (3.2 HMAC auth ✅, 3.3 gap detection ✅). Task 3.3b (push alert on missing day) added as next infrastructure item. Dashboard pages deployed, automation live.*
