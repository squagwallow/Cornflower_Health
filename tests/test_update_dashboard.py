"""
Tests for src/update_dashboard.py and src/recovery_score.py

Covers:
  - Recovery score computation (HRV component, RHR component, modifiers, hard gates)
  - Booster decision tree
  - Dashboard formatting (callouts, metrics, sleep, flags, booster, averages)
  - Notion API interactions (mocked)
  - Config loading
  - Rolling averages
  - Dry-run mode
  - Edge cases (missing data, boundary values)

Does NOT call real Notion API — all API calls are mocked.
"""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

import httpx
import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recovery_score import (
    compute_hrv_component,
    compute_rhr_component,
    compute_modifiers,
    compute_hard_gates,
    score_to_zone,
    apply_hard_gates,
    compute_recovery,
    compute_booster_decision,
    _clamp,
    ZONE_COLORS,
    ZONE_EMOJIS,
)

from update_dashboard import (
    load_dashboard_config,
    get_daily_block_ids,
    _extract_row,
    format_recovery_callout,
    format_breakdown_callout,
    format_key_metrics,
    format_sleep,
    format_flags,
    format_flags_toggle_text,
    format_booster,
    format_exertion_paragraph,
    compute_rolling_averages,
    format_rolling_averages,
    run_update,
    _compute_baseline,
    _trend_arrow,
    _metric_status,
    _fmt_minutes,
    patch_block,
    replace_toggle_children,
    CONFIG_FILE,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def healthy_row():
    """A row representing a healthy/recovered day — should score GREEN."""
    return {
        "date": "2026-04-06",
        "hrv_sdnn_ms": 58.1,
        "rhr_bpm": 63.0,
        "hrv_baseline_60d_ms": 53.2,
        "rhr_baseline_60d_bpm": 64.8,
        "sleep_deep_min": 52.0,
        "sleep_rem_min": 82.0,
        "sleep_core_min": 188.0,
        "sleep_awake_min": 18.0,
        "sleep_time_asleep_min": 432.0,
        "sleep_time_in_bed_min": 472.0,
        "sleep_efficiency_pct": 91.5,
        "sleep_bedtime": "11:15 PM",
        "sleep_waketime": "6:27 AM",
        "sleep_waketime_num": 387,
        "spo2_avg_pct": 95.0,
        "spo2_min_pct": 91.0,
        "resp_rate_brpm": 14.2,
        "wrist_temp_abs": 99.1,
        "hr_day_avg_bpm": 78.0,
        "hr_dip_pct": 14.2,
        "hr_dip_category": "Borderline dipper",
        "sleep_awakenings_count": 2,
        "stress_context": None,
        "flag_deep_sleep_low": False,
        "flag_deep_gate_50": False,
        "flag_hrv_very_low": False,
        "flag_rhr_elevated": False,
        "flag_resp_rate_high": False,
        "flag_spo2_low": False,
        "flag_sleep_fragmented": False,
        "flag_early_wake": False,
        "flag_recovery_red_gate": False,
        "workout_type": None,
        "workout_summary": None,
        "workout_rest_day": True,
    }


@pytest.fixture
def stressed_row():
    """A row representing a stressed/under-recovered day — should score low."""
    return {
        "date": "2026-04-06",
        "hrv_sdnn_ms": 38.0,
        "rhr_bpm": 70.0,
        "hrv_baseline_60d_ms": 53.2,
        "rhr_baseline_60d_bpm": 64.8,
        "sleep_deep_min": 28.0,
        "sleep_rem_min": 45.0,
        "sleep_core_min": 120.0,
        "sleep_awake_min": 35.0,
        "sleep_time_asleep_min": 320.0,
        "sleep_time_in_bed_min": 380.0,
        "sleep_efficiency_pct": 84.0,
        "sleep_bedtime": "12:30 AM",
        "sleep_waketime": "4:45 AM",
        "sleep_waketime_num": 285,
        "spo2_avg_pct": 91.0,
        "spo2_min_pct": 87.0,
        "resp_rate_brpm": 19.5,
        "wrist_temp_abs": 99.8,
        "hr_day_avg_bpm": 85.0,
        "hr_dip_pct": 8.5,
        "hr_dip_category": "Non-dipper",
        "sleep_awakenings_count": 5,
        "stress_context": "High",
        "flag_deep_sleep_low": True,
        "flag_deep_gate_50": True,
        "flag_hrv_very_low": True,
        "flag_rhr_elevated": True,
        "flag_resp_rate_high": True,
        "flag_spo2_low": True,
        "flag_sleep_fragmented": True,
        "flag_early_wake": True,
        "flag_recovery_red_gate": True,
        "workout_type": None,
        "workout_summary": None,
        "workout_rest_day": None,
    }


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample dashboard_ids.json config."""
    config = {
        "Daily Dashboard": {
            "page_id": "test-page-id",
            "blocks": {
                "callout_0": "block-recovery-callout",
                "callout_1": "block-breakdown-callout",
                "heading_2_2": "block-exertion-heading",
                "paragraph_4": "block-exertion-paragraph",
                "heading_2_6": "block-metrics-heading",
                "paragraph_8": "block-metric-hrv",
                "paragraph_9": "block-metric-rhr",
                "paragraph_10": "block-metric-spo2",
                "paragraph_11": "block-metric-resp",
                "paragraph_12": "block-metric-temp",
                "paragraph_13": "block-metric-hr-dip",
                "heading_2_14": "block-sleep-heading",
                "paragraph_16": "block-sleep-total",
                "paragraph_17": "block-sleep-deep-rem",
                "paragraph_18": "block-sleep-core-awake",
                "paragraph_19": "block-sleep-bed-wake",
                "paragraph_20": "block-sleep-in-bed",
                "toggle_21": "block-flags-toggle",
                "toggle_22": "block-booster-toggle",
                "toggle_23": "block-averages-toggle",
            },
            "views": {},
        }
    }
    config_file = tmp_path / "config" / "dashboard_ids.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(config, indent=2))
    return config


@pytest.fixture
def sample_rows():
    """Build a list of 10 rows for testing rolling averages."""
    from datetime import timedelta
    rows = []
    base_date = datetime(2026, 4, 1)
    for i in range(10):
        d = base_date - timedelta(days=9 - i)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "hrv_sdnn_ms": 50.0 + i,
            "rhr_bpm": 65.0 - i * 0.5,
            "sleep_deep_min": 45.0 + i,
            "hr_dip_pct": 12.0 + i * 0.3,
        })
    return rows


# ============================================================
# Recovery Score — HRV Component
# ============================================================

class TestHRVComponent:
    def test_at_baseline(self):
        """HRV at baseline should give 60."""
        assert compute_hrv_component(53.2, 53.2) == 60.0

    def test_above_baseline_capped(self):
        """HRV above baseline should still cap at 60."""
        result = compute_hrv_component(70.0, 53.2)
        assert result == 60.0

    def test_below_baseline(self):
        """HRV below baseline should proportionally reduce score."""
        result = compute_hrv_component(26.6, 53.2)
        assert abs(result - 30.0) < 0.1

    def test_zero_hrv(self):
        assert compute_hrv_component(0.0, 53.2) == 0.0

    def test_zero_baseline(self):
        assert compute_hrv_component(50.0, 0.0) == 0.0

    def test_half_baseline(self):
        result = compute_hrv_component(26.6, 53.2)
        assert abs(result - 30.0) < 0.1


# ============================================================
# Recovery Score — RHR Component
# ============================================================

class TestRHRComponent:
    def test_at_baseline(self):
        """RHR at baseline should give 40."""
        result = compute_rhr_component(64.8, 64.8)
        assert abs(result - 40.0) < 0.1

    def test_below_baseline_is_better(self):
        """Lower RHR → higher score (but capped at 40)."""
        result = compute_rhr_component(60.0, 64.8)
        assert result == 40.0  # Capped at max

    def test_above_baseline_is_worse(self):
        """Higher RHR → lower score."""
        result = compute_rhr_component(70.0, 64.8)
        assert result < 40.0

    def test_capped_at_40(self):
        """Even very low RHR can't exceed 40."""
        result = compute_rhr_component(40.0, 64.8)
        assert result == 40.0

    def test_capped_at_0(self):
        """Very high RHR floors at 0."""
        result = compute_rhr_component(200.0, 64.8)
        assert result == 0.0

    def test_zero_baseline(self):
        assert compute_rhr_component(60.0, 0.0) == 0.0


# ============================================================
# Recovery Score — Modifiers
# ============================================================

class TestModifiers:
    def test_deep_sleep_excellent(self):
        mods = compute_modifiers({"sleep_deep_min": 85})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == 5

    def test_deep_sleep_good(self):
        mods = compute_modifiers({"sleep_deep_min": 70})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == 3

    def test_deep_sleep_neutral(self):
        mods = compute_modifiers({"sleep_deep_min": 55})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == 0

    def test_deep_sleep_mild_deficit(self):
        mods = compute_modifiers({"sleep_deep_min": 40})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == -5

    def test_deep_sleep_moderate_deficit(self):
        mods = compute_modifiers({"sleep_deep_min": 25})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == -10

    def test_deep_sleep_severe_deficit(self):
        mods = compute_modifiers({"sleep_deep_min": 15})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == -15

    def test_spo2_normal(self):
        mods = compute_modifiers({"spo2_avg_pct": 96})
        spo2_mod = [m for m in mods if m[0] == "SpO2 avg"][0]
        assert spo2_mod[1] == 0

    def test_spo2_borderline(self):
        mods = compute_modifiers({"spo2_avg_pct": 93})
        spo2_mod = [m for m in mods if m[0] == "SpO2 avg"][0]
        assert spo2_mod[1] == -3

    def test_spo2_significant(self):
        mods = compute_modifiers({"spo2_avg_pct": 90})
        spo2_mod = [m for m in mods if m[0] == "SpO2 avg"][0]
        assert spo2_mod[1] == -8

    def test_spo2_min_penalty(self):
        mods = compute_modifiers({"spo2_min_pct": 86})
        spo2_min_mod = [m for m in mods if m[0] == "SpO2 min"]
        assert len(spo2_min_mod) == 1
        assert spo2_min_mod[0][1] == -5

    def test_spo2_min_no_penalty(self):
        mods = compute_modifiers({"spo2_min_pct": 90})
        spo2_min_mod = [m for m in mods if m[0] == "SpO2 min"]
        assert len(spo2_min_mod) == 0

    def test_resp_low_arousal(self):
        mods = compute_modifiers({"resp_rate_brpm": 14.0})
        resp_mod = [m for m in mods if m[0] == "Resp rate"][0]
        assert resp_mod[1] == 2

    def test_resp_normal(self):
        mods = compute_modifiers({"resp_rate_brpm": 16.5})
        resp_mod = [m for m in mods if m[0] == "Resp rate"][0]
        assert resp_mod[1] == 0

    def test_resp_elevated(self):
        mods = compute_modifiers({"resp_rate_brpm": 20.0})
        resp_mod = [m for m in mods if m[0] == "Resp rate"][0]
        assert resp_mod[1] == -5

    def test_fragmented_sleep(self):
        mods = compute_modifiers({"sleep_awakenings_count": 5})
        frag = [m for m in mods if m[0] == "Sleep quality"]
        assert len(frag) == 1
        assert frag[0][1] == -5

    def test_no_fragmented_sleep(self):
        mods = compute_modifiers({"sleep_awakenings_count": 2})
        frag = [m for m in mods if m[0] == "Sleep quality"]
        assert len(frag) == 0

    def test_early_wake(self):
        mods = compute_modifiers({"sleep_waketime_num": 280})
        early = [m for m in mods if m[0] == "Early wake"]
        assert len(early) == 1
        assert early[0][1] == -3

    def test_no_early_wake(self):
        mods = compute_modifiers({"sleep_waketime_num": 400})
        early = [m for m in mods if m[0] == "Early wake"]
        assert len(early) == 0

    def test_stress_high(self):
        mods = compute_modifiers({"stress_context": "High"})
        stress = [m for m in mods if m[0] == "Stress"]
        assert len(stress) == 1
        assert stress[0][1] == -5

    def test_stress_extreme(self):
        mods = compute_modifiers({"stress_context": "Extreme"})
        stress = [m for m in mods if m[0] == "Stress"]
        assert len(stress) == 1
        assert stress[0][1] == -5

    def test_stress_none(self):
        mods = compute_modifiers({"stress_context": None})
        stress = [m for m in mods if m[0] == "Stress"]
        assert len(stress) == 0

    def test_stress_low(self):
        mods = compute_modifiers({"stress_context": "Low"})
        stress = [m for m in mods if m[0] == "Stress"]
        assert len(stress) == 0

    def test_missing_deep_sleep(self):
        mods = compute_modifiers({})
        deep_mod = [m for m in mods if m[0] == "Deep sleep"][0]
        assert deep_mod[1] == 0
        assert "no data" in deep_mod[2]


# ============================================================
# Recovery Score — Hard Gates
# ============================================================

class TestHardGates:
    def test_rhr_above_68(self):
        gates = compute_hard_gates({"rhr_bpm": 70, "sleep_deep_min": 50, "hrv_sdnn_ms": 55})
        gate_names = [g[0] for g in gates]
        assert "RHR > 68" in gate_names

    def test_deep_below_35(self):
        gates = compute_hard_gates({"rhr_bpm": 63, "sleep_deep_min": 30, "hrv_sdnn_ms": 55})
        gate_names = [g[0] for g in gates]
        assert "Deep < 35 min" in gate_names

    def test_force_red(self):
        gates = compute_hard_gates({"rhr_bpm": 63, "sleep_deep_min": 30, "hrv_sdnn_ms": 38})
        gate_names = [g[0] for g in gates]
        assert "HRV < 40 AND Deep < 35" in gate_names

    def test_no_gates(self):
        gates = compute_hard_gates({"rhr_bpm": 63, "sleep_deep_min": 55, "hrv_sdnn_ms": 55})
        assert gates == []

    def test_missing_data_no_gates(self):
        gates = compute_hard_gates({})
        assert gates == []


# ============================================================
# Recovery Score — Zone Mapping
# ============================================================

class TestZoneMapping:
    def test_green(self):
        assert score_to_zone(85) == "GREEN"
        assert score_to_zone(75) == "GREEN"
        assert score_to_zone(100) == "GREEN"

    def test_yellow(self):
        assert score_to_zone(60) == "YELLOW"
        assert score_to_zone(50) == "YELLOW"
        assert score_to_zone(74) == "YELLOW"

    def test_orange(self):
        assert score_to_zone(35) == "ORANGE"
        assert score_to_zone(25) == "ORANGE"
        assert score_to_zone(49) == "ORANGE"

    def test_red(self):
        assert score_to_zone(10) == "RED"
        assert score_to_zone(0) == "RED"
        assert score_to_zone(24) == "RED"


class TestApplyHardGates:
    def test_force_red_overrides_green(self):
        score, zone = apply_hard_gates(85, "GREEN", [("test", "force_red")])
        assert zone == "RED"
        assert score <= 24

    def test_cap_yellow_overrides_green(self):
        score, zone = apply_hard_gates(85, "GREEN", [("test", "cap_yellow")])
        assert zone == "YELLOW"
        assert score <= 74

    def test_cap_yellow_doesnt_affect_yellow(self):
        score, zone = apply_hard_gates(60, "YELLOW", [("test", "cap_yellow")])
        assert zone == "YELLOW"
        assert score == 60

    def test_no_gates(self):
        score, zone = apply_hard_gates(85, "GREEN", [])
        assert zone == "GREEN"
        assert score == 85

    def test_force_red_takes_precedence(self):
        """force_red should override cap_yellow."""
        score, zone = apply_hard_gates(
            85, "GREEN",
            [("gate1", "cap_yellow"), ("gate2", "force_red")],
        )
        assert zone == "RED"


# ============================================================
# Recovery Score — Full Integration
# ============================================================

class TestComputeRecovery:
    def test_healthy_day_is_green(self, healthy_row):
        result = compute_recovery(healthy_row)
        assert result["zone"] == "GREEN"
        assert result["score"] >= 75
        assert result["hrv_component"] is not None
        assert result["rhr_component"] is not None
        assert len(result["modifiers"]) > 0
        assert result["hard_gate_active"] is False

    def test_stressed_day_is_red(self, stressed_row):
        result = compute_recovery(stressed_row)
        assert result["zone"] == "RED"
        assert result["score"] <= 24
        assert result["hard_gate_active"] is True

    def test_missing_hrv_returns_unknown(self):
        result = compute_recovery({
            "rhr_bpm": 63.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
        })
        assert result["zone"] == "UNKNOWN"
        assert result["score"] is None
        assert "hrv_sdnn_ms" in result["missing_fields"]

    def test_missing_baseline_returns_unknown(self):
        result = compute_recovery({
            "hrv_sdnn_ms": 55.0,
            "rhr_bpm": 63.0,
        })
        assert result["zone"] == "UNKNOWN"
        assert result["score"] is None

    def test_score_clamped_at_100(self):
        """Even with big positive modifiers, score can't exceed 100."""
        row = {
            "hrv_sdnn_ms": 80.0,
            "rhr_bpm": 50.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
            "sleep_deep_min": 90.0,
            "resp_rate_brpm": 12.0,
        }
        result = compute_recovery(row)
        assert result["score"] <= 100

    def test_score_clamped_at_0(self):
        """Even with huge penalties, score can't go below 0."""
        row = {
            "hrv_sdnn_ms": 10.0,
            "rhr_bpm": 100.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
            "sleep_deep_min": 10.0,
            "spo2_avg_pct": 85.0,
            "spo2_min_pct": 80.0,
            "resp_rate_brpm": 22.0,
            "sleep_awakenings_count": 8,
            "sleep_waketime_num": 250,
            "stress_context": "Extreme",
        }
        result = compute_recovery(row)
        assert result["score"] >= 0

    def test_hard_gate_rhr_caps_yellow(self):
        """RHR > 68 should prevent GREEN even with good other metrics."""
        row = {
            "hrv_sdnn_ms": 60.0,
            "rhr_bpm": 69.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
            "sleep_deep_min": 60.0,
        }
        result = compute_recovery(row)
        assert result["zone"] in ("YELLOW", "ORANGE", "RED")

    def test_hard_gate_deep_caps_yellow(self):
        """Deep < 35 should prevent GREEN."""
        row = {
            "hrv_sdnn_ms": 60.0,
            "rhr_bpm": 60.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
            "sleep_deep_min": 30.0,
        }
        result = compute_recovery(row)
        assert result["zone"] != "GREEN"

    def test_hard_gate_force_red(self):
        """HRV < 40 AND deep < 35 forces RED."""
        row = {
            "hrv_sdnn_ms": 38.0,
            "rhr_bpm": 60.0,
            "hrv_baseline_60d_ms": 53.2,
            "rhr_baseline_60d_bpm": 64.8,
            "sleep_deep_min": 30.0,
        }
        result = compute_recovery(row)
        assert result["zone"] == "RED"

    def test_zone_colors_match(self, healthy_row):
        result = compute_recovery(healthy_row)
        assert result["zone_color"] == ZONE_COLORS[result["zone"]]
        assert result["zone_emoji"] == ZONE_EMOJIS[result["zone"]]


# ============================================================
# Booster Decision Tree
# ============================================================

class TestBoosterDecision:
    def test_green_light(self):
        result = compute_booster_decision({
            "hrv_sdnn_ms": 55.0, "rhr_bpm": 63.0, "sleep_deep_min": 55.0,
        })
        assert result["status"] == "Both doses"
        assert result["emoji"] == "🟢"

    def test_skip_hrv_low(self):
        result = compute_booster_decision({
            "hrv_sdnn_ms": 35.0, "rhr_bpm": 63.0, "sleep_deep_min": 55.0,
        })
        assert result["status"] == "Recovery day — skip"
        assert result["emoji"] == "🔴"

    def test_skip_rhr_high(self):
        result = compute_booster_decision({
            "hrv_sdnn_ms": 55.0, "rhr_bpm": 70.0, "sleep_deep_min": 55.0,
        })
        assert result["status"] == "Recovery day — skip"

    def test_skip_deep_low(self):
        result = compute_booster_decision({
            "hrv_sdnn_ms": 55.0, "rhr_bpm": 63.0, "sleep_deep_min": 30.0,
        })
        assert result["status"] == "Recovery day — skip"

    def test_borderline(self):
        result = compute_booster_decision({
            "hrv_sdnn_ms": 44.0, "rhr_bpm": 63.0, "sleep_deep_min": 42.0,
        })
        assert result["status"] == "First only"
        assert result["emoji"] == "🟡"

    def test_insufficient_data(self):
        result = compute_booster_decision({})
        assert result["status"] == "Unknown"


# ============================================================
# Dashboard Formatting
# ============================================================

class TestFormatRecoveryCallout:
    def test_green_callout(self, healthy_row):
        recovery = compute_recovery(healthy_row)
        payload = format_recovery_callout(recovery)
        callout = payload["callout"]
        assert callout["color"] == "green_background"
        assert callout["icon"]["emoji"] == "🟢"
        assert "GREEN" in callout["rich_text"][0]["text"]["content"]

    def test_red_callout(self, stressed_row):
        recovery = compute_recovery(stressed_row)
        payload = format_recovery_callout(recovery)
        callout = payload["callout"]
        assert callout["color"] == "red_background"
        assert callout["icon"]["emoji"] == "🔴"

    def test_unknown_callout(self):
        recovery = compute_recovery({})
        payload = format_recovery_callout(recovery)
        callout = payload["callout"]
        assert "Insufficient data" in callout["rich_text"][0]["text"]["content"]


class TestFormatBreakdownCallout:
    def test_has_components(self, healthy_row):
        recovery = compute_recovery(healthy_row)
        payload = format_breakdown_callout(recovery)
        text = payload["callout"]["rich_text"][0]["text"]["content"]
        assert "HRV component:" in text
        assert "RHR component:" in text
        assert "Base score:" in text
        assert "Final score:" in text
        assert "Hard gates:" in text

    def test_gray_background(self, healthy_row):
        recovery = compute_recovery(healthy_row)
        payload = format_breakdown_callout(recovery)
        assert payload["callout"]["color"] == "gray_background"

    def test_shows_modifiers(self, healthy_row):
        recovery = compute_recovery(healthy_row)
        payload = format_breakdown_callout(recovery)
        text = payload["callout"]["rich_text"][0]["text"]["content"]
        assert "Deep sleep:" in text

    def test_shows_active_gates(self, stressed_row):
        recovery = compute_recovery(stressed_row)
        payload = format_breakdown_callout(recovery)
        text = payload["callout"]["rich_text"][0]["text"]["content"]
        assert "RHR > 68" in text or "Deep < 35" in text or "HRV < 40" in text


class TestFormatKeyMetrics:
    def test_all_six_metrics(self, healthy_row):
        results = format_key_metrics(
            healthy_row,
            {"hrv_sdnn_ms": 55.0, "rhr_bpm": 64.0},
            {"hrv_sdnn_ms": 53.2, "rhr_bpm": 64.8},
        )
        assert len(results) == 6
        names = [r[0] for r in results]
        assert "metric_hrv" in names
        assert "metric_rhr" in names
        assert "metric_spo2" in names
        assert "metric_resp" in names
        assert "metric_temp" in names
        assert "metric_hr_dip" in names

    def test_hrv_line_format(self, healthy_row):
        results = format_key_metrics(
            healthy_row,
            {"hrv_sdnn_ms": 55.0},
            {"hrv_sdnn_ms": 53.2},
        )
        hrv_payload = [r for r in results if r[0] == "metric_hrv"][0][1]
        text = hrv_payload["paragraph"]["rich_text"][0]["text"]["content"]
        assert "58.1" in text
        assert "55.0" in text
        assert "53.2" in text

    def test_missing_values_show_dashes(self):
        results = format_key_metrics({}, {}, {})
        for _, payload in results:
            text = payload["paragraph"]["rich_text"][0]["text"]["content"]
            assert "--" in text


class TestFormatSleep:
    def test_all_five_lines(self, healthy_row):
        results = format_sleep(healthy_row)
        assert len(results) == 5
        names = [r[0] for r in results]
        assert "sleep_total" in names
        assert "sleep_deep_rem" in names
        assert "sleep_core_awake" in names
        assert "sleep_bed_wake" in names
        assert "sleep_in_bed" in names

    def test_total_format(self, healthy_row):
        results = format_sleep(healthy_row)
        total_payload = [r for r in results if r[0] == "sleep_total"][0][1]
        text = total_payload["paragraph"]["rich_text"][0]["text"]["content"]
        assert "7h 12m" in text
        assert "92" in text  # efficiency 91.5 rounds to 92

    def test_deep_check_mark(self, healthy_row):
        results = format_sleep(healthy_row)
        deep_payload = [r for r in results if r[0] == "sleep_deep_rem"][0][1]
        text = deep_payload["paragraph"]["rich_text"][0]["text"]["content"]
        assert "✅" in text  # deep >= 50

    def test_bed_wake_times(self, healthy_row):
        results = format_sleep(healthy_row)
        bw_payload = [r for r in results if r[0] == "sleep_bed_wake"][0][1]
        text = bw_payload["paragraph"]["rich_text"][0]["text"]["content"]
        assert "11:15 PM" in text
        assert "6:27 AM" in text


class TestFormatFlags:
    def test_no_flags(self, healthy_row):
        children = format_flags(healthy_row)
        assert len(children) == 1
        text = children[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "No flags active" in text

    def test_all_flags(self, stressed_row):
        children = format_flags(stressed_row)
        assert len(children) == 9  # all 9 flags active

    def test_flags_toggle_text_none(self, healthy_row):
        text = format_flags_toggle_text(healthy_row)
        assert "none active" in text

    def test_flags_toggle_text_count(self, stressed_row):
        text = format_flags_toggle_text(stressed_row)
        assert "9 active" in text


class TestFormatBooster:
    def test_green_light_format(self, healthy_row):
        children = format_booster(healthy_row)
        assert len(children) >= 2
        decision_text = children[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "Green light" in decision_text or "Both doses" in decision_text or "Borderline" in decision_text

    def test_skip_format(self, stressed_row):
        children = format_booster(stressed_row)
        decision_text = children[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "Recovery day" in decision_text or "skip" in decision_text.lower()

    def test_protocol_line(self, healthy_row):
        children = format_booster(healthy_row)
        protocol = children[-1]["paragraph"]["rich_text"][0]["text"]["content"]
        assert "Vyvanse" in protocol


class TestFormatExertion:
    def test_green_zone(self, healthy_row):
        recovery = compute_recovery(healthy_row)
        text = format_exertion_paragraph(healthy_row, recovery)
        assert "Zone 2" in text

    def test_red_zone(self, stressed_row):
        recovery = compute_recovery(stressed_row)
        text = format_exertion_paragraph(stressed_row, recovery)
        assert "Rest day" in text

    def test_rest_day_load(self, healthy_row):
        text = format_exertion_paragraph(
            healthy_row, compute_recovery(healthy_row)
        )
        assert "Rest day" in text

    def test_workout_summary(self):
        row = {
            "workout_rest_day": False,
            "workout_summary": "30 min zone 2 run",
            "workout_type": "Run",
        }
        recovery = {"zone": "GREEN"}
        text = format_exertion_paragraph(row, recovery)
        assert "30 min zone 2 run" in text


# ============================================================
# Rolling Averages
# ============================================================

class TestRollingAverages:
    def test_5_day_window(self, sample_rows):
        rolling = compute_rolling_averages(sample_rows, "2026-04-01")
        avg_5d = rolling[5]
        assert avg_5d.get("hrv_sdnn_ms") is not None
        assert avg_5d.get("rhr_bpm") is not None

    def test_window_respects_date_range(self, sample_rows):
        rolling = compute_rolling_averages(sample_rows, "2026-04-01")
        # 5-day window should include fewer rows than 40-day window
        avg_5 = rolling[5]
        avg_40 = rolling[40]
        assert avg_5 is not None
        assert avg_40 is not None

    def test_empty_rows(self):
        rolling = compute_rolling_averages([], "2026-04-06")
        for window in [5, 10, 20, 40]:
            for metric in ["hrv_sdnn_ms", "rhr_bpm", "sleep_deep_min", "hr_dip_pct"]:
                assert rolling[window][metric] is None

    def test_format_rolling_averages(self, sample_rows):
        rolling = compute_rolling_averages(sample_rows, "2026-04-01")
        children = format_rolling_averages(rolling)
        assert len(children) == 4  # HRV, RHR, Deep, HR dip
        for child in children:
            text = child["paragraph"]["rich_text"][0]["text"]["content"]
            assert "5d:" in text
            assert "40d:" in text


# ============================================================
# Utility Functions
# ============================================================

class TestTrendArrow:
    def test_up(self):
        assert _trend_arrow(60, 50, higher_is_better=True) == "↑"

    def test_down(self):
        assert _trend_arrow(40, 50, higher_is_better=True) == "↓"

    def test_flat(self):
        assert _trend_arrow(50.5, 50, higher_is_better=True) == "→"

    def test_rhr_lower_is_better(self):
        assert _trend_arrow(60, 65, higher_is_better=False) == "↑"

    def test_none_values(self):
        assert _trend_arrow(None, 50) == ""
        assert _trend_arrow(50, None) == ""


class TestMetricStatus:
    def test_ok(self):
        assert _metric_status(95, low=92) == "✅"

    def test_low(self):
        assert _metric_status(90, low=92) == "🔴"

    def test_high(self):
        assert _metric_status(20, high=18) == "⚠️"

    def test_none(self):
        assert _metric_status(None) == ""


class TestFmtMinutes:
    def test_hours_and_minutes(self):
        assert _fmt_minutes(432) == "7h 12m"

    def test_minutes_only(self):
        assert _fmt_minutes(45) == "45 min"

    def test_none(self):
        assert _fmt_minutes(None) == "--"

    def test_zero(self):
        assert _fmt_minutes(0) == "0 min"

    def test_exactly_one_hour(self):
        assert _fmt_minutes(60) == "1h 00m"


class TestClamp:
    def test_within_range(self):
        assert _clamp(50, 0, 100) == 50

    def test_below_range(self):
        assert _clamp(-10, 0, 100) == 0

    def test_above_range(self):
        assert _clamp(150, 0, 100) == 100


# ============================================================
# Config Loading
# ============================================================

class TestConfigLoading:
    def test_missing_config_raises(self):
        with patch("update_dashboard.CONFIG_FILE", Path("/nonexistent/path.json")):
            with pytest.raises(FileNotFoundError):
                load_dashboard_config()

    def test_valid_config(self, sample_config, tmp_path):
        config_file = tmp_path / "config" / "dashboard_ids.json"
        with patch("update_dashboard.CONFIG_FILE", config_file):
            config = load_dashboard_config()
        assert "Daily Dashboard" in config

    def test_get_daily_block_ids(self, sample_config):
        block_ids = get_daily_block_ids(sample_config)
        assert block_ids["recovery_callout"] == "block-recovery-callout"
        assert block_ids["breakdown_callout"] == "block-breakdown-callout"
        assert block_ids["metric_hrv"] == "block-metric-hrv"
        assert block_ids["sleep_total"] == "block-sleep-total"
        assert block_ids["flags_toggle"] == "block-flags-toggle"
        assert block_ids["booster_toggle"] == "block-booster-toggle"
        assert block_ids["averages_toggle"] == "block-averages-toggle"


# ============================================================
# Notion Row Extraction
# ============================================================

class TestExtractRow:
    def test_number_field(self):
        page = {
            "id": "test-id",
            "properties": {
                "hrv_sdnn_ms": {"type": "number", "number": 55.3},
            },
        }
        row = _extract_row(page)
        assert row["hrv_sdnn_ms"] == 55.3
        assert row["page_id"] == "test-id"

    def test_date_field(self):
        page = {
            "id": "test-id",
            "properties": {
                "date": {"type": "date", "date": {"start": "2026-04-06"}},
            },
        }
        row = _extract_row(page)
        assert row["date"] == "2026-04-06"

    def test_rich_text_field(self):
        page = {
            "id": "test-id",
            "properties": {
                "sleep_bedtime": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "11:15 PM"}],
                },
            },
        }
        row = _extract_row(page)
        assert row["sleep_bedtime"] == "11:15 PM"

    def test_formula_number(self):
        page = {
            "id": "test-id",
            "properties": {
                "sleep_efficiency_pct": {
                    "type": "formula",
                    "formula": {"type": "number", "number": 91.5},
                },
            },
        }
        row = _extract_row(page)
        assert row["sleep_efficiency_pct"] == 91.5

    def test_formula_boolean(self):
        page = {
            "id": "test-id",
            "properties": {
                "flag_deep_sleep_low": {
                    "type": "formula",
                    "formula": {"type": "boolean", "boolean": True},
                },
            },
        }
        row = _extract_row(page)
        assert row["flag_deep_sleep_low"] is True

    def test_multi_select(self):
        page = {
            "id": "test-id",
            "properties": {
                "source_tags": {
                    "type": "multi_select",
                    "multi_select": [{"name": "Apple Health"}],
                },
            },
        }
        row = _extract_row(page)
        assert row["source_tags"] == ["Apple Health"]

    def test_select_field(self):
        page = {
            "id": "test-id",
            "properties": {
                "stress_context": {
                    "type": "select",
                    "select": {"name": "High"},
                },
            },
        }
        row = _extract_row(page)
        assert row["stress_context"] == "High"

    def test_null_date(self):
        page = {
            "id": "test-id",
            "properties": {
                "date": {"type": "date", "date": None},
            },
        }
        row = _extract_row(page)
        assert row["date"] is None

    def test_empty_rich_text(self):
        page = {
            "id": "test-id",
            "properties": {
                "sleep_bedtime": {"type": "rich_text", "rich_text": []},
            },
        }
        row = _extract_row(page)
        assert row["sleep_bedtime"] is None


# ============================================================
# Baselines Computation
# ============================================================

class TestComputeBaseline:
    def test_7_day_baseline(self, sample_rows):
        baseline = _compute_baseline(sample_rows, "2026-04-01", 7)
        assert "hrv_sdnn_ms" in baseline
        assert "rhr_bpm" in baseline

    def test_60_day_baseline(self, sample_rows):
        baseline = _compute_baseline(sample_rows, "2026-04-01", 60)
        # All 10 rows fall within 60-day window
        assert "hrv_sdnn_ms" in baseline

    def test_empty_rows(self):
        baseline = _compute_baseline([], "2026-04-06", 7)
        assert baseline == {}


# ============================================================
# PATCH Block (mocked)
# ============================================================

class TestPatchBlock:
    def test_dry_run(self):
        result = patch_block("block-id", {"paragraph": {}}, None, dry_run=True)
        assert result is True

    def test_empty_block_id(self):
        result = patch_block("", {"paragraph": {}}, None, dry_run=False)
        assert result is False

    def test_successful_patch(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_client.patch.return_value = mock_response

        result = patch_block("block-id", {"paragraph": {}}, mock_client, dry_run=False)
        assert result is True
        mock_client.patch.assert_called_once()

    def test_429_retries(self):
        mock_client = MagicMock()
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "0"}
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.raise_for_status = MagicMock()
        mock_client.patch.side_effect = [resp_429, resp_ok]

        with patch("update_dashboard.time.sleep"):
            result = patch_block("block-id", {"paragraph": {}}, mock_client, dry_run=False)
        assert result is True
        assert mock_client.patch.call_count == 2

    def test_http_error(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = (
            httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)
        )
        mock_client.patch.return_value = mock_response

        result = patch_block("block-id", {"paragraph": {}}, mock_client, dry_run=False)
        assert result is False


# ============================================================
# Replace Toggle Children (mocked)
# ============================================================

class TestReplaceToggleChildren:
    def test_dry_run(self):
        result = replace_toggle_children(
            "toggle-id", [{"type": "paragraph"}], None, dry_run=True
        )
        assert result is True

    def test_empty_toggle_id(self):
        result = replace_toggle_children("", [], None, dry_run=False)
        assert result is False

    def test_successful_replace(self):
        mock_client = MagicMock()

        # Mock GET children
        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.json.return_value = {
            "results": [{"id": "child-1"}, {"id": "child-2"}]
        }

        # Mock DELETE children
        del_resp = MagicMock()
        del_resp.status_code = 200

        # Mock PATCH append children
        patch_resp = MagicMock()
        patch_resp.raise_for_status = MagicMock()

        mock_client.get.return_value = get_resp
        mock_client.delete.return_value = del_resp
        mock_client.patch.return_value = patch_resp

        new_children = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
        result = replace_toggle_children("toggle-id", new_children, mock_client, dry_run=False)
        assert result is True
        assert mock_client.delete.call_count == 2  # Deleted 2 old children


# ============================================================
# Full run_update (mocked)
# ============================================================

class TestRunUpdate:
    def test_missing_config(self, tmp_path):
        with patch("update_dashboard.CONFIG_FILE", tmp_path / "nonexistent.json"):
            result = run_update(date_str="2026-04-06", dry_run=True)
        assert result["status"] == "error"

    def test_dry_run_with_config(self, sample_config, tmp_path):
        config_file = tmp_path / "config" / "dashboard_ids.json"
        with patch("update_dashboard.CONFIG_FILE", config_file):
            result = run_update(date_str="2026-04-06", dry_run=True)
        # Dry run with placeholder data should complete
        assert result["status"] in ("success", "partial")
        assert result["updated"] > 0

    def test_no_row_found(self, sample_config, tmp_path):
        config_file = tmp_path / "config" / "dashboard_ids.json"

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": [], "has_more": False}
        mock_client.post.return_value = mock_resp

        with patch("update_dashboard.CONFIG_FILE", config_file), \
             patch("update_dashboard.httpx.Client") as MockClient:
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_client)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            # Patch the Client constructor to return our mock
            with patch("update_dashboard.httpx.Client", return_value=mock_client):
                mock_client.close = MagicMock()
                result = run_update(date_str="2026-04-06", dry_run=False)

        assert result["status"] == "error"
        assert "No Notion row found" in result["message"]

    def test_successful_update_with_mocked_api(self, sample_config, tmp_path, healthy_row):
        config_file = tmp_path / "config" / "dashboard_ids.json"

        # Build a mock Notion page response from healthy_row
        mock_page = _build_mock_page(healthy_row)

        mock_client = MagicMock()

        # Mock query_rows response
        query_resp = MagicMock()
        query_resp.status_code = 200
        query_resp.raise_for_status = MagicMock()
        query_resp.json.return_value = {
            "results": [mock_page],
            "has_more": False,
        }
        mock_client.post.return_value = query_resp

        # Mock PATCH responses
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.raise_for_status = MagicMock()
        mock_client.patch.return_value = patch_resp

        # Mock GET (for toggle children)
        get_resp = MagicMock()
        get_resp.raise_for_status = MagicMock()
        get_resp.json.return_value = {"results": []}
        mock_client.get.return_value = get_resp

        mock_client.close = MagicMock()

        with patch("update_dashboard.CONFIG_FILE", config_file), \
             patch("update_dashboard.httpx.Client", return_value=mock_client), \
             patch("update_dashboard.time.sleep"):
            result = run_update(date_str="2026-04-06", dry_run=False)

        assert result["status"] in ("success", "partial")
        assert result["recovery_score"] is not None
        assert result["recovery_zone"] == "GREEN"
        assert result["updated"] > 0

    def test_date_defaults_to_today(self, sample_config, tmp_path):
        config_file = tmp_path / "config" / "dashboard_ids.json"
        with patch("update_dashboard.CONFIG_FILE", config_file):
            result = run_update(dry_run=True)
        today = datetime.now().strftime("%Y-%m-%d")
        assert result["date"] == today


