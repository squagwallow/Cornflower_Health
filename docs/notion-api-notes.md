# Notion API Implementation Notes

This document captures hard-won knowledge from building the Daily Health Metrics database via the Notion API. Read before attempting any database creation, property addition, or formula deployment.

**Source:** Rescued from Thread Report April 5 short (April 5–6, 2026). This information was previously only in deprecated thread reports.

---

## Database Identity

> **Security note:** These IDs are safe to store in the repo (they are not secrets). The integration token is a secret — never commit it. See `.env.example`.

| Item | Value |
|---|---|
| Database name | Daily Health Metrics |
| Database ID (for API calls) | `339d7cd8-531f-819f-85b2-c769696ea27c` |
| Database URL | `https://www.notion.so/339d7cd8531f819f85b2c769696ea27c` |
| Parent page ID | `339d7cd8-531f-800b-b02d-efefaa086bf5` |
| Parent page name | Cornflower Health |
| Data source (collection) ID | `collection://339d7cd8-531f-819f-85b2-c769696ea27c` |

**Status as of 2026-04-06:** The database exists, is fully built, and contains a test row (Formula Test Row – DELETE ME). It is substantially ahead of what `schema-plan.md` documented at repo creation. See `current-state.md` for the full audit comparison.

---

## Confirmed Working API Patterns

### Staged Batch Creation

When building or modifying the schema via the API, use a staged approach:

1. **Stage 1:** Create the database with the base set of simple properties (numbers, text, dates, selects) via `POST /v1/databases`
2. **Stage 2:** Add formula properties one at a time via `PATCH /v1/databases/{database_id}`

Do not attempt to add all properties in a single request. Large property sets cause API timeouts or silent partial-application.

### Base Payload Structure (Working)

```bash
curl -X POST https://api.notion.com/v1/databases \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d @payload.json
```

Write the JSON payload to a file first (`payload.json`) rather than passing it inline. Inline JSON in zsh/bash is prone to quote corruption on complex nested structures.

### Adding a Formula Property (Working)

```bash
curl -X PATCH "https://api.notion.com/v1/databases/${DATABASE_ID}" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "sleep_efficiency_pct": {
        "formula": {
          "expression": "round((prop(\"sleep_time_in_bed_min\") / prop(\"sleep_time_asleep_min\")) * 100)"
        }
      }
    }
  }'
```

### Confirmed: `PATCH /v1/databases/{id}` Works for Adding Properties Post-Creation

You do not need to delete and recreate the database to add new properties. PATCH correctly adds new columns without disrupting existing data.

---

## Critical Limitation: Formula Cannot Reference Formula

**The Notion API does not allow a formula property to reference another formula property at schema-creation time.**

This is the most important limitation to understand before writing formula properties.

**What fails:**
```json
{
  "hr_dip_category": {
    "formula": {
      "expression": "if(prop(\"hr_dip_pct\") >= 15, \"Normal\", ...)"
    }
  }
}
```
If `hr_dip_pct` is itself a formula, the above will fail with a Notion API error.

**The workaround — inline computation:**

Embed the full formula computation directly, without referencing the intermediate formula:

```json
{
  "hr_dip_category": {
    "formula": {
      "expression": "if(prop(\"hr_day_avg_bpm\") == 0, \"No data\", if(round(((prop(\"hr_day_avg_bpm\") - prop(\"hr_sleep_avg_bpm\")) / prop(\"hr_day_avg_bpm\")) * 100) >= 15, \"Normal\", if(round(((prop(\"hr_day_avg_bpm\") - prop(\"hr_sleep_avg_bpm\")) / prop(\"hr_day_avg_bpm\")) * 100) >= 10, \"Borderline\", \"Non-dipping\")))"
    }
  }
}
```

This is verbose but required. The inline approach was confirmed working via API during thread development.

---

## Confirmed Working Formula Definitions

