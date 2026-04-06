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
| **0.2** — Retrieve and document deployed Notion formula expressions | 🟡 Ready | Notion API access + regenerated token | `notion-api-notes.md` completeness; Phase 1 formula verification |
| **0.3** — Add 3 missing Notion fields (`hr_day_min_bpm`, `hr_day_max_bpm`, `sleep_core_min`) | 🟡 Ready | Notion API access + regenerated token | Task 1.2 (normalization of those fields) |

---

## Phase 1 — Core Backend Pipeline

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **1.1** — Webhook endpoint (logging stub) | 🟡 Ready | — | Tasks 1.2, 1.3, 1.4 |
| **1.2** — HAE normalization layer | 🟡 Ready | Task 0.3 (for min/max/core fields) | Task 1.3, 1.4 |
| **1.3** — Notion write layer | 🔴 Blocked | Tasks 1.1, 1.2 | Task 1.4 |
| **1.4** — End-to-end integration test | 🔴 Blocked | Tasks 1.1, 1.2, 1.3 | Phase 2 all tasks; Phase 3 deployment |

---

## Phase 2 — Backfill

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **2.1** — HAE historical export structure verification | 🔴 Blocked | Task 1.4 verified in production | Task 2.2 |
| **2.2** — Backfill script | 🔴 Blocked | Tasks 1.2, 1.3 (normalization + write layers); Task 2.1 | Task 2.3 |
| **2.3** — Full historical backfill run (6+ months) | 🔴 Blocked | Task 2.2; 2-week test backfill verified clean | Phase 4 (coaching layer requires historical data) |

---

## Phase 3 — Infrastructure and Observability

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **3.1** — Deploy backend to hosting platform | 🔴 Blocked | Task 1.4 (pipeline verified locally) | Live HAE daily webhook |
| **3.2** — Webhook authentication hardening | 🔴 Blocked | Task 3.1 (requires deployed URL) | Nothing (can layer on top of live backend) |
| **3.3** — Basic error alerting | 🔴 Blocked | Task 3.1 | Nothing (monitoring is independent) |

---

## Phase 4 — Coaching Layer

| Task | Status | Depends On | Blocks |
|---|---|---|---|
| **4.1** — Rolling baseline computation | 🔴 Blocked | Task 2.3 (full backfill); 30+ days clean data | Task 4.2 (recovery score depends on baselines) |
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

### Hard Blockers (No Code Can Start Without These)

1. ~~**Real HAE JSON payload sample (Task 0.1)**~~ — **Resolved 2026-04-06.** See `samples/hae_sample_2026-04-05.json`.

2. **Regenerate Notion integration token**
   - What it unblocks: Tasks 0.2, 0.3 (and eventually all backend API calls)
   - How to unblock: [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations) → find integration → Regenerate → update `.env`
   - Estimated time: 5 minutes
   - **Do this immediately.** The previous token is exposed.

### Soft Blockers (Can Be Done in Parallel With Phase 0)

3. **Hosting platform decision (for Task 3.1)**
   - Decision needed: local Python vs. Railway vs. Fly.io vs. Vercel
   - See `docs/architecture-plan.md` for comparison
   - Recommendation: Railway (simplest deploy for Python/FastAPI, low cost, always-on)

4. **Backend language/framework decision (for Task 1.1)**
   - Default recommendation: Python 3.11 + FastAPI + python-dotenv
   - Can be overridden to Flask (simpler) if preferred

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

*Last updated: 2026-04-06*
