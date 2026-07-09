"""Transparent sleep score — every point loss is explained."""

from __future__ import annotations

from nightplug.models import NightSummary


def score_night(summary: NightSummary) -> NightSummary:
    """
    Start at 100; subtract explainable penalties.

    This is a personal wellness score, not a clinical index.
    """
    score = 100
    reasons: list[str] = []

    hours = summary.time_in_bed_hours
    if hours < 5.0:
        score -= 25
        reasons.append(f"Short time in bed ({hours:.1f} h) −25")
    elif hours < 6.0:
        score -= 15
        reasons.append(f"Under 6 h in bed ({hours:.1f} h) −15")
    elif hours < 6.5:
        score -= 5
        reasons.append(f"Slightly short night ({hours:.1f} h) −5")
    elif hours > 10.0:
        score -= 8
        reasons.append(f"Very long time in bed ({hours:.1f} h) −8")
    else:
        reasons.append(f"Time in bed OK ({hours:.1f} h)")

    restless_min = summary.restless_secs / 60.0
    restless_pen = min(30, int(restless_min * 0.5))
    if restless_pen:
        score -= restless_pen
        reasons.append(f"Restlessness ({restless_min:.0f} min) −{restless_pen}")
    else:
        reasons.append("Low restlessness")

    awake_min = summary.awake_in_bed_secs / 60.0
    awake_pen = min(20, int(awake_min * 0.35))
    if awake_pen:
        score -= awake_pen
        reasons.append(f"Awake-in-bed motion ({awake_min:.0f} min) −{awake_pen}")

    # Sleep efficiency proxy
    if summary.time_in_bed_secs > 0:
        eff = summary.sleep_like_secs / summary.time_in_bed_secs
        if eff < 0.55:
            score -= 15
            reasons.append(f"Low sleep-like fraction ({eff:.0%}) −15")
        elif eff < 0.70:
            score -= 8
            reasons.append(f"Moderate sleep-like fraction ({eff:.0%}) −8")
        else:
            reasons.append(f"Sleep-like fraction OK ({eff:.0%})")

    events = summary.apnea_like_events
    if events:
        pen = min(20, events * 2)
        score -= pen
        reasons.append(
            f"{events} apnea-like candidate(s) −{pen} (heuristic only, not diagnosis)"
        )
    else:
        reasons.append("No apnea-like candidates flagged")

    # Breathing plausibility
    if summary.avg_breathing_bpm > 0:
        if summary.avg_breathing_bpm < 8 or summary.avg_breathing_bpm > 24:
            score -= 5
            reasons.append(
                f"Average breathing outside typical rest range "
                f"({summary.avg_breathing_bpm:.1f} bpm) −5"
            )
        else:
            reasons.append(f"Avg breathing {summary.avg_breathing_bpm:.1f} bpm")

    summary.score = max(0, min(100, score))
    summary.score_reasons = reasons
    return summary


def score_label(score: int) -> str:
    if score >= 85:
        return "Strong night"
    if score >= 70:
        return "Decent night"
    if score >= 50:
        return "Rough night"
    return "Difficult night"
