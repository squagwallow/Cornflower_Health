# Decision Log

This is a chronological log of key decisions made during this project. Entries are short and focus on what was decided and why. This log is append-only — do not edit or remove past entries.

Format per entry:
```
## YYYY-MM-DD — [Short title]
**Decision:** What was decided.
**Rationale:** Why.
**Alternatives considered:** What else was considered and why it was not chosen (if applicable).
```

---

## 2026-04-06 — Adopt backend-first architecture

**Decision:** Move away from Make.com as the primary integration layer. The project will use a lightweight backend service to receive HAE webhooks, normalize fields, and write to Notion.

**Rationale:** Make.com was explored as a no-code integration approach but proved unsuitable due to: difficulty parsing nested HAE JSON arrays, fragile expression syntax, lack of version control, silent failure modes, and repeated context loss across AI-assisted debugging sessions. A minimal backend service provides full control over parsing, explicit error handling, idempotency, and testability.

**Alternatives considered:** Continuing to iterate on Make.com scenarios. Rejected because the root problems (nested JSON, no version control, no testability) are structural limitations of the platform, not configuration issues that can be fixed with more iteration.

---

## 2026-04-06 — One row per calendar day as the Notion write pattern

**Decision:** Each Notion database row represents one calendar day. The `health_date` field (YYYY-MM-DD) is the primary deduplication key.

**Rationale:** Daily summaries are the natural granularity for the target use case (health trend review, LLM coaching). Intraday granularity would increase row count, complicate queries, and provide no benefit for the current use case.

**Alternatives considered:** One row per metric per day (wide table) or one row per HAE export event. Rejected because they add complexity without benefit.

---

## 2026-04-06 — Normalize all field names to internal snake_case names

**Decision:** Raw HAE field names (e.g., `heart_rate_variability`, `apple_sleeping_wrist_temperature`) are never written directly to Notion. All fields are mapped to normalized internal names before writing.

**Rationale:** HAE field names may change across app versions. Normalizing at ingest decouples the internal schema from the upstream source. Internal names are more readable and consistent.

---

## 2026-04-06 — Defer 9 metrics to Phase 2 or later

**Decision:** The following fields are explicitly deferred from v1: `hr_sleep_avg_bpm`, `hr_sleep_min_bpm`, `hr_dip_pct`, `sleep_awakenings_count`, `sleep_longest_wake_min`, `wrist_temp_delta`, `hrv_baseline_7d`, `hrv_baseline_30d`, `recovery_flag`.

**Rationale:** These fields depend on either (a) HAE payload features not yet confirmed (sleep-window HR segmentation, awakening sub-events), or (b) historical baseline data that does not yet exist. Including them in v1 would require either unsupported assumptions or placeholder formulas that would produce misleading values.

---

## 2026-04-06 — Historical backfill is a first-class project phase

**Decision:** Backfill of 6+ months of historical Apple Health data is treated as a dedicated project phase, not an optional add-on.

**Rationale:** Without historical data, the Notion database is not useful for trend analysis or LLM coaching prompts. The backfill phase must be planned with explicit deduplication and QA requirements before it is executed.

---

## 2026-04-06 — This repository is the authoritative project memory

**Decision:** All future AI-assisted work sessions on this project must begin by reading this repository. The repo takes precedence over any context in a chat thread.

**Rationale:** Repeated context loss across AI-assisted work sessions has been the primary source of wasted effort on this project. Encoding the project state in version-controlled markdown files eliminates dependency on thread continuity.

---

## 2026-04-06 — JSON export preferred over CSV for backfill

**Decision (provisional/assumed):** HAE JSON export is the preferred format for the historical backfill because it mirrors the live webhook payload structure, allowing the same normalization logic to be reused.

**Rationale:** Reusing the normalization layer reduces the amount of new code needed for backfill and ensures consistent field handling.

**Status:** This is an assumption. It must be confirmed by performing a test export and comparing the JSON and CSV formats. Update this entry after the test export.

---

*Entries above are the initial log, created as part of the documentation-first phase on 2026-04-06. Future entries should be appended below this line.*

---

## 2026-04-06 — HAE historical export uses same dict format as live webhook

**Decision:** Task 2.1 confirmed that HAE historical JSON export uses the same dict format as live webhook payloads. No structural differences found. The backfill script handles both dict and array formats.

**Rationale:** Testing the historical export against the live payload structure confirmed they are identical in format. This allowed the backfill script to reuse the same normalization layer without any format-specific branching. The script defensively handles both dict and array formats for robustness.

**Alternatives considered:** None — this was a verification task, not a design decision. The provisional assumption (JSON export preferred over CSV) from the earlier decision log entry is now confirmed.

---

*Last updated: 2026-04-06*

---

## Open Research Questions (added 2026-04-07)

### HRV Methodology: Athlytic vs Bevel Philosophy
**Status:** Unresolved — pending research. Add to backlog before implementing any HRV weighting changes.

**Observation:**
- Athlytic tends to produce higher-variance HRV readings, weights recent samples heavily,
  and recalculates daily recovery when mindfulness sessions are completed (especially early
  in the day). It actively pulls HRV from mindfulness/breathing session data.
- Bevel produces tightly distributed HRV data, is less responsive to intraday swings,
  and appears to use a more smoothed/averaged approach.

**Questions to resolve:**
1. What underlying HRV metric does each app use — RMSSD, SDNN, or something else? Are they measuring the same thing?
2. Does Athlytic pull from all Apple Health HRV samples (including Mindfulness app sessions) or only overnight/morning readings?
3. What does HAE export for HRV — is it the overnight average, the most recent reading, or all samples? Can we control which one we store?
4. Given our use case (daily recovery scoring, stimulant protocol gating), which philosophy better serves the goal? A more responsive model tracks genuine intraday changes but may produce noisy gates; a smoothed model is more stable but may lag real recovery shifts.
5. Should the 60-day baseline be computed from all stored HRV values or only overnight values?

**Recommended approach before resolving:**
Route to Tier 3 (research prompt) in `docs/agentic-cost-guidelines.md`, then bring the research findings back for an informed implementation decision. Do not change HRV storage or baseline logic until this is settled.
