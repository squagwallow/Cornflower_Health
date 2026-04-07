"""
Dashboard Deployment Script
Cornflower Health project — src/deploy_dashboard.py

Creates the 5 dashboard pages under the Cornflower Health parent page in Notion
and populates them with block structures per docs/dashboard-design.md.

Usage:
    python src/deploy_dashboard.py [--dry-run] [--page NAME]

Reuses:
    - Notion API patterns from src/notion_writer.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is importable when run as `python src/deploy_dashboard.py`
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("cornflower.deploy_dashboard")

# --- Config ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "339d7cd8-531f-819f-85b2-c769696ea27c"
)
PARENT_PAGE_ID = "339d7cd8-531f-800b-b02d-efefaa086bf5"
NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"

# Dashboard page names → icons
PAGE_SPECS = {
    "Daily Dashboard": "📊",
    "Trends": "📈",
    "Flags & Alerts": "🚩",
    "Full Data Table": "📋",
    "Settings & Reference": "⚙️",
}

# Config output path
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "dashboard_ids.json"


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
    log_file = logs_dir / f"deploy_dashboard_{timestamp}.log"

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
# Notion API helpers
# ============================================================

def api_create_page(
    parent_id: str, title: str, icon_emoji: str, client: httpx.Client | None,
    children: list[dict] | None = None,
    dry_run: bool = False,
) -> str | None:
    """Create a Notion page (with optional inline children). Returns page ID or None."""
    payload: dict[str, Any] = {
        "parent": {"page_id": parent_id},
        "icon": {"type": "emoji", "emoji": icon_emoji},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
    }
    if children:
        payload["children"] = children

    if dry_run:
        logger.info("DRY RUN: would create page '%s' under %s", title, parent_id)
        return f"dry-run-page-{title.lower().replace(' ', '-')}"

    for attempt in range(2):
        try:
            resp = client.post(
                f"{NOTION_BASE}/pages", headers=_headers(), json=payload
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            page_id = resp.json()["id"]
            logger.info("Created page '%s' — id: %s", title, page_id)
            return page_id
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error creating page '%s' (attempt %d): %s %s",
                title, attempt + 1, exc.response.status_code,
                exc.response.text[:300],
            )
            return None
        except Exception as exc:
            logger.error("Error creating page '%s': %s", title, exc)
            return None
    logger.error("Gave up creating page '%s' after 2 attempts", title)
    return None


def api_append_children(
    block_id: str, children: list[dict], client: httpx.Client | None,
    dry_run: bool = False,
) -> list[dict] | None:
    """Append child blocks to a block. Returns list of created block results."""
    if dry_run:
        logger.info(
            "DRY RUN: would append %d children to block %s", len(children), block_id
        )
        # Return fake results with IDs for downstream reference
        results = []
        for i, child in enumerate(children):
            results.append({
                "id": f"dry-run-block-{block_id[-8:]}-{i}",
                "type": child.get("type", "unknown"),
            })
        return results

    for attempt in range(2):
        try:
            # Notion API: append block children uses PATCH, not POST
            resp = client.patch(
                f"{NOTION_BASE}/blocks/{block_id}/children",
                headers=_headers(),
                json={"children": children},
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            results = resp.json().get("results", [])
            logger.debug(
                "Appended %d children to block %s", len(results), block_id
            )
            return results
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error appending children to %s (attempt %d): %s %s",
                block_id, attempt + 1, exc.response.status_code,
                exc.response.text[:300],
            )
            return None
        except Exception as exc:
            logger.error("Error appending children to %s: %s", block_id, exc)
            return None
    logger.error("Gave up appending children to %s after 2 attempts", block_id)
    return None


def api_fetch_children(
    block_id: str, client: httpx.Client | None,
) -> list[dict]:
    """GET /v1/blocks/{id}/children to retrieve created block IDs after page creation."""
    if not client:
        return []
    try:
        resp = client.get(
            f"{NOTION_BASE}/blocks/{block_id}/children",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception as exc:
        logger.error("Error fetching children of %s: %s", block_id, exc)
        return []


def api_create_view(
    view_payload: dict, client: httpx.Client | None, dry_run: bool = False,
    label: str = "",
) -> str | None:
    """Create a linked database view or chart via POST /v1/views. Returns view ID."""
    if dry_run:
        logger.info("DRY RUN: would create view: %s", label or "unnamed")
        return f"dry-run-view-{label.lower().replace(' ', '-')}"

    for attempt in range(2):
        try:
            resp = client.post(
                f"{NOTION_BASE}/views", headers=_headers(), json=view_payload
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            view_id = resp.json().get("id", "unknown")
            logger.info("Created view '%s' — id: %s", label, view_id)
            return view_id
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error creating view '%s' (attempt %d): %s %s",
                label, attempt + 1, exc.response.status_code,
                exc.response.text[:300],
            )
            return None
        except Exception as exc:
            logger.error("Error creating view '%s': %s", label, exc)
            return None
    logger.error("Gave up creating view '%s' after 2 attempts", label)
    return None


# ============================================================
# Block builder helpers
# ============================================================

def _rich_text(content: str, bold: bool = False, color: str = "default") -> dict:
    """Build a single rich_text annotation object."""
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


def heading_2(text: str) -> dict:
    return {
        "type": "heading_2",
        "heading_2": {
            "rich_text": [_rich_text(text)],
        },
    }


def heading_3(text: str) -> dict:
    return {
        "type": "heading_3",
        "heading_3": {
            "rich_text": [_rich_text(text)],
        },
    }


def divider() -> dict:
    return {"type": "divider", "divider": {}}


def paragraph(text: str, bold: bool = False, color: str = "default") -> dict:
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [_rich_text(text, bold=bold, color=color)],
        },
    }


def paragraph_rich(rich_text_list: list[dict]) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text_list},
    }


def callout(
    text: str, icon_emoji: str, color: str = "default",
    children: list[dict] | None = None,
) -> dict:
    block: dict[str, Any] = {
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": icon_emoji},
            "rich_text": [_rich_text(text)],
            "color": color,
        },
    }
    if children:
        block["callout"]["children"] = children
    return block


def callout_rich(
    rich_text_list: list[dict], icon_emoji: str, color: str = "default",
) -> dict:
    return {
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": icon_emoji},
            "rich_text": rich_text_list,
            "color": color,
        },
    }


def toggle(text: str, children: list[dict] | None = None) -> dict:
    """Toggle block. Children can be nested up to 2 levels deep in one call."""
    block: dict[str, Any] = {
        "type": "toggle",
        "toggle": {
            "rich_text": [_rich_text(text)],
        },
    }
    if children:
        block["toggle"]["children"] = children
    return block


def table_of_contents() -> dict:
    return {"type": "table_of_contents", "table_of_contents": {"color": "default"}}


def bookmark(url: str) -> dict:
    return {"type": "bookmark", "bookmark": {"url": url}}


# ============================================================
# Linked database view builders
# ============================================================

def _linked_view_payload(
    parent_block_id: str,
    title: str,
    visible_properties: list[str],
    sorts: list[dict] | None = None,
    filter_obj: dict | None = None,
    view_type: str = "table",
) -> dict:
    """Build a POST /v1/views payload for a linked database view."""
    payload: dict[str, Any] = {
        "parent": {"block_id": parent_block_id},
        "type": view_type,
        "title": title,
        "create_database": NOTION_DATABASE_ID,
    }
    if visible_properties:
        payload["visible_properties"] = visible_properties
    if sorts:
        payload["sorts"] = sorts
    if filter_obj:
        payload["filter"] = filter_obj
    return payload


def _chart_view_payload(
    parent_block_id: str,
    title: str,
    chart_type: str,
    x_axis: str,
    y_axis: str,
    filter_obj: dict | None = None,
) -> dict:
    """Build a POST /v1/views payload for a chart view."""
    payload: dict[str, Any] = {
        "parent": {"block_id": parent_block_id},
        "type": "chart",
        "title": title,
        "create_database": NOTION_DATABASE_ID,
        "chart": {
            "chart_type": chart_type,
            "x_axis": {"property": x_axis},
            "y_axis": {"property": y_axis},
        },
    }
    if chart_type == "line":
        payload["chart"]["gradient_fill"] = True
        payload["chart"]["smooth_line"] = True
    if filter_obj:
        payload["filter"] = filter_obj
    return payload


def _date_filter_last_n_days(n: int) -> dict:
    """Build a Notion filter for 'date is within last N days'."""
    return {
        "property": "date",
        "date": {"past_week": {} if n == 7 else {"type": "relative", "relative": {"amount": n, "unit": "day"}}},
    }


def _date_relative_filter(n: int) -> dict:
    """Build a relative date filter for the last N days."""
    return {
        "property": "date",
        "date": {"on_or_after": f"{{{{now|date_add(-{n}, 'days')}}}}"},
    }


# ============================================================
# Page content builders — one function per dashboard page
# ============================================================

def build_daily_dashboard_blocks() -> list[dict]:
    """Build the block structure for the Daily Dashboard page (Page 1)."""
    blocks = []

    # Section 1 — Recovery Zone [SCRIPTED] — placeholder
    blocks.append(callout(
        "GREEN — 0/100\nAwaiting first daily update. Run update_dashboard.py to populate.",
        "🟢",
        "green_background",
    ))

    # Section 2 — Recovery Breakdown [SCRIPTED] — placeholder
    blocks.append(callout(
        "Recovery Breakdown\n\n"
        "HRV component:       -- / 60\n"
        "RHR component:       -- / 40\n"
        "---\n"
        "Base score:          -- / 100\n\n"
        "Modifiers:           (awaiting data)\n"
        "---\n"
        "Final score:         -- / 100\n\n"
        "Hard gates: (awaiting data)",
        "📊",
        "gray_background",
    ))

    # Section 3 — Exertion / Stress / Energy
    blocks.append(heading_2("Exertion & Stress"))
    blocks.append(divider())
    # Scripted paragraph — placeholder for update script
    blocks.append(paragraph(
        "Exertion rec: (awaiting data)\nYesterday load: (awaiting data)"
    ))
    # NOTE: Linked DB view for subjective fields will be created after page exists
    # (needs the block ID of a parent to attach to)
    blocks.append(paragraph(
        "[Linked view: today's subjective fields — created after page deploy]",
        color="gray",
    ))

    # Section 4 — Key Metrics [SCRIPTED] — placeholder
    blocks.append(heading_2("Key Metrics"))
    blocks.append(divider())
    blocks.append(paragraph("HRV:  -- ms  (7d: -- | 60d: --) --"))
    blocks.append(paragraph("RHR:  -- bpm  (7d: -- | 60d: --) --"))
    blocks.append(paragraph("SpO2: --%"))
    blocks.append(paragraph("Resp: -- brpm"))
    blocks.append(paragraph("Temp: --\u00b0F"))
    blocks.append(paragraph("HR dip: --% (--)"))

    # Section 5 — Sleep [SCRIPTED] — placeholder
    blocks.append(heading_2("Sleep"))
    blocks.append(divider())
    blocks.append(paragraph("Total: --  |  Efficiency: --%"))
    blocks.append(paragraph("Deep: --  |  REM: --"))
    blocks.append(paragraph("Core: --  |  Awake: --"))
    blocks.append(paragraph("Bed: -- \u2192 Wake: --"))
    blocks.append(paragraph("In bed: --"))

    # Section 6 — Active Flags [SCRIPTED]
    blocks.append(toggle("Flags (awaiting data)", children=[
        paragraph("\u2705 No flags active today (awaiting first update)"),
    ]))

    # Section 7 — Booster Protocol [SCRIPTED]
    blocks.append(toggle("Booster Protocol (awaiting data)", children=[
        paragraph("Decision: (awaiting data)"),
        paragraph("Protocol: Vyvanse 60mg + Dex 5mg @10am + 5mg @1pm"),
    ]))

    # Section 8 — Rolling Averages [SCRIPTED]
    blocks.append(toggle("Rolling Averages", children=[
        paragraph("HRV  \u2014 7d: -- ms  |  60d: -- ms"),
        paragraph("RHR  \u2014 7d: -- bpm  |  60d: -- bpm"),
        paragraph("Deep \u2014 7d: -- min"),
        paragraph("HR dip \u2014 7d: --%"),
    ]))

    # Section 9 — Manual Notes [LINKED VIEW]
    blocks.append(heading_2("Notes & Log"))
    blocks.append(divider())
    # Linked DB view placeholder — created via Views API after page
    blocks.append(paragraph(
        "[Linked view: meds_notes, notes — created after page deploy]",
        color="gray",
    ))
    # BUTTON placeholder — cannot be created via API
    blocks.append(callout(
        "MANUAL STEP: Add 'Log Today's Entry' button here "
        "(action: add page to Daily Health Metrics DB with date=today). "
        "Buttons cannot be created via API.",
        "\u26a0\ufe0f",
        "yellow_background",
    ))

    # Section 10 — Workout Log [LINKED VIEW]
    blocks.append(toggle("Workout Log", children=[
        paragraph(
            "[Linked view: workout fields — created after page deploy]",
            color="gray",
        ),
    ]))

    return blocks


def build_trends_blocks() -> list[dict]:
    """Build the block structure for the Trends page (Page 2).

    Uses standard section headings for each time window.
    Tab/chart UI requires the Notion Views API; add linked DB views
    manually in Notion for each window once the pages are created.
    """
    blocks = []

    for label, days in [("5 Days", 5), ("10 Days", 10), ("20 Days", 20), ("40 Days", 40)]:
        blocks.append(heading_2(f"Trends — {label}"))
        blocks.append(divider())
        blocks.append(paragraph(
            f"[Add linked database view here, filtered to last {days} days]",
            color="gray",
        ))

    return blocks


def build_flags_blocks() -> list[dict]:
    """Build the block structure for the Flags & Alerts page (Page 3)."""
    blocks = []

    blocks.append(heading_2("Flagged Days"))
    blocks.append(divider())

    # Linked DB view placeholder — filtered to flagged days
    blocks.append(paragraph(
        "[Linked view: flagged days table (last 14 days, any flag=true) — "
        "created via Views API after deploy]",
        color="gray",
    ))

    # Flag frequency chart placeholder
    blocks.append(paragraph(
        "[Chart: Flag Frequency (bar) — created via Views API after deploy]",
        color="gray",
    ))

    # Flag definitions toggle
    blocks.append(toggle("Flag Definitions", children=[
        paragraph("flag_deep_sleep_low: sleep_deep_min < 35 — Severe deep sleep deficit"),
        paragraph("flag_deep_gate_50: sleep_deep_min < 50 — Below titration gate"),
        paragraph("flag_hrv_very_low: hrv_sdnn_ms < 40 — Critically suppressed HRV"),
        paragraph("flag_rhr_elevated: rhr_bpm > 68 — Elevated resting heart rate"),
        paragraph("flag_resp_rate_high: resp_rate_brpm > 18 — Elevated respiratory rate"),
        paragraph("flag_spo2_low: spo2_min_pct < 90 — Low nocturnal SpO2"),
        paragraph("flag_sleep_fragmented: awakenings >= 5 OR longest_wake > 15 min"),
        paragraph("flag_early_wake: waketime between 5:30-7:25 AM window"),
        paragraph("flag_recovery_red_gate: (HRV<40 AND deep<35) OR RHR>68 OR SpO2 min<90"),
    ]))

    return blocks


def build_full_table_blocks() -> list[dict]:
    """Build the block structure for the Full Data Table page (Page 4)."""
    blocks = []

    blocks.append(heading_2("Full Data Table"))
    blocks.append(divider())

    # Linked DB view placeholder — full table, all columns
    blocks.append(paragraph(
        "[Linked view: full database table (all columns, sorted date desc) — "
        "created via Views API after deploy]",
        color="gray",
    ))

    # NOTE: Manual steps
    blocks.append(callout(
        "MANUAL STEPS after deploy:\n"
        "- Set 'Show as Bar' display on recovery_score property\n"
        "- Set wrap cells: false\n"
        "- Freeze 'date' column (index 0)\n"
        "- Enable quick filters: source_tags, date range",
        "\u26a0\ufe0f",
        "yellow_background",
    ))

    return blocks


def build_settings_blocks() -> list[dict]:
    """Build the block structure for the Settings & Reference page (Page 5)."""
    blocks = []

    # Current Baselines
    blocks.append(heading_2("Current Baselines"))
    blocks.append(paragraph("HRV 60-day: 53.2 ms", bold=True))
    blocks.append(paragraph("RHR target: 61\u201366 bpm"))
    blocks.append(paragraph("Deep sleep target: \u226550 min"))
    blocks.append(paragraph("Deep sleep floor: \u226535 min"))
    blocks.append(paragraph("HRV hard floor: \u226540 ms"))

    # Recovery Scoring Algorithm toggle
    blocks.append(toggle("Recovery Scoring Algorithm", children=[
        paragraph("HRV component (~60%): hrv_score = (hrv_sdnn_ms / hrv_baseline_60d_ms) * 60, capped at 60"),
        paragraph("RHR component (~40%): rhr_score = clamp(((rhr_baseline - rhr) / rhr_baseline) * 40 + 40, 0, 40)"),
        paragraph("Base score = hrv_score + rhr_score (0\u2013100)"),
        paragraph(""),
        paragraph("Modifiers:", bold=True),
        paragraph("Deep 65\u201380 min: +3 | Deep \u226580 min: +5"),
        paragraph("Deep 35\u201350 min: -5 | Deep 20\u201335 min: -10 | Deep <20 min: -15"),
        paragraph("SpO2 92\u201394%: -3 | SpO2 <92%: -8 | SpO2 min <88%: -5 (stacks)"),
        paragraph("Resp \u226415 brpm: +2 | Resp \u226519 brpm: -5"),
        paragraph("Fragmented sleep (\u22654 awakenings): -5"),
        paragraph("Early wake (<5 AM): -3"),
        paragraph("Stress High/Extreme: -5"),
        paragraph(""),
        paragraph("Hard Gates:", bold=True),
        paragraph("RHR > 68 \u2192 cap at YELLOW"),
        paragraph("Deep < 35 min \u2192 cap at YELLOW"),
        paragraph("HRV < 40 AND Deep < 35 \u2192 force RED"),
    ]))

    # Stimulant Protocol toggle
    blocks.append(toggle("Stimulant Protocol & Decision Tree", children=[
        paragraph("Current: Vyvanse 60mg (AM) + Dex 5mg @10am + Dex 5mg @1pm", bold=True),
        paragraph(""),
        paragraph("Go/No-Go Decision Tree:", bold=True),
        paragraph("1. HRV < 40 ms? \u2192 Skip both boosters (recovery day)"),
        paragraph("2. RHR > 68 bpm? \u2192 Skip both boosters"),
        paragraph("3. Deep < 35 min? \u2192 Skip both boosters"),
        paragraph("4. Deep 35\u201350 AND HRV 40\u201347? \u2192 First booster only"),
        paragraph("5. Deep \u226550 AND HRV \u226548 AND RHR \u226466? \u2192 Both boosters cleared"),
        paragraph(""),
        paragraph("Advancement gates (7 consecutive days):", bold=True),
        paragraph("Deep \u226550 min, HRV \u224850 ms, RHR 61\u201366, no heaviness, no crash"),
    ]))

    # Flag Thresholds toggle
    blocks.append(toggle("Flag Thresholds", children=[
        paragraph("flag_deep_sleep_low: sleep_deep_min < 35"),
        paragraph("flag_deep_gate_50: sleep_deep_min < 50"),
        paragraph("flag_hrv_very_low: hrv_sdnn_ms < 40"),
        paragraph("flag_rhr_elevated: rhr_bpm > 68"),
        paragraph("flag_resp_rate_high: resp_rate_brpm > 18"),
        paragraph("flag_spo2_low: spo2_min_pct < 90"),
        paragraph("flag_sleep_fragmented: awakenings \u2265 5 OR longest_wake > 15 min"),
        paragraph("flag_early_wake: waketime 5:30\u20137:25 AM"),
        paragraph("flag_recovery_red_gate: (HRV<40 AND deep<35) OR RHR>68 OR SpO2 min<90"),
    ]))

    # Zone Mapping toggle
    blocks.append(toggle("Zone Mapping", children=[
        paragraph("\U0001F7E2 GREEN (75\u2013100): Full training cleared"),
        paragraph("\U0001F7E1 YELLOW (50\u201374): Moderate load only"),
        paragraph("\U0001F7E0 ORANGE (25\u201349): Light activity or active recovery"),
        paragraph("\U0001F534 RED (0\u201324): Rest day; no structured training"),
    ]))

    return blocks


# ============================================================
# View creation — called after pages/blocks exist
# ============================================================

def create_daily_dashboard_views(
    page_id: str, block_ids: dict, client: httpx.Client | None, dry_run: bool,
) -> dict[str, str | None]:
    """Create linked DB views for the Daily Dashboard page."""
    view_ids: dict[str, str | None] = {}

    # Exertion section — today's subjective fields (gallery card view)
    exertion_view = _linked_view_payload(
        parent_block_id=page_id,
        title="Today's Subjective Fields",
        visible_properties=[
            "energy_1_5", "stress_context", "fatigue_level",
            "morning_heaviness", "afternoon_crash",
        ],
        sorts=[{"property": "date", "direction": "descending"}],
        view_type="gallery",
    )
    view_ids["exertion_view"] = api_create_view(
        exertion_view, client, dry_run, label="Daily - Exertion subjective"
    )

    # Notes section — meds_notes, notes
    notes_view = _linked_view_payload(
        parent_block_id=page_id,
        title="Notes & Log",
        visible_properties=["date", "meds_notes", "notes"],
        sorts=[{"property": "date", "direction": "descending"}],
    )
    view_ids["notes_view"] = api_create_view(
        notes_view, client, dry_run, label="Daily - Notes"
    )

    # Workout log view
    workout_view = _linked_view_payload(
        parent_block_id=page_id,
        title="Workout Log",
        visible_properties=[
            "date", "workout_type", "workout_total_min",
            "workout_exertion_felt", "workout_z2_min", "workout_z3_min",
            "workout_z4_min", "workout_summary", "workout_rest_day",
        ],
        sorts=[{"property": "date", "direction": "descending"}],
    )
    view_ids["workout_view"] = api_create_view(
        workout_view, client, dry_run, label="Daily - Workout"
    )

    return view_ids


def create_trends_views(
    page_id: str, tab_block_ids: dict, client: httpx.Client | None, dry_run: bool,
) -> dict[str, str | None]:
    """Create chart and table views for each Trends tab."""
    view_ids: dict[str, str | None] = {}

    windows = [5, 10, 20, 40]
    chart_specs = [
        ("HRV Trend", "line", "date", "hrv_sdnn_ms"),
        ("RHR Trend", "line", "date", "rhr_bpm"),
        ("Deep Sleep", "bar", "date", "sleep_deep_min"),
        ("Total Sleep", "bar", "date", "sleep_time_asleep_min"),
        ("SpO2", "line", "date", "spo2_avg_pct"),
        ("Resp Rate", "line", "date", "resp_rate_brpm"),
    ]

    for window in windows:
        tab_id = tab_block_ids.get(f"tab_{window}d")
        if not tab_id:
            logger.warning("No tab block ID for %d-day window, skipping charts", window)
            continue

        date_filter = _date_relative_filter(window)

        for chart_name, chart_type, x_axis, y_axis in chart_specs:
            label = f"Trends {window}d - {chart_name}"
            chart_payload = _chart_view_payload(
                parent_block_id=tab_id,
                title=f"{chart_name} ({window}d)",
                chart_type=chart_type,
                x_axis=x_axis,
                y_axis=y_axis,
                filter_obj=date_filter,
            )
            view_ids[label] = api_create_view(
                chart_payload, client, dry_run, label=label
            )

        # Table view per tab
        table_label = f"Trends {window}d - Table"
        table_payload = _linked_view_payload(
            parent_block_id=tab_id,
            title=f"Recent Days ({window}d)",
            visible_properties=[
                "date", "recovery_score", "hrv_sdnn_ms", "rhr_bpm",
                "sleep_deep_min", "sleep_time_asleep_min", "spo2_avg_pct",
                "source_tags",
            ],
            sorts=[{"property": "date", "direction": "descending"}],
            filter_obj=date_filter,
        )
        view_ids[table_label] = api_create_view(
            table_payload, client, dry_run, label=table_label
        )

    return view_ids


def create_flags_views(
    page_id: str, client: httpx.Client | None, dry_run: bool,
) -> dict[str, str | None]:
    """Create linked DB views for the Flags & Alerts page."""
    view_ids: dict[str, str | None] = {}

    flag_fields = [
        "flag_deep_sleep_low", "flag_deep_gate_50", "flag_hrv_very_low",
        "flag_rhr_elevated", "flag_resp_rate_high", "flag_spo2_low",
        "flag_sleep_fragmented", "flag_early_wake", "flag_recovery_red_gate",
    ]

    # Flagged days table — last 14 days where any flag is true
    flag_filter = {
        "and": [
            _date_relative_filter(14),
            {
                "or": [
                    {"property": f, "formula": {"checkbox": {"equals": True}}}
                    for f in flag_fields
                ]
            },
        ]
    }

    flagged_table = _linked_view_payload(
        parent_block_id=page_id,
        title="Flagged Days (Last 14 Days)",
        visible_properties=[
            "date", "recovery_score", "hrv_sdnn_ms", "rhr_bpm",
            "sleep_deep_min",
        ] + flag_fields,
        sorts=[{"property": "date", "direction": "descending"}],
        filter_obj=flag_filter,
    )
    view_ids["flagged_days_table"] = api_create_view(
        flagged_table, client, dry_run, label="Flags - Flagged days table"
    )

    # Manual step note for conditional row colors
    # (can't set this via API)

    return view_ids


def create_full_table_view(
    page_id: str, client: httpx.Client | None, dry_run: bool,
) -> dict[str, str | None]:
    """Create the full data table linked view."""
    view_ids: dict[str, str | None] = {}

    full_table = _linked_view_payload(
        parent_block_id=page_id,
        title="All Data",
        visible_properties=[],  # Empty = show all
        sorts=[{"property": "date", "direction": "descending"}],
    )
    view_ids["full_table"] = api_create_view(
        full_table, client, dry_run, label="Full Data Table - All"
    )

    return view_ids


# ============================================================
# Nesting handler — Notion's 2-level nesting limit
# ============================================================

def append_blocks_recursive(
    parent_id: str,
    blocks: list[dict],
    client: httpx.Client | None,
    dry_run: bool,
    depth: int = 0,
) -> list[dict]:
    """
    Append blocks to a parent, handling Notion's 2-level nesting limit.

    Notion allows including children up to 2 levels deep in a single
    append call. For deeper nesting, we must:
    1. Append the parent blocks without deep children
    2. Get their IDs
    3. Append the deeper children in a separate call

    Returns the list of created block result objects.
    """
    # Separate blocks that have children needing >2 level nesting
    top_level_blocks = []
    deferred_children: dict[int, list[dict]] = {}

    for i, block in enumerate(blocks):
        block_type = block.get("type", "")
        block_content = block.get(block_type, {})
        children = block_content.get("children", [])

        # Check if any children themselves have children (3+ levels)
        has_deep_nesting = False
        for child in children:
            child_type = child.get("type", "")
            child_content = child.get(child_type, {})
            if child_content.get("children"):
                has_deep_nesting = True
                break

        if has_deep_nesting:
            # Strip grandchildren — append them after parent is created
            stripped_children = []
            grandchildren_map: dict[int, list[dict]] = {}
            for j, child in enumerate(children):
                child_type = child.get("type", "")
                child_content = child.get(child_type, {})
                gc = child_content.pop("children", [])
                if gc:
                    grandchildren_map[j] = gc
                stripped_children.append(child)

            block_copy = json.loads(json.dumps(block))
            block_copy[block_type]["children"] = stripped_children
            top_level_blocks.append(block_copy)
            deferred_children[i] = grandchildren_map  # type: ignore
        else:
            top_level_blocks.append(block)

    # Append top-level blocks
    results = api_append_children(parent_id, top_level_blocks, client, dry_run)
    if results is None:
        return []

    # Handle deferred children (3+ level nesting)
    for block_idx, gc_map in deferred_children.items():
        if block_idx >= len(results):
            continue
        parent_result = results[block_idx]
        parent_block_id = parent_result.get("id", "")

        # The parent block's children are now created — get their IDs
        # We need to read the children of the parent to find child block IDs
        # For simplicity in dry-run, use the results directly
        block_type = parent_result.get("type", "")
        if not parent_block_id:
            continue

        # For each grandchild mapping, we need the child block ID
        # Since we appended children inline, they're already part of the parent.
        # We need to fetch child blocks to get their IDs for grandchild appending.
        if not dry_run and client:
            try:
                resp = client.get(
                    f"{NOTION_BASE}/blocks/{parent_block_id}/children",
                    headers=_headers(),
                )
                resp.raise_for_status()
                child_results = resp.json().get("results", [])
                for child_idx, grandchildren in gc_map.items():
                    if child_idx < len(child_results):
                        child_id = child_results[child_idx]["id"]
                        api_append_children(child_id, grandchildren, client, dry_run)
            except Exception as exc:
                logger.error(
                    "Error fetching children for deep nesting on block %s: %s",
                    parent_block_id, exc,
                )
        elif dry_run:
            for child_idx, grandchildren in gc_map.items():
                fake_child_id = f"dry-run-child-{parent_block_id[-8:]}-{child_idx}"
                api_append_children(fake_child_id, grandchildren, client, dry_run)

    return results


# ============================================================
# Main deployment logic
# ============================================================

def deploy_page(
    page_name: str,
    client: httpx.Client | None,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Deploy a single dashboard page. Returns its ID mapping dict."""
    if page_name not in PAGE_SPECS:
        logger.error("Unknown page name: '%s'. Valid: %s", page_name, list(PAGE_SPECS.keys()))
        return None

    icon = PAGE_SPECS[page_name]
    logger.info("Deploying page: %s %s", icon, page_name)

    # Build block content first
    if page_name == "Daily Dashboard":
        blocks = build_daily_dashboard_blocks()
    elif page_name == "Trends":
        blocks = build_trends_blocks()
    elif page_name == "Flags & Alerts":
        blocks = build_flags_blocks()
    elif page_name == "Full Data Table":
        blocks = build_full_table_blocks()
    elif page_name == "Settings & Reference":
        blocks = build_settings_blocks()
    else:
        blocks = []

    # Create the page WITH inline children in a single API call.
    # POST /v1/blocks/{id}/children is unavailable for this integration token
    # (returns invalid_request_url), but POST /v1/pages with inline children works.
    page_id = api_create_page(
        PARENT_PAGE_ID, page_name, icon, client,
        children=blocks if blocks else None,
        dry_run=dry_run,
    )
    if not page_id:
        return None

    ids: dict[str, Any] = {"page_id": page_id, "views": {}, "blocks": {}}

    # Rate limit between API calls
    if not dry_run:
        time.sleep(0.5)

    # Fetch the created block IDs via GET (this works with our token).
    # IDs are stored as "{type}_{index}" matching what update_dashboard.py expects.
    if blocks and not dry_run and client:
        created = api_fetch_children(page_id, client)
        for i, result in enumerate(created):
            block_type = result.get("type", f"block_{i}")
            block_id = result.get("id", "")
            ids["blocks"][f"{block_type}_{i}"] = block_id
        logger.info(
            "Fetched %d block IDs for '%s'", len(created), page_name
        )
    elif dry_run:
        # Populate fake IDs for downstream dry-run validation
        for i, block in enumerate(blocks):
            block_type = block.get("type", f"block_{i}")
            ids["blocks"][f"{block_type}_{i}"] = f"dry-run-block-{i}"

    # Create linked database views (POST /v1/views).
    # These will be skipped gracefully if the endpoint is unavailable —
    # views can be added manually in Notion after deploy.
    try:
        if page_name == "Daily Dashboard":
            view_ids = create_daily_dashboard_views(page_id, ids["blocks"], client, dry_run)
            ids["views"].update(view_ids)
        elif page_name == "Trends":
            view_ids = create_trends_views(page_id, {}, client, dry_run)
            ids["views"].update(view_ids)
        elif page_name == "Flags & Alerts":
            view_ids = create_flags_views(page_id, client, dry_run)
            ids["views"].update(view_ids)
        elif page_name == "Full Data Table":
            view_ids = create_full_table_view(page_id, client, dry_run)
            ids["views"].update(view_ids)
    except Exception as exc:
        logger.warning(
            "View creation skipped for '%s' (non-fatal): %s", page_name, exc
        )

    return ids


