"""
Tests for src/normalize.py
Verified against samples/hae_sample_2026-04-05.json (real payload).

Expected values for April 5, 2026 record (from coding-session-prompts.md):
  hrv_sdnn_ms       = 44.059  (actual: 44.05909693426334 — round to 3 dp)
  rhr_bpm           = 67.5
  hr_day_avg_bpm    = 87.049  (actual: 87.04912334858682)
  sleep_deep_min    = round(0.477 * 60) = 29
  sleep_time_asleep_min = round(6.537 * 60) = 392
  wrist_temp_abs    = 99.426  (actual: 99.4257736206054)
  spo2_avg_pct      = 92.6
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from normalize import normalize

SAMPLE_PATH = Path(__file__).parent.parent / "samples" / "hae_sample_2026-04-05.json"
TARGET_DATE = "2026-04-05"


@pytest.fixture(scope="module")
def payload():
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def record(payload):
    return normalize(payload, target_date=TARGET_DATE)


# ----------------------------------------------------------------
# Basic structure
# ----------------------------------------------------------------

def test_record_not_empty(record):
    assert record, "normalize() returned an empty dict"


def test_date_field(record):
    assert record["date"] == TARGET_DATE


def test_source_tags(record):
    assert record["source_tags"] == ["Apple Health"]


# ----------------------------------------------------------------
# Scalar cardio metrics
# ----------------------------------------------------------------

def test_hrv_sdnn_ms(record):
    assert record["hrv_sdnn_ms"] is not None
    assert round(record["hrv_sdnn_ms"], 3) == pytest.approx(44.059, abs=0.001)


def test_rhr_bpm(record):
    assert record["rhr_bpm"] == pytest.approx(67.5, abs=0.01)


def test_resp_rate_brpm(record):
    assert record["resp_rate_brpm"] is not None
    assert record["resp_rate_brpm"] == pytest.approx(17.523, abs=0.01)


def test_spo2_avg_pct(record):
    # Must NOT be multiplied by 100 — should be ~92.6
    assert record["spo2_avg_pct"] == pytest.approx(92.6, abs=0.01)
    assert record["spo2_avg_pct"] < 100, "spo2_avg_pct looks like it was multiplied by 100"


def test_wrist_temp_abs(record):
    assert record["wrist_temp_abs"] == pytest.approx(99.426, abs=0.01)


# ----------------------------------------------------------------
# Heart rate (capital Avg/Min/Max keys)
# ----------------------------------------------------------------

def test_hr_day_avg_bpm(record):
    assert record["hr_day_avg_bpm"] == pytest.approx(87.049, abs=0.01)


def test_hr_day_min_bpm(record):
    # Raw value: 53 — already integer in payload
    assert record["hr_day_min_bpm"] == 53


def test_hr_day_max_bpm(record):
    assert record["hr_day_max_bpm"] == 148


# ----------------------------------------------------------------
# Sleep analysis (hours → minutes conversion)
# ----------------------------------------------------------------

def test_sleep_time_asleep_min(record):
    # 6.537360689441363 * 60 = 392.24 → round to 392
    assert record["sleep_time_asleep_min"] == 392


def test_sleep_deep_min(record):
    # 0.47712289373079936 * 60 = 28.63 → round to 29
    assert record["sleep_deep_min"] == 29


def test_sleep_rem_min(record):
    # 1.3142187190386985 * 60 = 78.85 → 79
    assert record["sleep_rem_min"] == 79


def test_sleep_core_min(record):
    # 4.746019076671866 * 60 = 284.76 → 285
    assert record["sleep_core_min"] == 285


def test_sleep_awake_min(record):
    # 0.1254988591538535 * 60 = 7.53 → 8
    assert record["sleep_awake_min"] == 8


def test_sleep_time_in_bed_min(record):
    # inBedStart: 2026-04-04 21:51:21 -0600
    # inBedEnd:   2026-04-05 04:31:08 -0600
    # Diff = 6h 39m 47s = 399.78 min → round to 400
    assert record["sleep_time_in_bed_min"] == 400


def test_sleep_bedtime(record):
    assert record["sleep_bedtime"] == "2026-04-04 21:51:21 -0600"


def test_sleep_waketime(record):
    assert record["sleep_waketime"] == "2026-04-05 04:31:08 -0600"


def test_sleep_waketime_num(record):
    # 04:31 local = 4*60 + 31 = 271
    assert record["sleep_waketime_num"] == 271


# ----------------------------------------------------------------
# Manual-only fields must NOT appear in record
# ----------------------------------------------------------------

MANUAL_FIELDS = [
    "hr_sleep_avg_bpm",
    "hr_sleep_min_bpm",
    "spo2_min_pct",
    "sleep_awakenings_count",
    "sleep_longest_wake_min",
    "hrv_baseline_60d_ms",
    "rhr_baseline_60d_bpm",
    "recovery_score",
]


@pytest.mark.parametrize("field", MANUAL_FIELDS)
def test_manual_field_not_populated(record, field):
    assert field not in record, f"Backend should not populate manual field: {field}"


# ----------------------------------------------------------------
# Missing-field resilience: date with no data should return None values
# ----------------------------------------------------------------

def test_missing_date_returns_none_fields(payload):
    rec = normalize(payload, target_date="2020-01-01")
    # Should still return a record structure (with date) but all metrics None
    assert rec["date"] == "2020-01-01"
    assert rec["hrv_sdnn_ms"] is None
    assert rec["rhr_bpm"] is None
    assert rec["sleep_deep_min"] is None
