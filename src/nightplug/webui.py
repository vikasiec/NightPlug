"""Local dashboard — stdlib-only HTTP server, no external dependencies.

Serves a single-page dashboard (Tonight / Trends / Device) reading from
data/nights/*.jsonl and, for the Device page, the ESP32's own local HTTP
API (see sync.py / the sibling RuView firmware's sample_buffer.c).
Everything shown is either data actually on disk or actually fetched from
the device — nothing here is fabricated to fill a gap in what's queryable.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from nightplug.config import DATA_DIR, ensure_dirs
from nightplug.logger import latest_night, list_nights, load_samples
from nightplug.models import NightSummary, Sample
from nightplug.scoring import score_label, score_night
from nightplug.session import analyze_samples
from nightplug.sync import SyncError, fetch_json, load_cursor, sync

DASHBOARD_HTML_PATH = Path(__file__).parent / "web" / "dashboard.html"
DEFAULT_UI_PORT = 8420

# Set by `nightplug ui --host`; overridable per-request via ?host=.
_default_host: str | None = None


def _downsample(samples: list[Sample], target_points: int = 160) -> dict:
    """Bucket a night's samples into ~target_points averaged points, so
    the Tonight charts stay smooth and small regardless of the source
    rate (1Hz simulator vs ~2Hz hardware vs a sparse buffered pull).
    """
    if not samples:
        return {"times": [], "motion": [], "breathing": []}

    n = len(samples)
    bucket_size = max(1, n // target_points)
    times, motion, breathing = [], [], []
    for i in range(0, n, bucket_size):
        chunk = samples[i : i + bucket_size]
        times.append(chunk[len(chunk) // 2].ts)
        motion.append(round(sum(s.motion for s in chunk) / len(chunk), 3))
        breathing.append(round(sum(s.breathing_bpm for s in chunk) / len(chunk), 2))
    return {"times": times, "motion": motion, "breathing": breathing}


def _heart_rate_stats(samples: list[Sample]) -> dict:
    """Experimental heart rate summary — deliberately kept separate from
    NightSummary/scoring. The firmware's heartbeat_conf is a binary
    plausible-range flag, not a real confidence score, and CSI-only heart
    rate (no mmWave hardware) is known to be much less reliable than
    presence/motion/breathing — surfaced for visibility, not trusted for
    the score.
    """
    confident = [s for s in samples if s.heartbeat_bpm > 0]
    if not confident:
        return {"avg_bpm": None, "confident_samples": 0, "total_samples": len(samples), "coverage_pct": 0.0}
    avg = sum(s.heartbeat_bpm for s in confident) / len(confident)
    return {
        "avg_bpm": round(avg, 1),
        "confident_samples": len(confident),
        "total_samples": len(samples),
        "coverage_pct": round(100 * len(confident) / len(samples), 1) if samples else 0.0,
    }


def _summary_to_dict(summary: NightSummary) -> dict:
    d = summary.to_dict()
    d["label"] = score_label(summary.score)
    d["time_in_bed_hours"] = round(summary.time_in_bed_hours, 2)
    return d


def _tonight_payload(night_id: str | None) -> dict:
    ensure_dirs()
    if night_id:
        path = DATA_DIR / f"{night_id}.jsonl"
        if not path.exists():
            return {"error": f"No data for {night_id}"}
    else:
        path = latest_night()
        if path is None:
            return {"error": "No nights recorded yet. Run: python -m nightplug demo"}

    loaded_id, samples = load_samples(path)
    if not samples:
        return {"error": f"{loaded_id} has no samples"}

    summary = score_night(analyze_samples(samples, night_id=loaded_id))
    payload = _summary_to_dict(summary)
    payload["series"] = _downsample(samples)
    payload["heart_rate"] = _heart_rate_stats(samples)
    return payload


def _trends_payload(days: int) -> dict:
    ensure_dirs()
    cutoff = date.today() - timedelta(days=days)
    nights = []
    for path in list_nights():
        try:
            night_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if night_date < cutoff:
            continue
        _, samples = load_samples(path)
        if not samples:
            continue
        summary = score_night(analyze_samples(samples, night_id=path.stem))
        nights.append(
            {
                "night_id": path.stem,
                "score": summary.score,
                "time_in_bed_hours": round(summary.time_in_bed_hours, 2),
                "avg_breathing_bpm": summary.avg_breathing_bpm,
                "gap_count": summary.gap_count,
                "gap_secs_total": summary.gap_secs_total,
            }
        )
    nights.sort(key=lambda n: n["night_id"])
    return {"nights": nights}


def _device_payload(host: str | None) -> dict:
    host = host or _default_host
    if not host:
        return {"reachable": False, "host": None, "error": "No device host configured — pass ?host= or start with `nightplug ui --host <ip>`"}

    def _describe(e: Exception) -> str:
        # Timeout/connection errors often stringify to "" (e.g. bare
        # socket.timeout) — fall back to the exception's type name so the
        # UI never shows a message with nothing after the colon.
        return str(e) or type(e).__name__

    result: dict = {"reachable": False, "host": host, "ota": None, "buffer": None, "error": None}
    try:
        result["ota"] = fetch_json(f"http://{host}:8032/ota/status", timeout=4.0)
    except Exception as e:  # noqa: BLE001 — surfaced to the UI, not swallowed
        result["error"] = f"OTA status unreachable: {_describe(e)}"
    try:
        result["buffer"] = fetch_json(f"http://{host}:8032/data/status", timeout=4.0)
    except Exception as e:  # noqa: BLE001
        result["error"] = (result["error"] + "; " if result["error"] else "") + f"Buffer status unreachable: {_describe(e)}"

    result["reachable"] = result["ota"] is not None or result["buffer"] is not None
    result["last_sync_cursor"] = load_cursor(host) or None
    return result


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 — quiet by default
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_html(DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
        elif parsed.path == "/api/tonight":
            self._send_json(_tonight_payload(qs.get("date", [None])[0]))
        elif parsed.path == "/api/trends":
            days = int(qs.get("days", ["14"])[0])
            self._send_json(_trends_payload(days))
        elif parsed.path == "/api/device":
            self._send_json(_device_payload(qs.get("host", [None])[0]))
        elif parsed.path == "/api/nights":
            self._send_json({"nights": [p.stem for p in list_nights()]})
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/sync":
            host = qs.get("host", [None])[0] or _default_host
            if not host:
                self._send_json({"error": "No device host configured"}, status=400)
                return
            try:
                added = sync(host)
            except SyncError as e:
                self._send_json({"error": str(e)}, status=502)
                return
            self._send_json({"added": added})
        else:
            self._send_json({"error": "not found"}, status=404)


def run(port: int = DEFAULT_UI_PORT, host: str | None = None, open_browser: bool = True) -> None:
    global _default_host
    _default_host = host

    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"NightPlug dashboard running at {url}")
    if host:
        print(f"Device: {host} (override per-request with ?host=)")
    else:
        print("No device host set — Device page will show 'not configured' until you pass --host")
    print("Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