All expressions below are **verified directly from the live Notion database via API (2026-04-06)**. No guesswork.

Note on formula syntax: Notion's internal representation uses URL-encoded property reference tokens. The expressions below have been decoded to use human-readable `prop("field_name")` syntax — this is the format you must use when writing new formulas via API PATCH.

### `sleep_efficiency_pct`
```
round((prop("sleep_time_asleep_min") / prop("sleep_time_in_bed_min")) * 100)
```

### `hr_dip_pct`
```
round((((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100) * 10) / 10
```
Note: rounds to 1 decimal place (×10 then /10 trick).

### `hr_dip_category`
Inline computation — no formula-to-formula reference. Categories: Normal (≥15%), Borderline (10–14%), Non-dipping (<10%):
```
if(round(((((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100) * 10) / 10) >= 15, "Normal", if(round(((((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100) * 10) / 10) >= 10, "Borderline", "Non-dipping"))
```

### `day_of_week`
```
formatDate(prop("date"), "dddd")
```

### `flag_deep_sleep_low`
```
prop("sleep_deep_min") < 35
```

### `flag_deep_gate_50`
```
prop("sleep_deep_min") < 50
```

### `flag_hrv_very_low`
```
prop("hrv_sdnn_ms") < 40
```

### `flag_rhr_elevated`
```
prop("rhr_bpm") > 68
```

### `flag_resp_rate_high`
```
prop("resp_rate_brpm") > 18
```
Note: threshold is `> 18` (not `>= 19` as documented in coaching-layer.md — these are equivalent for integers but the formula uses strict greater-than 18).

### `flag_spo2_low`
```
prop("spo2_min_pct") < 90
```
Note: uses `spo2_min_pct` (nightly minimum), not `spo2_avg_pct`. Threshold is 90, not 92. Update `coaching-layer.md` scoring modifiers accordingly.

### `flag_sleep_fragmented`
```
(prop("sleep_awakenings_count") >= 5) or (prop("sleep_longest_wake_min") > 15)
```
Note: threshold is ≥5 awakenings (not ≥4 as previously documented), and also triggers on longest single wake > 15 min.

### `flag_early_wake`
```
(prop("sleep_waketime_num") >= 330) and (prop("sleep_waketime_num") <= 445)
```
Note: triggers between minutes 330–445 after midnight = 5:30 AM–7:25 AM window. This is not an "early wake" flag in the intuitive sense — it appears to flag waking within a specific target window. Confirm intent with user before relying on this.

### `flag_recovery_red_gate`
```
(((prop("hrv_sdnn_ms") < 40) and (prop("sleep_deep_min") < 35)) or (prop("rhr_bpm") > 68)) or (prop("spo2_min_pct") < 90)
```
Note: broader than documented — triggers on ANY of: (HRV<40 AND deep<35), RHR>68, OR SpO2 min<90. The SpO2 component was not in the original spec.

---

## Anti-Patterns (Do Not Repeat)

| Anti-Pattern | Problem | Resolution |
|---|---|---|
| Multi-line curl in zsh | Shell parsing errors on line breaks in JSON strings | Write JSON to file; use `curl -d @payload.json` |
| Long inline JSON paste in terminal | Quote corruption on copy-paste | Same as above |
| Formula referencing formula | Notion API rejects at schema time | Use inline computation (embed the sub-formula expression directly) |
| Creating all properties in one POST | Timeouts or silent partial application | Use staged batch: base schema first, formulas one at a time via PATCH |

---

## Environment Setup

The Notion integration token used during development is `ntn_579291266875...`. **This token is likely compromised** (it was included in a message shared with an AI assistant). Regenerate it before any further use:

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Find the Cornflower Health integration
3. Click "Show token" → "Regenerate"
4. Update your local `.env` file with the new token
5. The integration still has access to the database — only the token string changes

---

*Last updated: 2026-04-06 — Rescued from Thread Report April 5 short*
