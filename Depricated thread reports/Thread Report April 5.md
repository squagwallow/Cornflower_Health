<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Thread Report

## 1. Thread scope

This thread attempted to pivot an in-progress health tracking project from a Claude Projects-based implementation to a **Notion-centric architecture** powered by Apple Health data and an LLM coach. The primary focus shifted to: (1) finalizing the Notion database schema, (2) creating the database via API, and (3) designing an automation pipeline (Apple Health → Notion) using either Shortcuts or Health Auto Export. The thread ultimately struggled with implementation friction around Shortcuts complexity and context degradation.

## 2. Confirmed facts

- **Database created successfully:** `Daily Health Metrics` (ID: `339d7cd8-531f-819f-85b2-c769696ea27c`) exists in Notion under a "Health Hub" parent page.
- **API token verified:** Internal integration token `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` is valid and working.
- **Test row validated:** A manually inserted test row (2026-04-05) confirmed that core formulas fire correctly, including `hr_dip_pct`, `flag_deep_sleep_low`, `flag_recovery_red_gate`, and `recovery_category`.
- **Schema locked:** Final schema includes ~40 fields across meta, cardio/sleep, HR dip, workout load, subjective, medication, baselines, flags, and recovery categories.
- **Platform choice:** Perplexity (with Notion connector) selected as primary daily coach; Claude Desktop as secondary for weekly analysis.
- **User constraints:** Strong preference against manual data entry; willingness to pay for tools (\$20–50) to avoid fiddly setups; frustration with block-based visual programming (Shortcuts).


## 3. Attempts made

- **Schema design:** Iterative refinement of Notion property types, formulas, and derived fields (e.g., `sleep_efficiency_pct`, `hr_dip_category`, `flag_early_wake`).
- **Database creation via API:** Successful `curl` POST to `https://api.notion.com/v1/databases` using a JSON payload after troubleshooting auth (401) and formula type errors (400).
- **Formula debugging:** Stubbed complex boolean formulas (e.g., `flag_recovery_red_gate`) to bypass API validation errors, then verified in UI.
- **Automation design (Shortcuts):** Attempted to specify a macOS Shortcuts workflow to extract Apple Health samples (HRV, RHR, sleep stages, HR dip) and POST to Make.com webhook.
- **Automation design (Health Auto Export):** Discussed as a more robust alternative to Shortcuts, with Make.com computing baselines and writing to Notion.
- **Dashboard design (Phase C):** Outlined steps to create an Athlytic-style Notion dashboard with linked database views (table + board grouped by `recovery_category`).


## 4. What failed or proved fragile

- **Shortcuts implementation:** Proved excessively fiddly due to:
    - Lack of text-based specification format (no JSON/YAML → `.shortcut` bundle).
    - Block-based UI difficult to specify remotely; action names vary by OS version.
    - Sleep data extraction requires multiple stage-specific queries (In Bed, Asleep, Core, Deep, REM, Awake) rather than a single "Sleep Analysis" type.
    - HR dip calculation (splitting HR samples into sleep vs. awake windows) requires complex loop/conditional logic in Shortcuts.
- **Context degradation:** Thread exceeded effective context window, leading to incoherent recommendations and loss of schema/automation details.
- **Manual dashboard build:** User rejected the Phase C dashboard instructions as "manually entering each value" (misinterpretation, but indicative of frustration with any non-automated path).
- **Make.com baseline computation:** Not fully specified or tested; left as "optional v1" due to complexity.


## 5. What appeared to work

- **API database creation:** `curl` command with hardcoded token successfully created the database after formula stubbing.
- **Test row insertion:** `curl` POST to `/v1/pages` with sample data confirmed formulas compute correctly (e.g., RED recovery category triggered by low HRV + deep sleep).
- **Core formulas verified:** `day_of_week`, `sleep_efficiency_pct`, `hr_dip_pct`, `hr_dip_category`, `flag_deep_sleep_low` all validated in UI.
- **Schema design:** Final field list and formula logic are coherent and align with original Athlytic/Bevel-inspired recovery logic.


## 6. Recommendations made in this thread

