# Notion Linked Views — Setup Guide & Templates

This document explains what linked database views are, why each dashboard page
needs them, and provides step-by-step instructions for adding each one manually
in Notion.

**Why manual?** The Notion API's "linked view" endpoint requires an internal
collection UUID that is not publicly documented and behaves differently from the
standard block API. Until that is resolved programmatically, these take about
2 minutes each to set up by hand.

---

## What Is a Linked View?

A linked view embeds a **live, filtered slice** of the Daily Health Metrics
database directly inside a dashboard page. It behaves like a mini-spreadsheet:
rows update automatically whenever the webhook writes new data, and you can
filter, sort, and hide columns without affecting the underlying database.

Every dashboard page currently has a gray placeholder line where a linked view
should go (e.g., "[ linked view — Exertion & Stress ]"). You will delete that
placeholder and replace it with the live view.

---

## General Steps (applies to every view below)

1. Open the target dashboard page in Notion.
2. Find the gray placeholder text line for that section.
3. Click at the end of that line, select all the text, and **delete it**.
4. Click the `+` block button that appears (or type `/`) → search
   **"Linked view"** → select **Linked view of database**.
5. In the picker, select **Daily Health Metrics**.
6. Notion creates a default table view. Click the **view name** (top-left of
   the embedded table) to open the view editor.
7. Apply the filter and property visibility settings from the template below.
8. Click **Done** / close the editor. The view is live.

---

## View Templates

---

### 1. Daily Dashboard — Exertion & Stress

**Page:** 📊 Daily Dashboard
**Section:** Exertion & Stress
**View type:** Gallery
**Filter:** Date = Today
**Properties to show:** `energy_1_5`, `fatigue_level`, `stress_context`,
`hr_day_avg_bpm`, `hr_day_max_bpm`, `workout_type`, `workout_exertion_felt`
**Properties to hide:** Everything else (keep it tight — this is a glance view)

Steps:
- After step 6 above, click the view type icon and switch from **Table** to
  **Gallery**.
- Click **Filter** → **Add a filter** → Property: `date` → Condition:
  **is** → Value: **Today**.
- Click **Properties** → turn off everything except the 7 fields listed above.
- Rename the view: click the view name → type `Today — Exertion & Stress`.

---

### 2. Daily Dashboard — Notes & Log

**Page:** 📊 Daily Dashboard
**Section:** Notes & Log
**View type:** Table
**Filter:** Date = Today
**Properties to show:** `date`, `meds_notes`, `notes`, `stress_context`,
`morning_heaviness`, `afternoon_crash`
**Properties to hide:** Everything else

Steps:
- After step 6, leave view type as **Table**.
- Filter: `date` **is** **Today**.
- Properties: show only the 6 fields above.
- Rename: `Today — Notes & Log`.

---

### 3. Daily Dashboard — Workout Log

**Page:** 📊 Daily Dashboard
**Section:** Workout Log
**View type:** Table
**Filter:** Date = Today
**Properties to show:** `date`, `workout_rest_day`, `workout_type`,
`workout_total_min`, `workout_exertion_felt`, `workout_z2_min`,
`workout_z3_min`, `workout_z4_min`, `workout_summary`
**Properties to hide:** Everything else

Steps:
- After step 6, leave view type as **Table**.
- Filter: `date` **is** **Today**.
- Properties: show only the 9 fields above.
- Rename: `Today — Workout Log`.

---

### 4. Trends — Each Time-Window Section (×4)

**Page:** 📈 Trends
**Sections:** Last 5 days / Last 10 days / Last 20 days / Last 40 days
**View type:** Table
**Filter:** Date is in the last N days (set N to match the section heading)
**Properties to show:** `date`, `hrv_sdnn_ms`, `rhr_bpm`, `sleep_time_asleep_min`,
`sleep_deep_min`, `sleep_rem_min`, `sleep_efficiency_pct`, `hr_dip_pct`,
`hr_dip_category`, `resp_rate_brpm`, `spo2_avg_pct`, `recovery_score`
**Sort:** `date` descending (newest first)

