"""
Task 1.3 — Notion Write Layer
Cornflower Health project — src/notion_writer.py

Accepts a normalized record (output of normalize.py) and writes it to the
existing Notion database. Handles idempotency, type mapping, error logging,
and 429 retry.

Reference:
  - docs/schema-plan.md      (field names and Notion property types)
  - docs/notion-api-notes.md (API patterns, database ID, formula limitations)
"""

import json
import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cornflower.notion_writer")

# --- Config ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv(
    "NOTION_DATABASE_ID", "339d7cd8-531f-819f-85b2-c769696ea27c"
)
NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"

# ----------------------------------------------------------------
# Fields the backend writes — keyed by Notion property name.
# Value is the Notion property type string used in the write payload.
#
# Formula fields are NOT listed here — they auto-compute in Notion.
# Manual-only fields are NOT listed here — the backend never writes them.
# ----------------------------------------------------------------

# Number fields written by the backend
_NUMBER_FIELDS = {
    "hrv_sdnn_ms",
    "rhr_bpm",
    "resp_rate_brpm",
    "spo2_avg_pct",
    "wrist_temp_abs",
    "hr_day_avg_bpm",
    "hr_day_min_bpm",
    "hr_day_max_bpm",
    "sleep_time_in_bed_min",
    "sleep_time_asleep_min",
    "sleep_deep_min",
    "sleep_rem_min",
    "sleep_core_min",
    "sleep_awake_min",
    "sleep_waketime_num",
}

# Rich text fields written by the backend
_RICH_TEXT_FIELDS = {
    "sleep_bedtime",
    "sleep_waketime",
}

