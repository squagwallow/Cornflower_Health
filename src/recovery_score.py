"""
Recovery Score Computation
Cornflower Health project — src/recovery_score.py

Implements the recovery scoring algorithm from docs/coaching-layer.md.
Pure computation — no API calls, no side effects.

Components:
  - HRV component (0–60): (hrv / hrv_baseline_60d) * 60, capped at 60
  - RHR component (0–40): clamp(((rhr_baseline_60d - rhr) / rhr_baseline_60d) * 40 + 40, 0, 40)
  - Modifier adjustments (deep sleep, SpO2, resp rate, sleep quality, stress)
  - Hard gate overrides (RHR >68, deep <35, HRV <40 AND deep <35)
"""

import logging
from typing import Any

logger = logging.getLogger("cornflower.recovery_score")

# Zone boundaries
ZONE_GREEN = (75, 100)
ZONE_YELLOW = (50, 74)
ZONE_ORANGE = (25, 49)
ZONE_RED = (0, 24)

ZONE_MAP = [
    (75, "GREEN"),
    (50, "YELLOW"),
    (25, "ORANGE"),
    (0, "RED"),
]

ZONE_COLORS = {
    "GREEN": "green_background",
    "YELLOW": "yellow_background",
    "ORANGE": "orange_background",
    "RED": "red_background",
}

ZONE_EMOJIS = {
    "GREEN": "🟢",
    "YELLOW": "🟡",
    "ORANGE": "🟠",
    "RED": "🔴",
}

