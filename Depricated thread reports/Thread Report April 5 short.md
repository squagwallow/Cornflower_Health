<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Thread Report

## 1. Thread scope

- Generate and execute Notion `databases.create` API payload + script for "Daily Health Metrics" schema (detailed field list with formulas, selects, checkboxes).
- Troubleshoot API errors (401 unauthorized, 400 validation_error "Type error with formula") using curl and iterative fixes.
- Batch-add formula properties to existing database via `PATCH /v1/databases/{id}`.


## 2. Confirmed facts

- Parent page ID: `339d7cd8-531f-800b-b02d-efefaa086bf5` ("Cornflower Health").
- Working integration token (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) passed `/v1/users/me`.
- Base database created successfully: ID `339d7cd8-531f-819f-85b2-c769696ea27c`.
- `PATCH /v1/databases/{id}` works for adding properties.
- Formula properties can be added post-creation.
- `hr_dip_category` referencing `hr_dip_pct` (both formulas) fails with "Type error with formula"; inline computation from raw fields succeeds.


## 3. Attempts made

- Inline curl with full schema JSON (failed 400 formula validation).
- Python script `daily_health_metrics.py` with schema as dict (not executed in thread).
- Batch 1: No-formula base schema via `POST /v1/databases` (succeeded).
- Batch 2: One-by-one formula adds (`day_of_week`, `sleep_efficiency_pct`, `hr_dip_pct`, inline `hr_dip_category`) via `PATCH`.
- Single-condition `hr_dip_category` tests (failed).
- Inline dip computation for `hr_dip_category` (succeeded).
- `flag_deep_sleep_low` add (succeeded).


## 4. What failed or proved fragile

- Full schema `POST` with all formulas: 400 "Type error with formula".
- `hr_dip_category` referencing formula `hr_dip_pct`: 400 "Type error with formula" (API limitation: formulas can't reference other formulas at schema time).
- Multi-line curl (zsh misparsed as separate commands).
- Long inline JSON paste (quote corruption, emoji mangling).
- Formula referencing formula properties (fragile/unreliable via API).


## 5. What appeared to work

- Token validation via `/v1/users/me`.
- Base database creation (batch 1).
- Simple formula adds (`day_of_week`, `sleep_efficiency_pct`, `hr_dip_pct`).
- Inline formula computation avoiding formula refs.
- `flag_deep_sleep_low` checkbox formula.


## 6. Recommendations made in this thread

- Regenerate/refresh Notion token and share page with integration: **Still plausible**.
- Use staged batches (base then formulas): **Still plausible** (proven effective).
- Inline computation for interdependent formulas: **Still plausible** (worked for `hr_dip_category`).
- Python script for shell quoting: **Still plausible** (not executed but prepared).
- One-by-one property adds via PATCH: **Still plausible** (worked).
- Skip complex formula refs: **Still plausible** (circumvented limitation).


## 7. Artifacts worth preserving

- Full "Daily Health Metrics" schema (fields, formulas, select options).
- Working base payload structure.
- Inline dip formula: `round((((prop("hr_day_avg_bpm") - prop("hr_sleep_avg_bpm"))