| Recommendation | Label | Notes |
| :-- | :-- | :-- |
| Use **Health Auto Export + Make.com** for automation | Still plausible | User expressed willingness to pay; avoids Shortcuts friction. |
| Use **Shortcuts-only** for automation | Superseded | User rejected due to complexity and lack of text-based spec. |
| Build **Notion dashboard** (Phase C) before automation | Likely outdated | User rejected as "manual entry"; priority shifted back to automation first. |
| Stub complex formulas in JSON, fix in UI later | Still plausible | Proven workaround for API formula validation errors. |
| Use **Perplexity with Notion connector** as primary coach | Still plausible | Aligns with user's mobile-first, low-friction goals. |
| Manually enter rows temporarily to test dashboard | Superseded | User explicitly rejected any manual workflow. |
| Defer sleep/HR dip automation to v1.1 | Unclear | Would require accepting partial automation; user's tolerance unknown. |

## 7. Artifacts worth preserving

- **Final schema:** ~40-field Notion schema with pre-computed baselines, boolean flags, and recovery categories (see schema block in thread).
- **Formula expressions:**
    - `hr_dip_pct`: `round((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm") * 100 * 10) / 10`
    - `flag_recovery_red_gate`: `(prop("hrv_sdnn_ms") < 40 and prop("sleep_deep_min") < 35) or prop("rhr_bpm") > 68 or prop("flag_hr_dip_non_dipping") or prop("spo2_min_pct") < 90`
    - `recovery_category`: `if(prop("flag_recovery_red_gate"), "🔴 RED", if(and(prop("hrv_sdnn_ms") >= 50, prop("sleep_deep_min") >= 45, not(prop("flag_rhr_elevated"))), "🟢 GREEN", "🟡 YELLOW"))`
- **API commands:**
    - Database creation: `curl -X POST "https://api.notion.com/v1/databases" -H "Authorization: Bearer <token>" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" -d @payload.json`
    - Test row insertion: Full `curl` POST to `/v1/pages` with sample metrics (preserved in thread).
- **Handoff prompt:** Detailed restart prompt with schema context, DB ID, token, and deliverables list (optimized for new thread continuity).


## 8. Open questions left unresolved

- **Automation tool choice:** Health Auto Export vs. Shortcuts vs. hybrid (sleep data only via export, others via Shortcuts).
- **Make.com baseline logic:** Exact JavaScript/module configuration to compute 60d and 7d rolling averages from existing Notion rows.
- **Sleep stage availability:** Which sleep types (In Bed, Asleep, Core, Deep, REM, Awake) are exposed in macOS Shortcuts on the user's specific OS version.
- **HR dip approximation:** Whether to use simplified HR dip (RHR as day avg, sleep session avg from Health) or full sample-splitting logic.
- **Dashboard column set:** Final ordered list of columns for Athlytic-style table view (user rejected initial proposal before seeing it).
- **LLM prompt specifics:** Exact Perplexity prompt that reads the Notion dashboard and outputs recovery score + medication/training recommendations.


## 9. Usefulness score

**Score: 3/5**

**Why:**

- ✅ **High value:** Database successfully created, schema locked, test row validated, API workflow proven.
- ❌ **High friction:** Automation design stalled on Shortcuts complexity; context degradation rendered final recommendations incoherent.
- ⚠️ **Partial:** Dashboard and LLM prompt phases outlined but not executed; user frustration suggests misalignment on implementation path.


## 10. Repo-ready summary

**Thread A (2026-04-05): Notion DB Creation \& Schema Lock** — Successfully created the `Daily Health Metrics` database via Notion API (`339d7cd8...`) and validated core formulas with a test row. Locked a 40-field schema including HR dip metrics, recovery flags, and medication logic. Automation design stalled due to Shortcuts complexity (sleep stage extraction, HR sample splitting) and context degradation. Recommended path forward: Health Auto Export + Make.com for robust, low-fiddling automation. Dashboard and LLM coaching phases outlined but deferred. Key artifacts: final schema, formula expressions, API curl commands, handoff prompt for continuation.

