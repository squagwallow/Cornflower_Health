# Notion API Implementation Notes

This document captures hard-won knowledge from building the Daily Health Metrics database via the Notion API. Read before attempting any database creation, property addition, or formula deployment.

**Source:** Rescued from Thread Report April 5 short (April 5–6, 2026). This information was previously only in deprecated thread reports.

---

## Database Identity

> **Security note:** These IDs are safe to store in the repo (they are not secrets). The integration token is a secret — never commit it. See `.env.example`.

| Item | Value |
|---|---|
| Database name | Daily Health Metrics |
| Database ID (for API calls) | `339d7cd8-531f-81f5-be5d-000bc78ce4eb` |
| Database URL | `https://www.notion.so/339d7cd8531f819f85b2c769696ea27c` |
| Parent page ID | `339d7cd8-531f-800b-b02d-efefaa086bf5` |
| Parent page name | Cornflower Health |
| Data source (collection) ID | `collection://339d7cd8-531f-81f5-be5d-000bc78ce4eb` |

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

These formulas were successfully deployed to the database via API.

### `sleep_efficiency_pct`
```
round((prop("sleep_time_asleep_min") / prop("sleep_time_in_bed_min")) * 100)
```
Note: The repo integration report uses `sleep_total_min` as the numerator, but the Notion field is `sleep_time_asleep_min`. Verify the correct interpretation (total sleep vs. time asleep) against a real payload before finalizing.

### `hr_dip_pct`
```
round(((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100)
```
Returns 0 if `hr_day_avg_bpm` is 0. Add null guard in production: `if(prop("hr_day_avg_bpm") == 0, 0, round(...))`.

### `hr_dip_category`
Inline computation — no formula-to-formula reference:
```
if(prop("hr_day_avg_bpm") == 0, "No data", if(round(((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100) >= 15, "Normal dipper", if(round(((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm")) / prop("hr_day_avg_bpm")) * 100) >= 10, "Borderline", "Non-dipping")))
```

### `flag_deep_sleep_low`
Exact definition not yet recovered from thread. Known threshold: `sleep_deep_min < 35`. Probable formula:
```
prop("sleep_deep_min") < 35
```
**Status: needs verification from thread or real formula inspection.**

### `flag_deep_gate_50`
Known threshold: `sleep_deep_min < 50`. Probable formula:
```
prop("sleep_deep_min") < 50
```
**Status: needs verification.**

### `flag_rhr_elevated`
Known threshold: `rhr_bpm > 68`. Probable formula:
```
prop("rhr_bpm") > 68
```
**Status: needs verification.**

### `flag_hrv_very_low`
Known threshold: `hrv_sdnn_ms < 40`. Probable formula:
```
prop("hrv_sdnn_ms") < 40
```
**Status: needs verification.**

### `flag_recovery_red_gate`
Hard gate: HRV < 40 AND deep < 35. Probable formula:
```
and(prop("hrv_sdnn_ms") < 40, prop("sleep_deep_min") < 35)
```
**Status: needs verification.**

### `flag_resp_rate_high`
Known threshold: `resp_rate_brpm >= 19`. Probable formula:
```
prop("resp_rate_brpm") >= 19
```
**Status: needs verification.**

### `flag_spo2_low`
Known threshold: SpO2 below acceptable range. Probable formula:
```
prop("spo2_avg_pct") < 0.92
```
Note: `spo2_avg_pct` is stored as `percent` number format in Notion. Verify whether the formula compares against decimal (0.92) or percent (92) depending on how Notion formula engine interprets the stored value.

### `flag_sleep_fragmented`
Known trigger: high awakening count or awake time. Probable formula:
```
or(prop("sleep_awakenings_count") >= 4, prop("sleep_awake_min") >= 60)
```
**Status: needs verification.**

### `flag_early_wake`
Known trigger: wake time before approximately 5:00 AM. Uses `sleep_waketime_num` (minutes after midnight):
```
and(prop("sleep_waketime_num") > 0, prop("sleep_waketime_num") <= 300)
```
**Status: needs verification.**

### `day_of_week`
```
formatDate(prop("date"), "dddd")
```
**Status: confirmed deployed.**

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
