"""
Dashboard Daily Update Script
Cornflower Health project — src/update_dashboard.py

Reads config/dashboard_ids.json, queries today's Notion row + recent rows,
computes the recovery score, and updates all scripted sections of the Daily
Dashboard via PATCH /v1/blocks/{id}.

Usage:
    python src/update_dashboard.py [--dry-run] [--date YYYY-MM-DD]

Reuses:
    - src/recovery_score.py  (recovery scoring algorithm)
    - Notion API patterns from src/notion_writer.py

Reference:
    - docs/dashboard-design.md  (block layout and section spec)
    - docs/coaching-layer.md    (recovery scoring algorithm)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is importable when run as `python src/update_dashboard.py`
sys.path.insert(0, str(Path(__file__).parent))

from recovery_score import (
    compute_recovery,
    compute_booster_decision,
)

logger = logging.getLogger("cornflower.update_dashboard")

# --- Config ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "339d7cd8-531f-819f-85b2-c769696ea27c"
)
NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"

CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "dashboard_ids.json"

# Rolling average windows per design spec
ROLLING_WINDOWS = [5, 10, 20, 40]


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _setup_logging() -> str:
    """Configure logging to file and stderr. Returns the log file path."""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = logs_dir / f"update_dashboard_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s — %(message)s")
    )

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(
        logging.Formatter("%(levelname)-7s %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)

    return str(log_file)


# ============================================================
# Config loading
# ============================================================

def load_dashboard_config() -> dict[str, Any]:
    """Load dashboard_ids.json. Raises FileNotFoundError if missing."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Dashboard config not found at {CONFIG_FILE}. "
            "Run deploy_dashboard.py first."
        )
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def get_daily_block_ids(config: dict[str, Any]) -> dict[str, str]:
    """
    Extract the Daily Dashboard block IDs from config.
    Returns a dict mapping section names to block IDs.
    """
    daily = config.get("Daily Dashboard", {})
    blocks = daily.get("blocks", {})

    # Map logical section names to the block keys from deploy_dashboard.py.
    # The deploy script stores blocks as "{type}_{index}" based on the order
    # they appear in build_daily_dashboard_blocks().
    return {
        "recovery_callout": blocks.get("callout_0", ""),
        "breakdown_callout": blocks.get("callout_1", ""),
        "exertion_heading": blocks.get("heading_2_2", ""),
        "exertion_paragraph": blocks.get("paragraph_4", ""),
        "metrics_heading": blocks.get("heading_2_6", ""),
        "metric_hrv": blocks.get("paragraph_8", ""),
        "metric_rhr": blocks.get("paragraph_9", ""),
        "metric_spo2": blocks.get("paragraph_10", ""),
        "metric_resp": blocks.get("paragraph_11", ""),
        "metric_temp": blocks.get("paragraph_12", ""),
        "metric_hr_dip": blocks.get("paragraph_13", ""),
        "sleep_heading": blocks.get("heading_2_14", ""),
        "sleep_total": blocks.get("paragraph_16", ""),
        "sleep_deep_rem": blocks.get("paragraph_17", ""),
        "sleep_core_awake": blocks.get("paragraph_18", ""),
        "sleep_bed_wake": blocks.get("paragraph_19", ""),
        "sleep_in_bed": blocks.get("paragraph_20", ""),
        "flags_toggle": blocks.get("toggle_21", ""),
        "booster_toggle": blocks.get("toggle_22", ""),
        "averages_toggle": blocks.get("toggle_23", ""),
    }


# ============================================================
# Notion API helpers — query and update
# ============================================================

