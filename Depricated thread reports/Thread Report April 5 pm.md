<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Thread Report

## 1. Thread scope

Getting a first-time Make.com user to extract specific Apple Health metrics (HRV, resting heart rate, respiratory rate, wrist temperature, daily average heart rate, blood oxygen) from a Health Auto Export webhook payload and map them to variables for insertion into a Notion database.

## 2. Confirmed facts

- Webhook module successfully receives JSON from Health Auto Export (iOS) via REST API automation.
- Payload structure: `data.metrics[]` array where each metric has `name`, `units`, and `data[]` array with daily entries containing `qty`, `date`, `source`, and sometimes `Avg`/`Min`/`Max`.
- Notion database exists: "Daily Health Metrics" (ID: `339d7cd8531f819f85b2c769696ea27c`).
- User is a Make.com beginner preferring copy-paste formulas over visual mapping.
- Exact metric names in payload: `heart_rate_variability`, `resting_heart_rate`, `respiratory_rate`, `apple_sleeping_wrist_temperature`, `heart_rate`, `blood_oxygen_saturation`.
- `heart_rate` entries have `.Avg` field; others use `.qty`.
- Only `yesterday_date` and `hrv_sdnn_ms` variables produced correct values; all others returned empty or wrong data.


## 3. Attempts made

- **Set Multiple Variables module** with complex nested formulas using `map()`, `filter()`, `get()`, `last()`, `first()`, `indexOf()`.
- Formula pattern 1: `first(filter(1.data.metrics; name = "...").data; parseDate(...) = ...).qty` — failed (function not found).
- Formula pattern 2: `get(last(filter(...)).data).qty` — failed (function not found).
- Formula pattern 3: `get(last(map(... ? ... : null)).data).qty` — failed (invalid key error).
- Formula pattern 4: `first(map(1.data.metrics; "data"; "name"; "...")).qty` — returned full array, not single value.
- Formula pattern 5 (working for HRV only): `last(map(get(first(map(1.data.metrics; "data"; "name"; "heart_rate_variability")); "data"); "qty"))`.
- Same pattern applied to other metrics — all returned empty or wrong values.
- Index-based access attempt: `get(1.data.metrics[10]; "data")` — syntax error (red bracket).
- Debug formula: `map(1.data.metrics; "name")` — suggested but not executed.


## 4. What failed or proved fragile

- All `filter()`-based formulas: Make reported "Function 'filter' not found!"
- All `get()` + `last()` + `map()` chains for metrics other than `heart_rate_variability`: returned empty or incorrect values.
- Index-based array access (`1.data.metrics[10]`): Make's parser rejected syntax.
- Copy-paste approach: Make's formula engine treated some pasted formulas as literal text strings instead of executable code.
- Formula consistency: Identical formula structure worked for `heart_rate_variability` but failed for `resting_heart_rate`, `respiratory_rate`, etc., suggesting Make bug or hidden payload differences.
- Error messages: Unhelpful ("Function 'get' finished with error!") — no actionable debugging info.


## 5. What appeared to work

- Webhook module: Successfully captured full JSON payload from Health Auto Export.
- `yesterday_date` formula: `{{formatDate(addDays(now; -1); "YYYY-MM-DD")}}` → correctly produced `2026-04-04`.
- `hrv_sdnn_ms` formula: `{{last(map(get(first(map(1.data.metrics; "data"; "name"; "heart_rate_variability")); "data"); "qty"))}}` → correctly produced `51.25`.
- Basic variable creation and scenario execution flow.


## 6. Recommendations made in this thread

1. **Array Aggregator module approach** (delete Set Multiple Variables, use Tools → Array Aggregator with filters per metric) — **Still plausible** (identified as best bet, not yet tested).
2. **Index-based direct access** (e.g., `1.data.metrics[0].data[-1].qty`) — **Likely outdated** (syntax rejected by Make, fragile if metric order changes).
3. **JSON Parse module** (Tools → JSON → Parse JSON with JSONPath) — **Still plausible** (not tested, cleaner separation).
4. **Visual mapping via right-panel mapper** (click through webhook output instead of formulas) — **Superseded** (user explicitly rejected due to excessive clicks).
5. **Debug with `map(1.data.metrics; "name")`** to verify exact metric names — **Still plausible** (not executed, could reveal whitespace/casing issues).
6. **Use `indexOf(map(...; "name"); "...")` pattern** — **Likely outdated** (tested, returned empty/wrong values).

## 7. Artifacts worth preserving

- **Working HRV formula** (template for potential fix):

```
{{last(map(get(first(map(1.data.metrics; "data"; "name"; "heart_rate_variability")); "data"); "qty"))}}
```

- **Working date formula**:

```
{{formatDate(addDays(now; -1); "YYYY-MM-DD")}}
```

- **Payload structure reference**:

```json
{
  "data": {
    "metrics": [
      {
        "name": "metric_name",
        "units": "...",
        "data": [{"qty": 51.25, "date": "...", "source": "..."}]
      }
    ]
  }
}
```

- **Notion field mapping target**:
    - `Entry` ← `yesterday_date`
    - `date` ← `yesterday_date`
    - `hrv_sdnn_ms` ← HRV formula
    - `rhr_bpm` ← resting heart rate formula
    - `resp_rate_brpm` ← respiratory rate formula
    - `wrist_temp_abs` ← wrist temperature formula
    - `hr_day_avg_bpm` ← heart rate `.Avg` formula
    - `spo2_avg_pct` ← blood oxygen formula / 100
    - `source_tags` ← `["Apple Health"]`


## 8. Open questions left unresolved

- Why does the identical formula pattern work for `heart_rate_variability` but fail for all other metrics?
- Is there invisible whitespace, casing difference, or special character in failing metric names?
- Does Make's formula engine have a limit on nested `map()` calls per module?
- Would Array Aggregator approach actually succeed where Set Multiple Variables failed?
- Is the payload structure stable across daily runs, or does metric order/availability vary?
- Would JSON Parse module with JSONPath be more reliable than formula-based extraction?


## 9. Usefulness score

**3/5** — Successfully established webhook connectivity and proved one metric extraction works, but core problem (extracting 5 other metrics) remains unsolved. Provides clear failure patterns and one promising alternative direction (Array Aggregator), but no working end-to-end solution yet. High frustration-to-progress ratio.

## 10. Repo-ready summary

**Thread: Make.com Formula Extraction Failures (April 5, 2026)** — First attempt to map Apple Health webhook data to Notion variables using Make.com's Set Multiple Variables module. Webhook integration succeeded; date calculation and HRV extraction worked with complex nested `map()` formulas. However, identical formula patterns failed for resting heart rate, respiratory rate, wrist temperature, daily average heart rate, and blood oxygen—returning empty or incorrect values despite matching payload structure. Make's formula engine proved fragile with unhelpful error messages ("Function 'filter' not found!", "Function 'get' finished with error!"). Root cause unclear: possible Make bug, hidden payload differences, or formula engine limitation. Recommended pivot: use Array Aggregator modules with filters instead of complex formulas—more verbose but visually debuggable and reportedly more reliable. Thread establishes baseline connectivity and identifies formula-based extraction as high-risk path for this use case.