ZONE_DESCRIPTIONS = {
    "GREEN": "Full training cleared",
    "YELLOW": "Moderate load only",
    "ORANGE": "Light activity or active recovery",
    "RED": "Rest day; no structured training",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_hrv_component(hrv_ms: float, hrv_baseline_60d: float) -> float:
    """HRV component: (hrv / baseline) * 60, capped at 60."""
    if hrv_baseline_60d <= 0:
        return 0.0
    raw = (hrv_ms / hrv_baseline_60d) * 60.0
    return min(raw, 60.0)


def compute_rhr_component(rhr_bpm: float, rhr_baseline_60d: float) -> float:
    """RHR component: clamp(((baseline - rhr) / baseline) * 40 + 40, 0, 40)."""
    if rhr_baseline_60d <= 0:
        return 0.0
    raw = ((rhr_baseline_60d - rhr_bpm) / rhr_baseline_60d) * 40.0 + 40.0
    return _clamp(raw, 0.0, 40.0)


def compute_modifiers(row: dict[str, Any]) -> list[tuple[str, float, str]]:
    """
    Compute modifier adjustments from a Notion row.
    Returns list of (label, adjustment, reason) tuples.
    """
    modifiers: list[tuple[str, float, str]] = []

    # Deep sleep modifier
    deep = row.get("sleep_deep_min")
    if deep is not None:
        if deep >= 80:
            modifiers.append(("Deep sleep", +5, f"{deep:.0f} min — excellent"))
        elif deep >= 65:
            modifiers.append(("Deep sleep", +3, f"{deep:.0f} min — good"))
        elif deep >= 50:
            modifiers.append(("Deep sleep", 0, f"{deep:.0f} min — neutral"))
        elif deep >= 35:
            modifiers.append(("Deep sleep", -5, f"{deep:.0f} min — mild deficit"))
        elif deep >= 20:
            modifiers.append(("Deep sleep", -10, f"{deep:.0f} min — moderate deficit"))
        else:
            modifiers.append(("Deep sleep", -15, f"{deep:.0f} min — severe deficit"))
    else:
        modifiers.append(("Deep sleep", 0, "no data"))

    # SpO2 avg modifier
    spo2 = row.get("spo2_avg_pct")
    if spo2 is not None:
        if spo2 >= 95:
            modifiers.append(("SpO2 avg", 0, f"{spo2:.0f}% — normal"))
        elif spo2 >= 92:
            modifiers.append(("SpO2 avg", -3, f"{spo2:.0f}% — borderline"))
        else:
            modifiers.append(("SpO2 avg", -8, f"{spo2:.0f}% — significant"))
    else:
        modifiers.append(("SpO2 avg", 0, "no data"))

    # SpO2 min modifier (stacks with avg)
    spo2_min = row.get("spo2_min_pct")
    if spo2_min is not None and spo2_min < 88:
        modifiers.append(("SpO2 min", -5, f"{spo2_min:.0f}% — low nadir"))

    # Respiratory rate modifier
    resp = row.get("resp_rate_brpm")
    if resp is not None:
        if resp <= 15:
            modifiers.append(("Resp rate", +2, f"{resp:.1f} — low arousal"))
        elif resp >= 19:
            modifiers.append(("Resp rate", -5, f"{resp:.1f} — elevated"))
        else:
            modifiers.append(("Resp rate", 0, f"{resp:.1f} — normal"))
    else:
        modifiers.append(("Resp rate", 0, "no data"))

    # Fragmented sleep (≥4 awakenings)
    awakenings = row.get("sleep_awakenings_count")
    if awakenings is not None and awakenings >= 4:
        modifiers.append(("Sleep quality", -5, f"{awakenings} awakenings — fragmented"))

    # Early wake (waketime_num ≤ 300 = before 5:00 AM)
    waketime_num = row.get("sleep_waketime_num")
    if waketime_num is not None and waketime_num <= 300:
        modifiers.append(("Early wake", -3, f"wake at {waketime_num // 60}:{waketime_num % 60:02d}"))

    # Stress context
    stress = row.get("stress_context")
    if stress is not None and isinstance(stress, str) and stress.lower() in ("high", "extreme"):
        modifiers.append(("Stress", -5, f"{stress}"))

    return modifiers


def compute_hard_gates(row: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Evaluate hard gate rules.
    Returns list of (gate_name, effect) tuples for active gates.
    """
    gates: list[tuple[str, str]] = []
    rhr = row.get("rhr_bpm")
    deep = row.get("sleep_deep_min")
    hrv = row.get("hrv_sdnn_ms")

    if rhr is not None and rhr > 68:
        gates.append(("RHR > 68", "cap_yellow"))

    if deep is not None and deep < 35:
        gates.append(("Deep < 35 min", "cap_yellow"))

    if (hrv is not None and hrv < 40) and (deep is not None and deep < 35):
        gates.append(("HRV < 40 AND Deep < 35", "force_red"))

    return gates


def score_to_zone(score: float) -> str:
    """Map a numeric score to a zone name."""
    for threshold, zone in ZONE_MAP:
        if score >= threshold:
            return zone
    return "RED"


def apply_hard_gates(score: float, zone: str, gates: list[tuple[str, str]]) -> tuple[float, str]:
    """Apply hard gate overrides to zone. Returns (score, zone)."""
    for _, effect in gates:
        if effect == "force_red":
            return (min(score, 24), "RED")

    for _, effect in gates:
        if effect == "cap_yellow" and zone == "GREEN":
            return (min(score, 74), "YELLOW")

    return (score, zone)


def compute_recovery(row: dict[str, Any]) -> dict[str, Any]:
    """
    Full recovery score computation.

    Args:
        row: dict with Notion field names (hrv_sdnn_ms, rhr_bpm, etc.)
             Must include hrv_baseline_60d_ms and rhr_baseline_60d_bpm.

    Returns dict with:
        score: final numeric score (0–100)
        zone: GREEN/YELLOW/ORANGE/RED
        zone_color: Notion callout background color
        zone_emoji: zone emoji
        zone_desc: zone description
        hrv_component: HRV component value (0–60)
        rhr_component: RHR component value (0–40)
        base_score: hrv + rhr before modifiers
        modifiers: list of (label, adjustment, reason)
        modifier_total: sum of modifier adjustments
        hard_gates: list of (gate_name, effect)
        hard_gate_active: bool — any hard gate fired
    """
    hrv = row.get("hrv_sdnn_ms")
    rhr = row.get("rhr_bpm")
    hrv_baseline = row.get("hrv_baseline_60d_ms")
    rhr_baseline = row.get("rhr_baseline_60d_bpm")

    # If we lack core inputs, return a minimal result
    if hrv is None or rhr is None or hrv_baseline is None or rhr_baseline is None:
        missing = []
        if hrv is None:
            missing.append("hrv_sdnn_ms")
        if rhr is None:
            missing.append("rhr_bpm")
        if hrv_baseline is None:
            missing.append("hrv_baseline_60d_ms")
        if rhr_baseline is None:
            missing.append("rhr_baseline_60d_bpm")
        logger.warning("Cannot compute recovery — missing: %s", ", ".join(missing))
        return {
            "score": None,
            "zone": "UNKNOWN",
            "zone_color": "gray_background",
            "zone_emoji": "⚪",
            "zone_desc": "Insufficient data",
            "hrv_component": None,
            "rhr_component": None,
            "base_score": None,
            "modifiers": [],
            "modifier_total": 0,
            "hard_gates": [],
            "hard_gate_active": False,
            "missing_fields": missing,
        }

    hrv_comp = compute_hrv_component(hrv, hrv_baseline)
    rhr_comp = compute_rhr_component(rhr, rhr_baseline)
    base = hrv_comp + rhr_comp

    modifiers = compute_modifiers(row)
    mod_total = sum(adj for _, adj, _ in modifiers)

    raw_score = _clamp(base + mod_total, 0, 100)
    zone = score_to_zone(raw_score)

    gates = compute_hard_gates(row)
    final_score, final_zone = apply_hard_gates(raw_score, zone, gates)
    final_score = _clamp(final_score, 0, 100)

    return {
        "score": round(final_score, 1),
        "zone": final_zone,
        "zone_color": ZONE_COLORS.get(final_zone, "gray_background"),
        "zone_emoji": ZONE_EMOJIS.get(final_zone, "⚪"),
        "zone_desc": ZONE_DESCRIPTIONS.get(final_zone, ""),
        "hrv_component": round(hrv_comp, 1),
        "rhr_component": round(rhr_comp, 1),
        "base_score": round(base, 1),
        "modifiers": modifiers,
        "modifier_total": mod_total,
        "hard_gates": gates,
        "hard_gate_active": len(gates) > 0,
    }


def compute_booster_decision(row: dict[str, Any]) -> dict[str, str]:
    """
    Evaluate the daily booster go/no-go decision tree.

    Returns dict with:
        decision: human-readable decision string
        status: "Both doses" / "First only" / "Recovery day — skip"
        emoji: 🟢/🟡/🔴
    """
    hrv = row.get("hrv_sdnn_ms")
    rhr = row.get("rhr_bpm")
    deep = row.get("sleep_deep_min")

    # Step 1: HRV < 40?
    if hrv is not None and hrv < 40:
        return {
            "decision": "Recovery day — skip both boosters (HRV < 40)",
            "status": "Recovery day — skip",
            "emoji": "🔴",
        }

    # Step 2: RHR > 68?
    if rhr is not None and rhr > 68:
        return {
            "decision": "Recovery day — skip both boosters (RHR > 68)",
            "status": "Recovery day — skip",
            "emoji": "🔴",
        }

    # Step 3: Deep < 35?
    if deep is not None and deep < 35:
        return {
            "decision": "Recovery day — skip both boosters (deep < 35 min)",
            "status": "Recovery day — skip",
            "emoji": "🔴",
        }

    # Step 4: Borderline
    if (deep is not None and 35 <= deep < 50) and (hrv is not None and 40 <= hrv < 48):
        return {
            "decision": "Borderline — first booster only (deep 35–50, HRV 40–47)",
            "status": "First only",
            "emoji": "🟡",
        }

    # Step 5: Green light
    if (deep is not None and deep >= 50) and (hrv is not None and hrv >= 48) and (rhr is not None and rhr <= 66):
        return {
            "decision": "Green light — both doses cleared",
            "status": "Both doses",
            "emoji": "🟢",
        }

    # Fallback: insufficient data or doesn't match any rule cleanly
    return {
        "decision": "Insufficient data for booster decision",
        "status": "Unknown",
        "emoji": "⚪",
    }
