"""NightPlug command-line interface."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from nightplug import __product__, __version__
from nightplug.config import DATA_DIR, ESP32_ETA, ESP32_NOTE, REPORTS_DIR, ROOT, ensure_dirs
from nightplug.ingest import DEFAULT_PORT, listen
from nightplug.logger import append_samples, latest_night, list_nights, load_samples, write_samples
from nightplug.report import write_report
from nightplug.scoring import score_night
from nightplug.session import analyze_samples
from nightplug.simulate import PROFILES, simulate_night
from nightplug.sync import DEFAULT_HTTP_PORT, SyncError, sync
from nightplug.webui import DEFAULT_UI_PORT
from nightplug.webui import run as run_webui


def _cmd_status(_: argparse.Namespace) -> int:
    ensure_dirs()
    nights = list_nights()
    print(f"{__product__} v{__version__}")
    print(f"  root:     {ROOT}")
    print(f"  nights:   {DATA_DIR} ({len(nights)} file(s))")
    print(f"  reports:  {REPORTS_DIR}")
    print(f"  hardware: {ESP32_NOTE} (ETA {ESP32_ETA})")
    if nights:
        print(f"  latest:   {nights[-1].name}")
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    ensure_dirs()
    night_id = args.date or date.today().isoformat()
    samples = simulate_night(
        hours=args.hours,
        seed=args.seed,
        profile=args.profile,
    )
    # Re-stamp dates onto chosen night_id calendar if needed
    if args.date:
        samples = _rebase_night_id(samples, args.date)

    path = write_samples(samples, night_id=night_id)
    print(f"Wrote {len(samples):,} samples -> {path}")
    return 0


def _rebase_night_id(samples, night_id: str):
    """Shift sample timestamps so the night falls on night_id evening."""
    from datetime import timedelta

    from nightplug.models import Sample

    day = date.fromisoformat(night_id)
    # Report date morning → bed start previous day 23:00
    start = datetime(day.year, day.month, day.day) - timedelta(days=1)
    start = start.replace(hour=23, minute=0, second=0, microsecond=0)
    out = []
    for i, s in enumerate(samples):
        ts = (start + timedelta(seconds=i)).isoformat(timespec="seconds")
        out.append(
            Sample(
                ts=ts,
                presence=s.presence,
                motion=s.motion,
                breathing_bpm=s.breathing_bpm,
                signal_quality=s.signal_quality,
                source=s.source,
            )
        )
    return out


def _analyze_path(path: Path):
    night_id, samples = load_samples(path)
    if not samples:
        raise SystemExit(f"No samples in {path}")
    summary = analyze_samples(samples, night_id=night_id)
    return score_night(summary)


def _cmd_report(args: argparse.Namespace) -> int:
    ensure_dirs()
    if args.latest:
        path = latest_night()
        if path is None:
            print("No nights found. Run: python -m nightplug simulate", file=sys.stderr)
            return 1
    elif args.date:
        path = DATA_DIR / f"{args.date}.jsonl"
        if not path.exists():
            print(f"Missing {path}", file=sys.stderr)
            return 1
    elif args.file:
        path = Path(args.file)
    else:
        path = latest_night()
        if path is None:
            print("No nights found. Run: python -m nightplug simulate", file=sys.stderr)
            return 1

    summary = _analyze_path(path)
    out = write_report(summary)
    print(f"Score: {summary.score}/100")
    print(f"Time in bed: {summary.time_in_bed_hours:.2f} h")
    print(f"Sleep-like:  {summary.sleep_like_secs / 3600:.2f} h")
    print(f"Restless:    {summary.restless_secs / 60:.0f} min")
    print(f"Apnea-like:  {summary.apnea_like_events}")
    print(f"Report -> {out}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    args.date = args.date or date.today().isoformat()
    args.hours = getattr(args, "hours", 8.0)
    args.seed = getattr(args, "seed", 42)
    args.profile = getattr(args, "profile", "normal")
    rc = _cmd_simulate(args)
    if rc != 0:
        return rc
    args.latest = False
    args.file = None
    return _cmd_report(args)


def _cmd_live(args: argparse.Namespace) -> int:
    ensure_dirs()
    night_id = args.date or date.today().isoformat()
    duration = args.minutes * 60.0 if args.minutes else None
    port = args.port

    print(f"Listening for ESP32 vitals on UDP {port} ... (Ctrl+C to stop)")
    samples: list = []
    try:
        for sample in listen(port=port, duration_secs=duration):
            samples.append(sample)
            print(
                f"  presence={sample.presence:.2f} motion={sample.motion:.2f} "
                f"breathing={sample.breathing_bpm:.1f}bpm quality={sample.signal_quality:.2f}"
            )
    except KeyboardInterrupt:
        print("\nStopped.")

    if not samples:
        print("No vitals packets received. Check the board is provisioned and on the same network.")
        return 1

    path = append_samples(samples, night_id=night_id)
    print(f"Wrote {len(samples):,} samples -> {path}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    ensure_dirs()
    print(f"Pulling buffered data from {args.host}:{args.port} ...")
    try:
        added = sync(args.host, port=args.port)
    except SyncError as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1

    if not added:
        print("Nothing new — device buffer is empty or already caught up.")
        return 0

    total = sum(added.values())
    print(f"Pulled {total:,} new sample(s) across {len(added)} night(s):")
    for night_id, count in sorted(added.items()):
        print(f"  {night_id}: +{count:,}")
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    ensure_dirs()
    run_webui(port=args.port, host=args.host, open_browser=not args.no_browser)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nightplug",
        description="NightPlug — contactless sleep clinic in a plug",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="Show paths and data status")
    s.set_defaults(func=_cmd_status)

    sim = sub.add_parser("simulate", help="Generate a synthetic night log")
    sim.add_argument("--hours", type=float, default=8.0)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--profile", choices=PROFILES, default="normal")
    sim.add_argument("--date", help="Night id / report date YYYY-MM-DD")
    sim.set_defaults(func=_cmd_simulate)

    rep = sub.add_parser("report", help="Build morning HTML report from a night log")
    g = rep.add_mutually_exclusive_group()
    g.add_argument("--latest", action="store_true", help="Use newest JSONL")
    g.add_argument("--date", help="Night id YYYY-MM-DD")
    g.add_argument("--file", help="Path to JSONL")
    rep.set_defaults(func=_cmd_report)

    demo = sub.add_parser("demo", help="Simulate a night and open-ready report")
    demo.add_argument("--hours", type=float, default=8.0)
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--profile", choices=PROFILES, default="normal")
    demo.add_argument("--date", help="Night id YYYY-MM-DD")
    demo.set_defaults(func=_cmd_demo)

    live = sub.add_parser("live", help="Ingest real vitals from an ESP32 CSI node over UDP")
    live.add_argument("--port", type=int, default=DEFAULT_PORT)
    live.add_argument("--minutes", type=float, default=None, help="Stop after N minutes (default: run until Ctrl+C)")
    live.add_argument("--date", help="Night id YYYY-MM-DD")
    live.set_defaults(func=_cmd_live)

    sy = sub.add_parser("sync", help="Pull buffered data from an ESP32 board's local HTTP API")
    sy.add_argument("--host", required=True, help="Board's IP address or hostname")
    sy.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    sy.set_defaults(func=_cmd_sync)

    ui = sub.add_parser("ui", help="Launch the local dashboard (Tonight / Trends / Device)")
    ui.add_argument("--port", type=int, default=DEFAULT_UI_PORT)
    ui.add_argument("--host", help="ESP32 board's IP, for the Device page and Sync button")
    ui.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab")
    ui.set_defaults(func=_cmd_ui)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