# ============================================================
# Helpers
# ============================================================

def _build_mock_page(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a flat row dict into a Notion-style page object for mocking."""
    props: dict[str, Any] = {}

    for key, val in row.items():
        if key in ("page_id",):
            continue

        if key == "date":
            props[key] = {"type": "date", "date": {"start": val} if val else None}
        elif key == "source_tags":
            props[key] = {
                "type": "multi_select",
                "multi_select": [{"name": t} for t in (val or [])],
            }
        elif key in ("sleep_bedtime", "sleep_waketime"):
            props[key] = {
                "type": "rich_text",
                "rich_text": [{"plain_text": str(val)}] if val else [],
            }
        elif key in ("stress_context",):
            props[key] = {
                "type": "select",
                "select": {"name": val} if val else None,
            }
        elif key in ("workout_rest_day", "morning_heaviness", "afternoon_crash"):
            props[key] = {"type": "checkbox", "checkbox": val or False}
        elif key.startswith("flag_"):
            props[key] = {
                "type": "formula",
                "formula": {"type": "boolean", "boolean": val or False},
            }
        elif key in ("sleep_efficiency_pct", "hr_dip_pct"):
            props[key] = {
                "type": "formula",
                "formula": {"type": "number", "number": val},
            }
        elif key == "hr_dip_category":
            props[key] = {
                "type": "formula",
                "formula": {"type": "string", "string": val},
            }
        elif key in ("workout_type", "workout_summary"):
            props[key] = {
                "type": "rich_text",
                "rich_text": [{"plain_text": str(val)}] if val else [],
            }
        elif isinstance(val, (int, float)):
            props[key] = {"type": "number", "number": val}
        elif isinstance(val, str):
            props[key] = {
                "type": "rich_text",
                "rich_text": [{"plain_text": val}],
            }

    return {"id": "mock-page-id", "properties": props}


