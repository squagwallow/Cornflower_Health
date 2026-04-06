"""
Task 1.2 — HAE Payload Normalization Layer
Cornflower Health project — src/normalize.py

Accepts a raw HAE webhook payload (list) and returns a normalized dict
with Notion field names as keys and Python-typed values ready for notion_writer.

All field names match docs/schema-plan.md exactly.
All conversions verified against samples/hae_sample_2026-04-05.json.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("cornflower.normalize")

# Timestamp format used in HAE sleep_analysis sub-fields
_DT_FMT = "%Y-%m-%d %H:%M:%S %z"


def _find_record(metric_data: list[dict], target_date: str) -> dict | None:
    """
    Return the first record in metric_data whose 'date' string starts with target_date (YYYY-MM-DD).
    Returns None if not found.
    """
    for record in metric_data:
        if record.get("date", "").startswith(target_date):
            return record
    return None


def _safe_qty(record: dict | None) -> float | None:
    """Extract 'qty' from a record dict, or None if missing/invalid."""
    if record is None:
        return None
    val = record.get("qty")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def normalize(payload: list[dict], target_date: str | None = None) -> dict[str, Any]:
    """
    Normalize a raw HAE webhook payload into a Notion-ready record dict.

    Args:
        payload: Raw HAE payload (top-level list, as received from webhook).
        target_date: YYYY-MM-DD string. If None, derived from sleep_analysis record date.

    Returns:
        Dict with Notion field names as keys. Missing fields are set to None.
        Fields not auto-populated by the backend are omitted (not included as None).
    """

    # --- Build metric lookup dict: name → data list ---
    try:
        metrics_list = payload[0]["data"]["metrics"]
    except (IndexError, KeyError, TypeError) as exc:
        logger.error("Cannot parse payload structure: %s", exc)
        return {}

    metrics: dict[str, list[dict]] = {}
    for m in metrics_list:
        name = m.get("name")
        data = m.get("data", [])
        if name:
            metrics[name] = data

    # --- Determine target_date from sleep_analysis if not provided ---
    sleep_data = metrics.get("sleep_analysis", [])
    if not target_date and sleep_data:
        raw_date = sleep_data[-1].get("date", "")
        target_date = raw_date.split(" ")[0]  # YYYY-MM-DD prefix

    if not target_date:
        logger.warning("Could not determine target_date — payload may be empty")
        return {}

    logger.info("Normalizing record for date: %s", target_date)

    # ----------------------------------------------------------------
    # SCALAR METRICS (qty field, no unit conversion)
    # ----------------------------------------------------------------

    hrv_rec = _find_record(metrics.get("heart_rate_variability", []), target_date)
    hrv_sdnn_ms = _safe_qty(hrv_rec)  # ms, no conversion

    rhr_rec = _find_record(metrics.get("resting_heart_rate", []), target_date)
    rhr_bpm = _safe_qty(rhr_rec)  # count/min = bpm, no conversion

    resp_rec = _find_record(metrics.get("respiratory_rate", []), target_date)
    resp_rate_brpm = _safe_qty(resp_rec)  # count/min, no conversion

    spo2_rec = _find_record(metrics.get("blood_oxygen_saturation", []), target_date)
    spo2_avg_pct = _safe_qty(spo2_rec)  # already in %, DO NOT multiply by 100

    wrist_rec = _find_record(metrics.get("apple_sleeping_wrist_temperature", []), target_date)
    wrist_temp_abs = _safe_qty(wrist_rec)  # degF, DO NOT convert to Celsius

    # ----------------------------------------------------------------
    # HEART RATE — capital Avg / Min / Max keys (confirmed from payload)
    # ----------------------------------------------------------------

    hr_rec = _find_record(metrics.get("heart_rate", []), target_date)
    hr_day_avg_bpm: float | None = None
    hr_day_min_bpm: int | None = None
    hr_day_max_bpm: int | None = None

    if hr_rec is not None:
        try:
            avg = hr_rec.get("Avg")
            hr_day_avg_bpm = float(avg) if avg is not None else None
        except (TypeError, ValueError):
            pass
        try:
            mn = hr_rec.get("Min")
            hr_day_min_bpm = round(float(mn)) if mn is not None else None
        except (TypeError, ValueError):
            pass
        try:
            mx = hr_rec.get("Max")
            hr_day_max_bpm = round(float(mx)) if mx is not None else None
        except (TypeError, ValueError):
            pass

    # ----------------------------------------------------------------
    # SLEEP ANALYSIS — all values are in HOURS, convert to minutes
    # ----------------------------------------------------------------

    sleep_rec = _find_record(sleep_data, target_date)

    sleep_time_asleep_min: int | None = None
    sleep_deep_min: int | None = None
    sleep_rem_min: int | None = None
    sleep_core_min: int | None = None
    sleep_awake_min: int | None = None
    sleep_time_in_bed_min: int | None = None
    sleep_bedtime: str | None = None
    sleep_waketime: str | None = None
    sleep_waketime_num: int | None = None

    if sleep_rec is not None:

        def _hours_to_min(key: str) -> int | None:
            val = sleep_rec.get(key)
            if val is None:
                return None
            try:
                return round(float(val) * 60)
            except (TypeError, ValueError):
                return None

        sleep_time_asleep_min = _hours_to_min("totalSleep")
        sleep_deep_min = _hours_to_min("deep")
        sleep_rem_min = _hours_to_min("rem")
        sleep_core_min = _hours_to_min("core")
        sleep_awake_min = _hours_to_min("awake")

        # sleep_time_in_bed_min: derived from inBedStart/inBedEnd timestamps
        # (inBed key is always 0 — do NOT use it)
        in_bed_start_str = sleep_rec.get("inBedStart")
        in_bed_end_str = sleep_rec.get("inBedEnd")
        if in_bed_start_str and in_bed_end_str:
            try:
                in_bed_start = datetime.strptime(in_bed_start_str, _DT_FMT)
                in_bed_end = datetime.strptime(in_bed_end_str, _DT_FMT)
                sleep_time_in_bed_min = round(
                    (in_bed_end - in_bed_start).total_seconds() / 60
                )
            except ValueError as exc:
                logger.warning("Could not parse inBed timestamps: %s", exc)

        # sleep_bedtime / sleep_waketime: store as text strings as-is
        sleep_bedtime = sleep_rec.get("sleepStart")
        sleep_waketime = sleep_rec.get("sleepEnd")

        # sleep_waketime_num: local hour*60 + minute from sleepEnd
        if sleep_waketime:
            try:
                wake_dt = datetime.strptime(sleep_waketime, _DT_FMT)
                sleep_waketime_num = wake_dt.hour * 60 + wake_dt.minute
            except ValueError as exc:
                logger.warning("Could not parse sleepEnd for waketime_num: %s", exc)

    # ----------------------------------------------------------------
    # DERIVED / FIXED FIELDS
    # ----------------------------------------------------------------

    date = target_date
    source_tags = ["Apple Health"]

    # ----------------------------------------------------------------
    # ASSEMBLE NORMALIZED RECORD
    # Fields set to None are included so notion_writer can skip them.
    # Fields not populated by backend at all are not included.
    # ----------------------------------------------------------------

    record: dict[str, Any] = {
        # Identity
        "date": date,
        "source_tags": source_tags,
        # Cardio
        "hrv_sdnn_ms": hrv_sdnn_ms,
        "rhr_bpm": rhr_bpm,
        "resp_rate_brpm": resp_rate_brpm,
        "spo2_avg_pct": spo2_avg_pct,
        "wrist_temp_abs": wrist_temp_abs,
        # Heart rate
        "hr_day_avg_bpm": hr_day_avg_bpm,
        "hr_day_min_bpm": hr_day_min_bpm,
        "hr_day_max_bpm": hr_day_max_bpm,
        # Sleep
        "sleep_time_in_bed_min": sleep_time_in_bed_min,
        "sleep_time_asleep_min": sleep_time_asleep_min,
        "sleep_deep_min": sleep_deep_min,
        "sleep_rem_min": sleep_rem_min,
        "sleep_core_min": sleep_core_min,
        "sleep_awake_min": sleep_awake_min,
        "sleep_bedtime": sleep_bedtime,
        "sleep_waketime": sleep_waketime,
        "sleep_waketime_num": sleep_waketime_num,
        # Manual-only fields — NOT populated by backend, not included:
        # hr_sleep_avg_bpm, hr_sleep_min_bpm, spo2_min_pct,
        # sleep_awakenings_count, sleep_longest_wake_min,
        # hrv_baseline_60d_ms, rhr_baseline_60d_bpm, hrv_7d_avg_ms,
        # rhr_7d_avg_bpm, deep_sleep_7d_avg_min, hr_dip_7d_avg_pct,
        # recovery_score, all booster_*/workout_*/subjective fields
    }

    logger.info("Normalized record for %s: %s", date, {k: v for k, v in record.items() if v is not None})
    return record
