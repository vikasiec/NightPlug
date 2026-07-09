# NightPlug

**Contactless sleep clinic in a plug.**

NightPlug sits by your bed (ESP32-S3 on USB power) and turns WiFi radio reflections into a morning sleep report — no watch, no camera, no cloud required.

> Wellness / personal screening only. **Not a medical device.** Not a clinical sleep study (no EEG). Apnea-like flags are heuristic hints, not a diagnosis.

## Status

| Phase | What | Status |
|-------|------|--------|
| **Now** | Simulator + session engine + morning HTML report | ✅ Ready |
| **22 July+** | Wire real ESP32-S3 CSI (RuView-compatible) | Planned |
| Later | Always-on host, phone glance, multi-night trends | Planned |

## Project path & GitHub

| | |
|--|--|
| **Local** | `C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug` |
| **GitHub** | https://github.com/vikasiec/NightPlug |
| **Agent rules** | See [`AGENTS.md`](AGENTS.md) — all future work on this product stays in this repo |

```
C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug
```

## Quick start (no hardware)

```powershell
cd "C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m nightplug simulate --hours 8 --seed 42
python -m nightplug report --latest
```

Open the generated file under `reports/`.

### CLI

```powershell
python -m nightplug simulate              # full synthetic night → data/nights/
python -m nightplug simulate --profile restless
python -m nightplug report --latest       # build HTML from newest night
python -m nightplug report --date 2026-07-09
python -m nightplug demo                  # simulate + report in one step
python -m nightplug status                # show data/report paths
```

## How it works

```
[ESP32 by bed] ──CSI/features──► [logger JSONL] ──► [session + scoring] ──► [morning HTML]
       ▲                              ▲
   (July 22+)                    (simulator today)
```

1. **Samples** — one row per second: presence, motion, breathing rate, signal quality  
2. **Session state machine** — empty → in_bed → sleep_like → restless → awake_in_bed → up  
3. **Scoring** — transparent rules (not a black-box ML grade)  
4. **Report** — hours in bed, restless minutes, breathing stats, event candidates, score + reasons  

## Hardware (when board arrives ~22 July)

| Item | Role |
|------|------|
| ESP32-S3 (N16R8) | Bedside RF sensor |
| USB wall adapter + data cable | “In a plug” power |
| This PC (or later a Pi) | Logging + report |
| Home Wi‑Fi | Same network as PC |

**Placement:** nightstand, ~1–2 m from mattress, not buried in metal.

Integration will reuse RuView CSI firmware / sensing pipeline from:

`C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\RuView`

## Folder layout

```
NightPlug/
├── src/nightplug/          # application package
│   ├── cli.py              # command entry
│   ├── config.py           # paths & thresholds
│   ├── models.py           # sample / night summary types
│   ├── session.py          # sleep state machine
│   ├── features.py         # rolling feature helpers
│   ├── scoring.py          # transparent sleep score
│   ├── logger.py           # JSONL night logs
│   ├── simulate.py         # synthetic overnight generator
│   └── report.py           # HTML morning report
├── data/nights/            # YYYY-MM-DD.jsonl logs
├── reports/                # morning HTML reports
├── templates/              # report HTML shell
├── scripts/                # helper scripts
├── pyproject.toml
└── README.md
```

## Privacy

- Local files only by default  
- No cloud upload  
- Logs stay under `data/nights/` on your machine  

## License

Personal project — MIT if you open-source later.
