# Persistent Flags — Always-Active Context

This file contains Tier 0 and Tier 1 context that is loaded at the start of every coaching session. It does not expire. Update it when the protocol changes or a major health event occurs.

---

## Medication Protocol (Tier 0 — Permanent)

- **Vyvanse:** 60 mg — morning baseline, taken daily
- **Booster 1:** Dextroamphetamine 5 mg — target ~10:00 AM
- **Booster 2:** Dextroamphetamine 5 mg — target ~1:00 PM
- Current step on titration ladder: **Step 4 (5 mg + 5 mg)**

Advancement to Step 5 requires 7 consecutive days meeting all gates:
deep_sleep_min ≥50, hrv_sdnn_ms ≈50, rhr_bpm 61–66, no morning_heaviness, no afternoon_crash.

---

## Personal Baselines (Tier 0 — Permanent until recalibrated)

- HRV 60-day rolling baseline: **53.2 ms** (as of April 2026)
- RHR target: **61–66 bpm**
- These are calibrated estimates. Recalibrate after 60+ days of clean data when the rolling baseline computation is built.

---

## Reference Event: The March Crash (Tier 1 — Active)

A stacked physiological load event in March 2026 used as a calibration reference for load interpretation.

- High life stress (external stressor, sustained)
- Poor sleep: deep < 35 min for approximately 5–7 consecutive nights
- Elevated RHR: > 68 bpm sustained
- Suppressed HRV: < 40 ms sustained
- Outcome: RED zone on all affected days; boosters held

**Coaching layer use:** When interpreting stacked load signals (stress + poor sleep + elevated RHR occurring together), reference this event as a calibration anchor. This pattern should always produce ORANGE or RED regardless of HRV alone.

---

## HRV Methodology Note (Tier 2 — Under Review)

Bevel and Athlytic use different HRV calculation methods and show notably different scores for the same nights. This has not been resolved. Until the methodology is aligned:

- Use Athlytic as the primary score reference
- Note divergences between Athlytic and Bevel when screenshots are provided
- Do not assume either app is definitively correct
- Flag large divergences (>15 ms difference) as worth investigating

---

*Last updated: 2026-04-07*