def deploy_all(
    dry_run: bool = False,
    single_page: str | None = None,
) -> dict[str, Any]:
    """
    Deploy all (or one) dashboard pages and save IDs to config.

    Returns the full dashboard_ids mapping.
    """
    client = None if dry_run else httpx.Client(timeout=30.0)

    try:
        dashboard_ids: dict[str, Any] = {}

        pages_to_deploy = [single_page] if single_page else list(PAGE_SPECS.keys())

        for page_name in pages_to_deploy:
            ids = deploy_page(page_name, client, dry_run)
            if ids:
                dashboard_ids[page_name] = ids
            else:
                logger.error("Failed to deploy page: %s", page_name)

        # Save IDs to config file
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # If deploying a single page, merge with existing config
        if single_page and CONFIG_FILE.exists():
            existing = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            existing.update(dashboard_ids)
            dashboard_ids = existing

        CONFIG_FILE.write_text(
            json.dumps(dashboard_ids, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Dashboard IDs saved to %s", CONFIG_FILE)

        return dashboard_ids

    finally:
        if client:
            client.close()


# ============================================================
# CLI entry point
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy Cornflower Health dashboard pages to Notion"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be created without making API calls",
    )
    parser.add_argument(
        "--page",
        type=str,
        default=None,
        help="Deploy only a specific page (e.g., 'Daily Dashboard', 'Trends')",
    )
    args = parser.parse_args()

    log_file = _setup_logging()
    logger.info(
        "Dashboard deploy started — dry_run: %s, page: %s",
        args.dry_run, args.page or "all",
    )
    logger.info("Log file: %s", log_file)

    if not args.dry_run and not NOTION_TOKEN:
        logger.error("NOTION_TOKEN not set — cannot deploy. Use --dry-run to test.")
        sys.exit(1)

    result = deploy_all(dry_run=args.dry_run, single_page=args.page)

    page_count = len(result)
    view_count = sum(len(v.get("views", {})) for v in result.values())
    block_count = sum(len(v.get("blocks", {})) for v in result.values())

    logger.info(
        "Deploy complete — %d pages, %d block groups, %d views created",
        page_count, block_count, view_count,
    )


if __name__ == "__main__":
    main()
