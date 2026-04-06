# Project Overview

## Summary

This project automates the collection of daily Apple Health metrics and writes structured daily summaries into a Notion database. The long-term goal is to build a reliable, normalized data layer that can support LLM-based health coaching and trend analysis without requiring manual data entry or fragile no-code glue logic.

---

## Goals

### Primary (v1)
- Receive daily Apple Health data from Health Auto Export (HAE) via webhook
- Normalize raw HAE fields into a consistent internal schema
- Write one row per day into a Notion database
- Ensure idempotent writes (re-running the same day does not create duplicate rows)
- Support historical backfill of 6+ months of existing Apple Health data

### Secondary (v2+)
- Build LLM-based coaching prompts on top of stable, normalized Notion fields
- Add rolling baseline calculations (e.g., 7-day and 30-day HRV averages)
- Add recovery scoring or flag fields derived from multiple metrics
- Potentially support multi-source ingestion beyond Apple Health

---

## Scope Boundaries

**In scope (v1):**
- HAE → backend → Notion pipeline for the confirmed v1 field list
- Historical backfill via HAE CSV or JSON export
- Basic deduplication and error logging

**Out of scope (v1):**
- Real-time or intraday metrics
- HR during sleep segmentation (requires additional source parsing)
- Wrist temperature delta (requires baseline; deferred)
- LLM coaching layer (requires stable Notion fields first)
- Any public-facing interface or dashboard

---

## Current Status

As of 2026-04-06:

- Source metrics and normalized field names have been confirmed for v1
- Make.com was explored as a no-code integration layer and was found to be insufficient for this use case
- No functional backend exists yet
- No Notion database rows are being written automatically
- Historical data is available and waiting for a backfill mechanism

---

## Major Pain Points Encountered

### Make.com Context and Syntax Failures
Substantial time was spent attempting to configure Make.com to parse nested HAE JSON payloads. This work encountered repeated failures:
- HAE payloads use nested arrays (e.g., sleep stages within a sleep analysis object) that Make's built-in JSON parser did not handle cleanly without custom iterator setups
- Syntax errors in Make's expression language accumulated across sessions
- Context was lost between AI-assisted work threads, requiring re-explanation of the same payload structure multiple times
- The no-code approach introduced brittleness: any change to the HAE payload format would likely break the scenario silently

### Cross-Thread Context Loss
Each new AI-assisted work session required re-establishing context about the payload structure, field names, schema decisions, and prior failed approaches. This created duplicated effort and introduced inconsistencies.

---

## Why Documentation-First Now

This repository exists to break the cycle described above. Before writing any more production code or no-code configurations, the project needs:

1. A single authoritative record of confirmed field mappings
2. A clear record of what has been tried and why it was rejected
3. A schema plan that future threads can treat as ground truth
4. An operational runbook so future AI threads can onboard without re-deriving decisions

**All future work sessions should begin by reading this repository.**

---

*Last updated: 2026-04-06*