def query_rows(
    date_str: str,
    lookback_days: int,
    client: httpx.Client,
) -> list[dict[str, Any]]:
    """
    Query the Notion database for rows from (date - lookback_days) to date.
    Returns list of row dicts with Notion field values extracted.
    Sorted by date ascending.
    """
    target = datetime.strptime(date_str, "%Y-%m-%d")
    start = (target - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    url = f"{NOTION_BASE}/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "date", "date": {"on_or_after": start}},
                {"property": "date", "date": {"on_or_before": date_str}},
            ]
        },
        "sorts": [{"property": "date", "direction": "ascending"}],
        "page_size": 100,
    }

    all_results: list[dict] = []
    has_more = True
    next_cursor = None

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor

        for attempt in range(2):
            try:
                resp = client.post(url, headers=_headers(), json=payload)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "1"))
                    logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = resp.json()
                all_results.extend(data.get("results", []))
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")
                break
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "HTTP error querying database (attempt %d): %s %s",
                    attempt + 1, exc.response.status_code,
                    exc.response.text[:300],
                )
                has_more = False
                break
            except Exception as exc:
                logger.error("Error querying database: %s", exc)
                has_more = False
                break
        else:
            has_more = False

    rows = [_extract_row(r) for r in all_results]
    return rows


def _extract_row(page: dict[str, Any]) -> dict[str, Any]:
    """Extract flat field values from a Notion page object."""
    props = page.get("properties", {})
    row: dict[str, Any] = {"page_id": page.get("id")}

    for name, prop in props.items():
        ptype = prop.get("type")

        if ptype == "date":
            date_obj = prop.get("date")
            row[name] = date_obj.get("start") if date_obj else None

        elif ptype == "number":
            row[name] = prop.get("number")

        elif ptype == "rich_text":
            parts = prop.get("rich_text", [])
            row[name] = parts[0].get("plain_text", "") if parts else None

        elif ptype == "title":
            parts = prop.get("title", [])
            row[name] = parts[0].get("plain_text", "") if parts else None

        elif ptype == "multi_select":
            row[name] = [o.get("name") for o in prop.get("multi_select", [])]

        elif ptype == "select":
            sel = prop.get("select")
            row[name] = sel.get("name") if sel else None

        elif ptype == "checkbox":
            row[name] = prop.get("checkbox")

        elif ptype == "formula":
            formula = prop.get("formula", {})
            ftype = formula.get("type")
            if ftype == "number":
                row[name] = formula.get("number")
            elif ftype == "string":
                row[name] = formula.get("string")
            elif ftype == "boolean":
                row[name] = formula.get("boolean")
            else:
                row[name] = None

    return row


def patch_block(
    block_id: str,
    block_payload: dict[str, Any],
    client: httpx.Client | None,
    dry_run: bool = False,
) -> bool:
    """
    Update a single Notion block via PATCH /v1/blocks/{id}.
    Returns True on success, False on failure.
    """
    if not block_id:
        logger.warning("Empty block ID — skipping update")
        return False

    if dry_run:
        block_type = list(block_payload.keys())[0] if block_payload else "unknown"
        logger.info("DRY RUN: would PATCH block %s (type: %s)", block_id, block_type)
        return True

    url = f"{NOTION_BASE}/blocks/{block_id}"

    for attempt in range(2):
        try:
            resp = client.patch(url, headers=_headers(), json=block_payload)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            logger.debug("Updated block %s", block_id)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error updating block %s (attempt %d): %s %s",
                block_id, attempt + 1, exc.response.status_code,
                exc.response.text[:300],
            )
            return False
        except Exception as exc:
            logger.error("Error updating block %s: %s", block_id, exc)
            return False

    logger.error("Gave up updating block %s after 2 attempts", block_id)
    return False