Steps (repeat for each of the 4 sections):
- After step 6, leave view type as **Table**.
- Filter: `date` **is within** → select **the past week** for 5-day,
  **the past 2 weeks** for 10-day. For 20-day and 40-day, use
  **is after** → type the date manually (today minus 20 or 40 days),
  since Notion's relative presets only go to 4 weeks.
- Properties: show the 12 fields above.
- Sort: `date` descending.
- Rename: `Last 5 Days`, `Last 10 Days`, `Last 20 Days`, `Last 40 Days`.

> **Tip for 20/40-day filters:** Instead of a fixed date, use
> **Date** → **is on or after** → **exact date** and update it monthly,
> OR just use the "past month" / "past 2 months" presets — close enough
> for trend review.

---

### 5. Flags & Alerts — Active Flags

**Page:** 🚩 Flags & Alerts
**Section:** Top section (main content area)
**View type:** Table
**Filter:** (date is in the last 14 days) AND (any flag property = true)
**Properties to show:** `date`, `flag_deep_sleep_low`, `flag_rhr_elevated`,
`flag_hrv_very_low`, `flag_recovery_red_gate`, `flag_resp_rate_high`,
`flag_spo2_low`, `flag_sleep_fragmented`, `flag_early_wake`,
`recovery_score`, `hrv_sdnn_ms`, `rhr_bpm`
**Sort:** `date` descending

Steps:
- After step 6, leave view type as **Table**.
- Filter: click **Add a filter** → `date` **is within** → **the past 2 weeks**.
- Click **Add a filter** again and add a second condition (Notion will AND
  them by default):
  - Property: `flag_recovery_red_gate` → **is** → **checked**.
  - Repeat for each flag field you want to surface, connected with **OR**
    (click the connector between filter lines to switch from AND to OR).
  - Simplest approach: just filter on `date` last 14 days and leave all
    rows visible — the flag columns will show ✓/blank and you can sort
    by any flag column to bubble up flagged days.
- Properties: show the 12 fields above.
- Sort: `date` descending.
- Rename: `Last 14 Days — Flags`.

---

### 6. Full Data Table — All Records

**Page:** 📋 Full Data Table
**Section:** Main section
**View type:** Table
**Filter:** None (show all rows)
**Properties to show:** All properties (or at minimum: `date`, all metric
fields, all flag fields — hide manual/workout fields if you prefer a cleaner
view)
**Sort:** `date` descending

Steps:
- After step 6, leave view type as **Table**.
- No filter needed.
- Properties: click **Properties** → **Show all** to expose every field,
  then optionally hide `notes`, `meds_notes`, `stress_context` if you
  want a tighter numeric view.
- Sort: `date` descending.
- Rename: `All Data`.

---

## Troubleshooting

**"Daily Health Metrics" doesn't appear in the database picker**
The Notion integration must have access to the database. Go to the database
page → click `•••` (top right) → **Add connections** → find the integration.

**The placeholder line can't be deleted**
Click just before the first character in the line, then Shift+End to select
to the end of the line, then Delete. Or place cursor anywhere on the line and
use the block handle (`⋮⋮`) on the left to delete the entire block.

**Filter shows no rows for "Today"**
The date property must be a Notion **Date** type (not plain text). All rows
written by the backend use a proper Date property, so this should resolve
once data exists for today.

**The view shows all columns and is very wide**
Click the `···` overflow menu in the top-right of the embedded view →
**Properties** → turn off the columns you don't need.

---

## Maintenance Notes

- Linked views are read-only from the dashboard pages. To edit data, open
  the **Daily Health Metrics** database directly.
- Adding a new view to a dashboard page does not affect the database or
  any other page.
- If the database schema changes (new fields added by the backend), open
  each view's **Properties** panel to expose the new field.