# Fields the backend MUST NOT write (formula, manual-only, rolling baseline)
_SKIP_FIELDS = {
    # Formula fields (auto-computed in Notion)
    "sleep_efficiency_pct", "hr_dip_pct", "hr_dip_category", "day_of_week",
    "flag_deep_sleep_low", "flag_deep_gate_50", "flag_rhr_elevated",
    "flag_hrv_very_low", "flag_recovery_red_gate", "flag_resp_rate_high",
    "flag_spo2_low", "flag_sleep_fragmented", "flag_early_wake",
    # Manual-only fields
    "energy_1_5", "day_quality_1_5", "meds_notes", "morning_heaviness",
    "afternoon_crash", "stress_context", "fatigue_level", "notes",
    "booster_status", "booster_decision", "workout_rest_day", "workout_type",
    "workout_total_min", "workout_exertion_felt", "workout_z2_min",
    "workout_z3_min", "workout_z4_min", "workout_summary",
    # Manual-only metrics not in HAE payload
    "hr_sleep_avg_bpm", "hr_sleep_min_bpm", "spo2_min_pct",
    "sleep_awakenings_count", "sleep_longest_wake_min",
    # Rolling baselines (Phase 3+)
    "hrv_7d_avg_ms", "rhr_7d_avg_bpm", "deep_sleep_7d_avg_min",
    "hr_dip_7d_avg_pct", "hrv_baseline_60d_ms", "rhr_baseline_60d_bpm",
    "recovery_score",
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _build_properties(record: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a normalized record dict into a Notion properties payload.
    Skips None values, formula fields, and manual-only fields.
    """
    props: dict[str, Any] = {}

    date_str = record.get("date")
    if not date_str:
        raise ValueError("record must contain a 'date' field (YYYY-MM-DD)")

    # Title — Entry field (Notion requires a title property)
    props["Entry"] = {"title": [{"text": {"content": date_str}}]}

    # Date property
    props["date"] = {"date": {"start": date_str}}

    # source_tags — multi-select
    tags = record.get("source_tags")
    if tags:
        props["source_tags"] = {
            "multi_select": [{"name": t} for t in tags]
        }

    # Number fields
    for field in _NUMBER_FIELDS:
        if field in record and record[field] is not None:
            props[field] = {"number": record[field]}

    # Rich text fields (sleep_bedtime, sleep_waketime stored as text)
    for field in _RICH_TEXT_FIELDS:
        val = record.get(field)
        if val is not None:
            props[field] = {
                "rich_text": [{"text": {"content": str(val)}}]
            }

    return props


def _query_existing(date_str: str, client: httpx.Client) -> str | None:
    """
    Query Notion for an existing page with the given date.
    Returns the page_id string if found, None otherwise.
    """
    url = f"{NOTION_BASE}/databases/{NOTION_DATABASE_ID}/query"
    payload = {
        "filter": {
            "property": "date",
            "date": {"equals": date_str}
        }
    }
    try:
        resp = client.post(url, headers=_headers(), json=payload)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Failed to query Notion for date %s: %s %s",
            date_str, exc.response.status_code, exc.response.text[:200]
        )
    except Exception as exc:
        logger.error("Unexpected error querying Notion: %s", exc)
    return None


def _post_page(properties: dict[str, Any], client: httpx.Client) -> dict | None:
    """
    POST a new page to the Notion database. Retries once on 429.
    Returns the response JSON on success, None on failure.
    """
    url = f"{NOTION_BASE}/pages"
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    for attempt in range(2):
        try:
            resp = client.post(url, headers=_headers(), json=payload)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Rate limited (429) — retrying after %ds", retry_after)
                time.sleep(retry_after)
                continue

            if resp.status_code == 400:
                logger.error(
                    "Bad request (400) writing to Notion. Properties sent:\n%s\nResponse:\n%s",
                    json.dumps(list(properties.keys())),
                    resp.text[:500],
                )
                return None

            if resp.status_code == 403:
                logger.error(
                    "Forbidden (403) — check that the Notion integration has access to the database. "
                    "Response: %s", resp.text[:200]
                )
                return None

            resp.raise_for_status()
            return resp.json()

        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error writing page (attempt %d): %s %s",
                attempt + 1, exc.response.status_code, exc.response.text[:200]
            )
            return None
        except Exception as exc:
            logger.error("Unexpected error writing page (attempt %d): %s", attempt + 1, exc)
            return None

    logger.error("Gave up after 2 attempts (rate limit not resolved)")
    return None


def write(record: dict[str, Any]) -> dict[str, Any]:
    """
    Write a normalized record to the Notion database.

    Args:
        record: Output of normalize.normalize() — dict with Notion field names.

    Returns:
        dict with keys:
            status: "written" | "skipped" | "error"
            date:   the date string from the record
            page_id: Notion page ID if written (else None)
            message: human-readable outcome string
    """
    date_str = record.get("date")
    if not date_str:
        return {"status": "error", "date": None, "page_id": None, "message": "Record has no date field"}

    with httpx.Client(timeout=30.0) as client:

        # --- Idempotency: check for existing row ---
        existing_id = _query_existing(date_str, client)
        if existing_id:
            msg = f"Duplicate skipped — page already exists for {date_str} (id: {existing_id})"
            logger.info(msg)
            return {
                "status": "skipped",
                "date": date_str,
                "page_id": existing_id,
                "message": msg,
            }

        # --- Build properties payload ---
        try:
            properties = _build_properties(record)
        except ValueError as exc:
            msg = f"Failed to build properties for {date_str}: {exc}"
            logger.error(msg)
            return {"status": "error", "date": date_str, "page_id": None, "message": msg}

        # --- Write to Notion ---
        result = _post_page(properties, client)
        if result is None:
            msg = f"Failed to write page for {date_str} — see logs above for details"
            return {"status": "error", "date": date_str, "page_id": None, "message": msg}

        page_id = result.get("id", "unknown")
        msg = f"Written — date: {date_str}, page_id: {page_id}"
        logger.info(msg)
        return {
            "status": "written",
            "date": date_str,
            "page_id": page_id,
            "message": msg,
        }
