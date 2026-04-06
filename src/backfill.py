"""
Task 2.2 — Historical Backfill Script
Cornflower Health project — src/backfill.py

CLI script that reads HAE historical JSON export files and writes rows
to the existing Notion database, one row per calendar day.

Usage:
    python src/backfill.py [--dry-run] path/to/export.json

Reuses:
    - src/normalize.py  (normalize function)
    - src/notion_writer.py (write function)
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is importable when run as `python src/backfill.py`
sys.path.insert(0, str(Path(__file__).parent))

from normalize import normalize
from notion_writer import write as notion_write

logger = logging.getLogger("cornflower.backfill")


def _setup_logging() -> str:
    """Configure logging to file and stderr. Returns the log file path."""
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = logs_dir / f"backfill_{timestamp}.log"

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


def _extract_metrics_list(payload: Any) -> list[dict] | None:
    """
    Extract the metrics list from a payload, handling both known formats:
      - dict:  {"data": {"metrics": [...]}}
      - list:  [{"data": {"metrics": [...]}}]
    Returns None if the structure is unrecognized.
    """
    try:
        if isinstance(payload, list):
            return payload[0]["data"]["metrics"]
        elif isinstance(payload, dict):
            return payload["data"]["metrics"]
    except (IndexError, KeyError, TypeError):
        pass
    return None


def _collect_dates(metrics_list: list[dict]) -> list[str]:
    """
    Scan all metric data entries and collect unique YYYY-MM-DD dates.
    Returns sorted list of date strings.
    """
    dates: set[str] = set()
    for metric in metrics_list:
        for entry in metric.get("data", []):
            raw_date = entry.get("date", "")
            day = raw_date.split(" ")[0]  # YYYY-MM-DD prefix
            if day:
                dates.add(day)
    return sorted(dates)


def _build_day_payload(metrics_list: list[dict], target_date: str, wrapper: str) -> Any:
    """
    Build a single-day payload in the format normalize() expects.

    For each metric, filter its data entries to only those matching target_date.
    Re-wrap in the original container format (list or dict).
    """
    day_metrics = []
    for metric in metrics_list:
        day_entries = [
            entry for entry in metric.get("data", [])
            if entry.get("date", "").startswith(target_date)
        ]
        if day_entries:
            day_metrics.append({
                "name": metric.get("name"),
                "units": metric.get("units", ""),
                "data": day_entries,
            })

    inner = {"data": {"metrics": day_metrics}}
    if wrapper == "list":
        return [inner]
    return inner


def run_backfill(file_path: str, dry_run: bool = False) -> dict[str, int]:
    """
    Main backfill logic. Reads a JSON export, groups by date, normalizes,
    and writes to Notion.

    Returns summary dict: {"written": N, "skipped": N, "errors": N}
    """
    path = Path(file_path)
    if not path.exists():
        logger.error("File not found: %s", file_path)
        return {"written": 0, "skipped": 0, "errors": 1}

    # --- Load JSON ---
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read/parse %s: %s", file_path, exc)
        return {"written": 0, "skipped": 0, "errors": 1}

    # --- Determine wrapper format ---
    wrapper = "list" if isinstance(raw, list) else "dict"

    # --- Extract metrics list ---
    metrics_list = _extract_metrics_list(raw)
    if metrics_list is None:
        logger.error("Unrecognized payload structure in %s — expected dict or array wrapper with data.metrics[]", file_path)
        return {"written": 0, "skipped": 0, "errors": 1}

    # --- Collect all dates in the export ---
    dates = _collect_dates(metrics_list)
    if not dates:
        logger.warning("No dates found in %s", file_path)
        return {"written": 0, "skipped": 0, "errors": 0}

    logger.info("Found %d unique dates in export: %s … %s", len(dates), dates[0], dates[-1])

    # --- Process each date ---
    summary = {"written": 0, "skipped": 0, "errors": 0}

    for i, date_str in enumerate(dates):
        try:
            # Build per-day payload and normalize
            day_payload = _build_day_payload(metrics_list, date_str, wrapper)
            record = normalize(day_payload, target_date=date_str)

            if not record:
                logger.warning("  %s — normalize returned empty, skipping", date_str)
                summary["errors"] += 1
                continue

            # Override source_tags for backfill
            record["source_tags"] = ["backfill_json"]

            if dry_run:
                logger.info("  %s — DRY RUN: would write record (%d fields with values)",
                            date_str,
                            sum(1 for v in record.values() if v is not None))
                summary["written"] += 1
                continue

            # Write to Notion (notion_writer handles dedup internally)
            result = notion_write(record)
            status = result.get("status", "error")
            message = result.get("message", "")

            if status == "written":
                logger.info("  %s — written: %s", date_str, message)
                summary["written"] += 1
            elif status == "skipped":
                logger.info("  %s — skipped (duplicate): %s", date_str, message)
                summary["skipped"] += 1
            else:
                logger.error("  %s — error: %s", date_str, message)
                summary["errors"] += 1

            # Rate limit between writes (not after the last one)
            if i < len(dates) - 1:
                time.sleep(0.35)

        except Exception as exc:
            logger.error("  %s — unhandled error: %s", date_str, exc, exc_info=True)
            summary["errors"] += 1
            continue

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill Notion database from HAE historical JSON export"
    )
    parser.add_argument("file", help="Path to HAE JSON export file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without calling Notion API",
    )
    args = parser.parse_args()

    log_file = _setup_logging()
    logger.info("Backfill started — file: %s, dry_run: %s", args.file, args.dry_run)
    logger.info("Log file: %s", log_file)

    summary = run_backfill(args.file, dry_run=args.dry_run)

    logger.info(
        "Backfill complete — written: %d, skipped: %d, errors: %d",
        summary["written"],
        summary["skipped"],
        summary["errors"],
    )


if __name__ == "__main__":
    main()
