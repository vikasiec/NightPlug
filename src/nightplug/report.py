"""Morning HTML report generator."""

from __future__ import annotations

import html
from pathlib import Path

from nightplug.config import REPORTS_DIR, ensure_dirs
from nightplug.models import NightSummary
from nightplug.scoring import score_label


def _bar(pct: float, color: str) -> str:
    pct = max(0, min(100, pct))
    return (
        f'<div class="bar"><div class="bar-fill" style="width:{pct:.1f}%;'
        f'background:{color}"></div></div>'
    )


def _hms(secs: int) -> str:
    h = secs // 3600
    m = (secs % 3600) // 60
    return f"{h}h {m:02d}m"


def render_html(summary: NightSummary) -> str:
    label = score_label(summary.score)
    score_color = (
        "#22c55e"
        if summary.score >= 85
        else "#84cc16"
        if summary.score >= 70
        else "#f59e0b"
        if summary.score >= 50
        else "#ef4444"
    )

    reasons = "".join(
        f"<li>{html.escape(r)}</li>" for r in summary.score_reasons
    )
    events = ""
    if summary.apnea_candidates:
        rows = []
        for e in summary.apnea_candidates[:20]:
            rows.append(
                "<tr>"
                f"<td>{html.escape(e.start_ts)}</td>"
                f"<td>{html.escape(e.end_ts)}</td>"
                f"<td>{e.duration_secs}s</td>"
                f"<td>{html.escape(e.note)}</td>"
                "</tr>"
            )
        events = f"""
        <h2>Apnea-like candidates</h2>
        <p class="muted">Heuristic only — not a medical finding.</p>
        <table>
          <thead><tr><th>Start</th><th>End</th><th>Duration</th><th>Note</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        """
    else:
        events = "<h2>Apnea-like candidates</h2><p>None flagged.</p>"

    # Simple state mix bars
    tib = max(summary.time_in_bed_secs, 1)
    sleep_pct = 100 * summary.sleep_like_secs / tib
    rest_pct = 100 * summary.restless_secs / tib
    awake_pct = 100 * summary.awake_in_bed_secs / tib

    timeline_bits = []
    for seg in summary.state_timeline[:40]:
        timeline_bits.append(
            f"<span class='chip chip-{html.escape(seg['state'])}'>"
            f"{html.escape(seg['state'])}</span>"
        )
    timeline = " ".join(timeline_bits) if timeline_bits else "<span class='muted'>n/a</span>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NightPlug — {html.escape(summary.night_id)}</title>
  <style>
    :root {{
      --bg: #0b1220;
      --card: #121a2b;
      --text: #e8eefc;
      --muted: #93a0b8;
      --accent: #38bdf8;
      --border: #243049;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1e293b, var(--bg));
      color: var(--text); line-height: 1.5; padding: 2rem 1rem 4rem;
    }}
    .wrap {{ max-width: 820px; margin: 0 auto; }}
    header {{
      display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: center;
      justify-content: space-between; margin-bottom: 1.5rem;
    }}
    h1 {{ margin: 0; font-size: 1.6rem; letter-spacing: 0.02em; }}
    .sub {{ color: var(--muted); margin: 0.25rem 0 0; }}
    .score-card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 1.25rem 1.5rem; min-width: 160px; text-align: center;
    }}
    .score {{
      font-size: 3rem; font-weight: 700; color: {score_color}; line-height: 1;
    }}
    .label {{ color: var(--muted); margin-top: 0.35rem; }}
    .grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 0.85rem; margin: 1.25rem 0;
    }}
    .metric {{
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      padding: 1rem;
    }}
    .metric .k {{ color: var(--muted); font-size: 0.85rem; }}
    .metric .v {{ font-size: 1.35rem; font-weight: 600; margin-top: 0.2rem; }}
    .card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 1.25rem 1.5rem; margin-top: 1rem;
    }}
    h2 {{ margin: 0 0 0.75rem; font-size: 1.1rem; }}
    ul {{ margin: 0; padding-left: 1.2rem; }}
    li {{ margin: 0.35rem 0; }}
    .muted {{ color: var(--muted); font-size: 0.9rem; }}
    .bar {{
      height: 10px; background: #1f2937; border-radius: 999px; overflow: hidden;
      margin: 0.35rem 0 0.75rem;
    }}
    .bar-fill {{ height: 100%; border-radius: 999px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-weight: 500; }}
    .chip {{
      display: inline-block; font-size: 0.72rem; padding: 0.15rem 0.45rem;
      border-radius: 999px; margin: 0.15rem; background: #1f2937; color: var(--muted);
    }}
    .chip-sleep_like {{ background: #14532d; color: #bbf7d0; }}
    .chip-restless {{ background: #713f12; color: #fde68a; }}
    .chip-awake_in_bed {{ background: #7c2d12; color: #fed7aa; }}
    .chip-in_bed {{ background: #1e3a5f; color: #bae6fd; }}
    .chip-empty, .chip-up {{ background: #374151; color: #d1d5db; }}
    footer {{
      margin-top: 1.5rem; padding: 1rem; border-left: 3px solid var(--accent);
      color: var(--muted); font-size: 0.88rem;
    }}
    .brand {{ color: var(--accent); font-weight: 600; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1><span class="brand">NightPlug</span> · Morning report</h1>
        <p class="sub">{html.escape(summary.night_id)} · source: {html.escape(summary.source)}</p>
        <p class="sub">{html.escape(summary.started_at)} → {html.escape(summary.ended_at)}</p>
      </div>
      <div class="score-card">
        <div class="score">{summary.score}</div>
        <div class="label">{html.escape(label)}</div>
      </div>
    </header>

    <div class="grid">
      <div class="metric"><div class="k">Time in bed</div>
        <div class="v">{_hms(summary.time_in_bed_secs)}</div></div>
      <div class="metric"><div class="k">Sleep-like</div>
        <div class="v">{_hms(summary.sleep_like_secs)}</div></div>
      <div class="metric"><div class="k">Restless</div>
        <div class="v">{_hms(summary.restless_secs)}</div></div>
      <div class="metric"><div class="k">Awake in bed</div>
        <div class="v">{_hms(summary.awake_in_bed_secs)}</div></div>
      <div class="metric"><div class="k">Avg breathing</div>
        <div class="v">{summary.avg_breathing_bpm:.1f} bpm</div></div>
      <div class="metric"><div class="k">Breathing range</div>
        <div class="v">{summary.min_breathing_bpm:.0f}–{summary.max_breathing_bpm:.0f}</div></div>
      <div class="metric"><div class="k">Apnea-like events</div>
        <div class="v">{summary.apnea_like_events}</div></div>
      <div class="metric"><div class="k">Samples</div>
        <div class="v">{summary.sample_count:,}</div></div>
    </div>

    <div class="card">
      <h2>In-bed composition</h2>
      <div class="muted">Sleep-like</div>
      {_bar(sleep_pct, "#22c55e")}
      <div class="muted">Restless</div>
      {_bar(rest_pct, "#f59e0b")}
      <div class="muted">Awake motion</div>
      {_bar(awake_pct, "#f97316")}
    </div>

    <div class="card">
      <h2>Why this score</h2>
      <ul>{reasons}</ul>
    </div>

    <div class="card">
      <h2>State timeline (segments)</h2>
      <div>{timeline}</div>
    </div>

    <div class="card">
      {events}
    </div>

    <footer>
      {html.escape(summary.disclaimer)}
      Hardware path: ESP32-S3 bedside node → local logger → this report. No cloud.
    </footer>
  </div>
</body>
</html>
"""


def write_report(summary: NightSummary, path: Path | None = None) -> Path:
    ensure_dirs()
    out = path or (REPORTS_DIR / f"{summary.night_id}.html")
    out.write_text(render_html(summary), encoding="utf-8")
    return out