def replace_toggle_children(
    toggle_id: str,
    new_children: list[dict[str, Any]],
    client: httpx.Client | None,
    dry_run: bool = False,
) -> bool:
    """
    Replace children of a toggle block.
    Notion doesn't support PATCH on children directly —
    we must delete existing children then append new ones.
    Returns True on success.
    """
    if not toggle_id:
        logger.warning("Empty toggle ID — skipping")
        return False

    if dry_run:
        logger.info(
            "DRY RUN: would replace %d children in toggle %s",
            len(new_children), toggle_id,
        )
        return True

    # Step 1: Fetch existing children
    try:
        resp = client.get(
            f"{NOTION_BASE}/blocks/{toggle_id}/children",
            headers=_headers(),
        )
        resp.raise_for_status()
        existing = resp.json().get("results", [])
    except Exception as exc:
        logger.error("Error fetching toggle children for %s: %s", toggle_id, exc)
        return False

    # Step 2: Delete each existing child
    for child in existing:
        child_id = child.get("id")
        if not child_id:
            continue
        try:
            resp = client.delete(
                f"{NOTION_BASE}/blocks/{child_id}",
                headers=_headers(),
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                time.sleep(retry_after)
                client.delete(f"{NOTION_BASE}/blocks/{child_id}", headers=_headers())
        except Exception as exc:
            logger.warning("Error deleting child block %s: %s", child_id, exc)

    # Step 3: Append new children
    try:
        resp = client.patch(
            f"{NOTION_BASE}/blocks/{toggle_id}/children",
            headers=_headers(),
            json={"children": new_children},
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Error appending new toggle children to %s: %s", toggle_id, exc)
        return False


# ============================================================
# Formatting helpers — build Notion block payloads
# ============================================================

def _rich_text(content: str, bold: bool = False, color: str = "default") -> dict:
    rt: dict[str, Any] = {
        "type": "text",
        "text": {"content": content},
    }
    annotations: dict[str, Any] = {}
    if bold:
        annotations["bold"] = True
    if color != "default":
        annotations["color"] = color
    if annotations:
        rt["annotations"] = annotations
    return rt


def _paragraph_block(text: str, bold: bool = False, color: str = "default") -> dict:
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [_rich_text(text, bold=bold, color=color)],
        },
    }


def _paragraph_rich_block(rich_text_list: list[dict]) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text_list},
    }


# ============================================================
# Section formatters — each returns a PATCH payload
# ============================================================

def format_recovery_callout(recovery: dict[str, Any]) -> dict[str, Any]:
    """Format Section 1 — Recovery Zone callout PATCH payload."""
    score = recovery.get("score")
    zone = recovery.get("zone", "UNKNOWN")
    emoji = recovery.get("zone_emoji", "⚪")
    color = recovery.get("zone_color", "gray_background")
    desc = recovery.get("zone_desc", "")

    if score is not None:
        hrv_comp = recovery.get("hrv_component", 0)
        rhr_comp = recovery.get("rhr_component", 0)
        # Build a summary line
        text = f"{zone} — {score:.0f}/100\n{desc}"
    else:
        text = "UNKNOWN — Insufficient data for recovery score"

    return {
        "callout": {
            "icon": {"type": "emoji", "emoji": emoji},
            "rich_text": [_rich_text(text)],
            "color": color,
        },
    }


def format_breakdown_callout(recovery: dict[str, Any]) -> dict[str, Any]:
    """Format Section 2 — Recovery Breakdown callout PATCH payload."""
    lines = ["Recovery Breakdown\n"]

    hrv_comp = recovery.get("hrv_component")
    rhr_comp = recovery.get("rhr_component")
    base = recovery.get("base_score")

    if hrv_comp is not None:
        lines.append(f"HRV component:       {hrv_comp:.0f} / 60")
    else:
        lines.append("HRV component:       -- / 60")

    if rhr_comp is not None:
        lines.append(f"RHR component:       {rhr_comp:.0f} / 40")
    else:
        lines.append("RHR component:       -- / 40")

    lines.append("─────────────────────────────")

    if base is not None:
        lines.append(f"Base score:          {base:.0f} / 100")
    else:
        lines.append("Base score:          -- / 100")

    lines.append("")

    # Modifiers
    modifiers = recovery.get("modifiers", [])
    for label, adj, reason in modifiers:
        sign = "+" if adj >= 0 else ""
        lines.append(f"{label}: {sign}{adj:.0f}  ({reason})")

    lines.append("─────────────────────────────")

    score = recovery.get("score")
    if score is not None:
        lines.append(f"Final score:         {score:.0f} / 100")
    else:
        lines.append("Final score:         -- / 100")

    lines.append("")

    # Hard gates
    gates = recovery.get("hard_gates", [])
    if gates:
        gate_names = [g[0] for g in gates]
        lines.append(f"Hard gates: {', '.join(gate_names)}")
    else:
        lines.append("Hard gates: None active")

    text = "\n".join(lines)

    return {
        "callout": {
            "icon": {"type": "emoji", "emoji": "📊"},
            "rich_text": [_rich_text(text)],
            "color": "gray_background",
        },
    }


def _trend_arrow(today: float | None, baseline: float | None, higher_is_better: bool = True) -> str:
    """Return ↑/↓/→ comparing today to baseline."""
    if today is None or baseline is None or baseline == 0:
        return ""
    pct = ((today - baseline) / abs(baseline)) * 100
    if abs(pct) < 2:
        return "→"
    if pct > 0:
        return "↑" if higher_is_better else "↓"
    return "↓" if higher_is_better else "↑"


def _metric_status(value: float | None, low: float | None = None, high: float | None = None) -> str:
    """Return ✅/⚠️/🔴 based on range."""
    if value is None:
        return ""
    if low is not None and value < low:
        return "🔴"
    if high is not None and value > high:
        return "⚠️"
    return "✅"


def format_key_metrics(
    today: dict[str, Any], baselines_7d: dict[str, float], baselines_60d: dict[str, float],
) -> list[tuple[str, dict[str, Any]]]:
    """
    Format Section 4 — Key Metrics. Returns list of (section_name, patch_payload) tuples
    for each metric line.
    """
    results = []

    # HRV
    hrv = today.get("hrv_sdnn_ms")
    hrv_7d = baselines_7d.get("hrv_sdnn_ms")
    hrv_60d = baselines_60d.get("hrv_sdnn_ms")
    arrow = _trend_arrow(hrv, hrv_60d, higher_is_better=True)
    hrv_str = f"{hrv:.1f}" if hrv is not None else "--"
    b7 = f"{hrv_7d:.1f}" if hrv_7d is not None else "--"
    b60 = f"{hrv_60d:.1f}" if hrv_60d is not None else "--"
    text = f"HRV:  {hrv_str} ms  (7d: {b7} | 60d: {b60}) {arrow}"
    results.append(("metric_hrv", {"paragraph": {"rich_text": [_rich_text(text, bold=True)]}}))

    # RHR
    rhr = today.get("rhr_bpm")
    rhr_7d = baselines_7d.get("rhr_bpm")
    rhr_60d = baselines_60d.get("rhr_bpm")
    arrow = _trend_arrow(rhr, rhr_60d, higher_is_better=False)
    rhr_str = f"{rhr:.0f}" if rhr is not None else "--"
    b7 = f"{rhr_7d:.1f}" if rhr_7d is not None else "--"
    b60 = f"{rhr_60d:.1f}" if rhr_60d is not None else "--"
    text = f"RHR:  {rhr_str} bpm  (7d: {b7} | 60d: {b60}) {arrow}"
    results.append(("metric_rhr", {"paragraph": {"rich_text": [_rich_text(text, bold=True)]}}))

    # SpO2
    spo2 = today.get("spo2_avg_pct")
    status = _metric_status(spo2, low=92)
    spo2_str = f"{spo2:.0f}" if spo2 is not None else "--"
    text = f"SpO2: {spo2_str}%  {status}"
    results.append(("metric_spo2", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    # Resp rate
    resp = today.get("resp_rate_brpm")
    status = _metric_status(resp, high=18)
    resp_str = f"{resp:.1f}" if resp is not None else "--"
    text = f"Resp: {resp_str} brpm  {status}"
    results.append(("metric_resp", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    # Temp
    temp = today.get("wrist_temp_abs")
    temp_str = f"{temp:.1f}" if temp is not None else "--"
    text = f"Temp: {temp_str}°F"
    results.append(("metric_temp", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    # HR dip
    hr_dip = today.get("hr_dip_pct")
    hr_dip_cat = today.get("hr_dip_category")
    dip_str = f"{hr_dip:.1f}" if hr_dip is not None else "--"
    cat_str = f" ({hr_dip_cat})" if hr_dip_cat else ""
    text = f"HR dip: {dip_str}%{cat_str}"
    results.append(("metric_hr_dip", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    return results


def _fmt_minutes(minutes: float | None) -> str:
    """Format minutes as Xh Ym."""
    if minutes is None:
        return "--"
    h = int(minutes) // 60
    m = int(minutes) % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m} min"


def format_sleep(today: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Format Section 5 — Sleep. Returns list of (section_name, patch_payload) tuples."""
    results = []

    total = today.get("sleep_time_asleep_min")
    eff = today.get("sleep_efficiency_pct")
    eff_str = f"{eff:.0f}" if eff is not None else "--"
    text = f"Total: {_fmt_minutes(total)}  |  Efficiency: {eff_str}%"
    results.append(("sleep_total", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    deep = today.get("sleep_deep_min")
    rem = today.get("sleep_rem_min")
    deep_status = ""
    if deep is not None:
        deep_status = " ✅" if deep >= 50 else (" ⚠️" if deep >= 35 else " 🔴")
    text = f"Deep: {_fmt_minutes(deep)}{deep_status}  |  REM: {_fmt_minutes(rem)}"
    results.append(("sleep_deep_rem", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    core = today.get("sleep_core_min")
    awake = today.get("sleep_awake_min")
    text = f"Core: {_fmt_minutes(core)}  |  Awake: {_fmt_minutes(awake)}"
    results.append(("sleep_core_awake", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    bedtime = today.get("sleep_bedtime") or "--"
    waketime = today.get("sleep_waketime") or "--"
    text = f"Bed: {bedtime} → Wake: {waketime}"
    results.append(("sleep_bed_wake", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    in_bed = today.get("sleep_time_in_bed_min")
    text = f"In bed: {_fmt_minutes(in_bed)}"
    results.append(("sleep_in_bed", {"paragraph": {"rich_text": [_rich_text(text)]}}))

    return results


def format_flags(today: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Format Section 6 — Flags toggle children.
    Returns list of paragraph blocks for toggle children.
    """
    flag_fields = [
        ("flag_deep_sleep_low", "Deep sleep critically low (< 35 min)"),
        ("flag_deep_gate_50", "Deep sleep below titration gate (< 50 min)"),
        ("flag_hrv_very_low", "HRV critically suppressed (< 40 ms)"),
        ("flag_rhr_elevated", "RHR elevated (> 68 bpm)"),
        ("flag_resp_rate_high", "Resp rate elevated (> 18 brpm)"),
        ("flag_spo2_low", "SpO2 low (min < 90%)"),
        ("flag_sleep_fragmented", "Fragmented sleep"),
        ("flag_early_wake", "Early wake"),
        ("flag_recovery_red_gate", "Recovery red gate active"),
    ]

    active: list[str] = []
    for field, desc in flag_fields:
        val = today.get(field)
        if val is True:
            active.append(f"🟡 {desc}")

    if not active:
        return [_paragraph_block("✅ No flags active today")]

    return [_paragraph_block(line) for line in active]


def format_flags_toggle_text(today: dict[str, Any]) -> str:
    """Return the toggle heading text for flags (with count)."""
    flag_fields = [
        "flag_deep_sleep_low", "flag_deep_gate_50", "flag_hrv_very_low",
        "flag_rhr_elevated", "flag_resp_rate_high", "flag_spo2_low",
        "flag_sleep_fragmented", "flag_early_wake", "flag_recovery_red_gate",
    ]
    count = sum(1 for f in flag_fields if today.get(f) is True)
    if count == 0:
        return "Flags (none active)"
    return f"Flags ({count} active)"


def format_booster(today: dict[str, Any]) -> list[dict[str, Any]]:
    """Format Section 7 — Booster Protocol toggle children."""
    booster = compute_booster_decision(today)
    children = []

    children.append(_paragraph_block(
        f"Decision: {booster['emoji']} {booster['decision']}"
    ))

    # Show gate statuses
    hrv = today.get("hrv_sdnn_ms")
    deep = today.get("sleep_deep_min")
    rhr = today.get("rhr_bpm")

    hrv_ok = "✅" if hrv is not None and hrv >= 48 else "❌"
    deep_ok = "✅" if deep is not None and deep >= 50 else "❌"
    rhr_ok = "✅" if rhr is not None and rhr <= 66 else "❌"

    hrv_str = f"{hrv:.0f}" if hrv is not None else "--"
    deep_str = f"{deep:.0f}" if deep is not None else "--"
    rhr_str = f"{rhr:.0f}" if rhr is not None else "--"

    children.append(_paragraph_block(
        f"HRV ≥48: {hrv_ok} ({hrv_str})  |  Deep ≥50: {deep_ok} ({deep_str})  |  RHR ≤66: {rhr_ok} ({rhr_str})"
    ))

    children.append(_paragraph_block(
        "Protocol: Vyvanse 60mg + Dex 5mg @10am + 5mg @1pm"
    ))

    return children


def compute_rolling_averages(
    rows: list[dict[str, Any]], target_date: str,
) -> dict[int, dict[str, float | None]]:
    """
    Compute rolling averages for each window size.
    Returns {window: {metric: avg_value}}.
    """
    target = datetime.strptime(target_date, "%Y-%m-%d")

    metrics = ["hrv_sdnn_ms", "rhr_bpm", "sleep_deep_min", "hr_dip_pct"]
    result: dict[int, dict[str, float | None]] = {}

    for window in ROLLING_WINDOWS:
        start = target - timedelta(days=window)
        window_rows = [
            r for r in rows
            if r.get("date") and start < datetime.strptime(r["date"], "%Y-%m-%d") <= target
        ]

        avgs: dict[str, float | None] = {}
        for metric in metrics:
            values = [r[metric] for r in window_rows if r.get(metric) is not None]
            avgs[metric] = round(sum(values) / len(values), 1) if values else None

        result[window] = avgs

    return result


def format_rolling_averages(
    rolling: dict[int, dict[str, float | None]],
) -> list[dict[str, Any]]:
    """Format Section 8 — Rolling Averages toggle children."""
    children = []

    # Show 7d and 60d (from baselines) + the 5/10/20/40d windows
    # For simplicity, show each metric with available windows
    metrics = [
        ("HRV", "hrv_sdnn_ms", "ms"),
        ("RHR", "rhr_bpm", "bpm"),
        ("Deep", "sleep_deep_min", "min"),
        ("HR dip", "hr_dip_pct", "%"),
    ]

    for label, key, unit in metrics:
        parts = []
        for window in ROLLING_WINDOWS:
            val = rolling.get(window, {}).get(key)
            if val is not None:
                parts.append(f"{window}d: {val:.1f} {unit}")
            else:
                parts.append(f"{window}d: --")
        text = f"{label}  —  {'  |  '.join(parts)}"
        children.append(_paragraph_block(text))

    return children


def format_exertion_paragraph(today: dict[str, Any], recovery: dict[str, Any]) -> str:
    """Format Section 3 — Exertion scripted paragraph."""
    zone = recovery.get("zone", "UNKNOWN")

    if zone == "GREEN":
        rec = "Zone 2 cleared, cap 60 min"
    elif zone == "YELLOW":
        rec = "Moderate load only, cap 45 min"
    elif zone == "ORANGE":
        rec = "Light activity or active recovery only"
    elif zone == "RED":
        rec = "Rest day — no structured training"
    else:
        rec = "Awaiting recovery data"

    # Yesterday load
    workout_type = today.get("workout_type")
    workout_summary = today.get("workout_summary")
    rest_day = today.get("workout_rest_day")

    if rest_day:
        load = "Yesterday load: Rest day"
    elif workout_summary:
        load = f"Yesterday load: {workout_summary}"
    elif workout_type:
        load = f"Yesterday load: {workout_type}"
    else:
        load = "Yesterday load: (not entered)"

    return f"Exertion rec: {rec}\n{load}"


# ============================================================
# Main update logic
# ============================================================

def run_update(
    date_str: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run the daily dashboard update.

    Args:
        date_str: Target date (YYYY-MM-DD). Defaults to today.
        dry_run: If True, log what would be updated without making API calls.

    Returns:
        Summary dict with update counts and any errors.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    logger.info("Dashboard update — date: %s, dry_run: %s", date_str, dry_run)

    # Load config
    try:
        config = load_dashboard_config()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"status": "error", "message": str(exc), "updated": 0, "errors": 1}

    block_ids = get_daily_block_ids(config)
    if not any(block_ids.values()):
        msg = "No block IDs found in config for Daily Dashboard"
        logger.error(msg)
        return {"status": "error", "message": msg, "updated": 0, "errors": 1}

    # Query Notion
    client = None if dry_run else httpx.Client(timeout=30.0)

    try:
        if not dry_run:
            # Query rows: need up to 60 days back for baselines + rolling averages
            rows = query_rows(date_str, lookback_days=60, client=client)
            logger.info("Queried %d rows from Notion (60-day lookback)", len(rows))

            today_row = None
            for r in rows:
                if r.get("date") == date_str:
                    today_row = r
                    break

            if today_row is None:
                msg = f"No Notion row found for {date_str}"
                logger.error(msg)
                return {"status": "error", "message": msg, "updated": 0, "errors": 1}
        else:
            # In dry-run mode, use placeholder data
            rows = []
            today_row = {"date": date_str}
            logger.info("DRY RUN: using placeholder data for %s", date_str)

        # Compute baselines from queried rows
        baselines_7d = _compute_baseline(rows, date_str, 7)
        baselines_60d = _compute_baseline(rows, date_str, 60)

        # Inject baselines into today_row for recovery score computation
        if today_row.get("hrv_baseline_60d_ms") is None:
            today_row["hrv_baseline_60d_ms"] = baselines_60d.get("hrv_sdnn_ms")
        if today_row.get("rhr_baseline_60d_bpm") is None:
            today_row["rhr_baseline_60d_bpm"] = baselines_60d.get("rhr_bpm")

        # Compute recovery score
        recovery = compute_recovery(today_row)
        logger.info(
            "Recovery: score=%s, zone=%s",
            recovery.get("score"), recovery.get("zone"),
        )

        # Compute rolling averages
        rolling = compute_rolling_averages(rows, date_str)

        # --- Build all update payloads ---
        updates: list[tuple[str, str, dict[str, Any]]] = []
        toggle_updates: list[tuple[str, str, str, list[dict[str, Any]]]] = []

        # Section 1 — Recovery callout
        updates.append((
            "recovery_callout",
            block_ids["recovery_callout"],
            format_recovery_callout(recovery),
        ))

        # Section 2 — Breakdown callout
        updates.append((
            "breakdown_callout",
            block_ids["breakdown_callout"],
            format_breakdown_callout(recovery),
        ))

        # Section 3 — Exertion paragraph
        exertion_text = format_exertion_paragraph(today_row, recovery)
        updates.append((
            "exertion_paragraph",
            block_ids["exertion_paragraph"],
            {"paragraph": {"rich_text": [_rich_text(exertion_text)]}},
        ))

        # Section 4 — Key Metrics
        for section_name, payload in format_key_metrics(today_row, baselines_7d, baselines_60d):
            updates.append((section_name, block_ids[section_name], payload))

        # Section 5 — Sleep
        for section_name, payload in format_sleep(today_row):
            updates.append((section_name, block_ids[section_name], payload))

        # Section 6 — Flags toggle (update heading text + replace children)
        flags_text = format_flags_toggle_text(today_row)
        updates.append((
            "flags_toggle",
            block_ids["flags_toggle"],
            {"toggle": {"rich_text": [_rich_text(flags_text)]}},
        ))
        flags_children = format_flags(today_row)
        toggle_updates.append((
            "flags_toggle_children",
            block_ids["flags_toggle"],
            flags_text,
            flags_children,
        ))

        # Section 7 — Booster toggle (replace children)
        booster_children = format_booster(today_row)
        toggle_updates.append((
            "booster_toggle_children",
            block_ids["booster_toggle"],
            "Booster Protocol",
            booster_children,
        ))

        # Section 8 — Rolling Averages (replace children)
        avg_children = format_rolling_averages(rolling)
        toggle_updates.append((
            "averages_toggle_children",
            block_ids["averages_toggle"],
            "Rolling Averages",
            avg_children,
        ))

        # --- Execute updates ---
        updated = 0
        errors = 0

        for name, bid, payload in updates:
            ok = patch_block(bid, payload, client, dry_run)
            if ok:
                updated += 1
            else:
                errors += 1
                logger.error("Failed to update %s (block %s)", name, bid)

            if not dry_run:
                time.sleep(0.15)  # Rate limiting between patches

        for name, tid, heading_text, children in toggle_updates:
            ok = replace_toggle_children(tid, children, client, dry_run)
            if ok:
                updated += 1
            else:
                errors += 1
                logger.error("Failed to update %s (toggle %s)", name, tid)

            if not dry_run:
                time.sleep(0.15)

        summary = {
            "status": "success" if errors == 0 else "partial",
            "date": date_str,
            "updated": updated,
            "errors": errors,
            "recovery_score": recovery.get("score"),
            "recovery_zone": recovery.get("zone"),
        }

        logger.info(
            "Update complete — %d sections updated, %d errors, "
            "recovery: %s (%s)",
            updated, errors,
            recovery.get("score"), recovery.get("zone"),
        )

        return summary

    finally:
        if client:
            client.close()


def _compute_baseline(
    rows: list[dict[str, Any]], target_date: str, window: int,
) -> dict[str, float]:
    """Compute averages for the given window (days before target_date)."""
    target = datetime.strptime(target_date, "%Y-%m-%d")
    start = target - timedelta(days=window)

    window_rows = [
        r for r in rows
        if r.get("date") and start < datetime.strptime(r["date"], "%Y-%m-%d") <= target
    ]

    metrics = ["hrv_sdnn_ms", "rhr_bpm", "sleep_deep_min", "hr_dip_pct"]
    result: dict[str, float] = {}

    for metric in metrics:
        values = [r[metric] for r in window_rows if r.get(metric) is not None]
        if values:
            result[metric] = round(sum(values) / len(values), 1)

    return result


# ============================================================
# CLI entry point
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update Cornflower Health Daily Dashboard in Notion"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making API calls",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    log_file = _setup_logging()
    logger.info(
        "Dashboard update started — date: %s, dry_run: %s",
        args.date or "today", args.dry_run,
    )
    logger.info("Log file: %s", log_file)

    if not args.dry_run and not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set — cannot update. Use --dry-run to test.")
        sys.exit(1)

    result = run_update(date_str=args.date, dry_run=args.dry_run)

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
