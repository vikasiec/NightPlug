# NightPlug — Agent / AI working rules

This file is the **source of truth** for any agent (Grok, Claude, Codex, etc.) working on this project.

## Project identity

| Field | Value |
|-------|--------|
| **Name** | NightPlug |
| **One-liner** | Contactless sleep clinic in a plug — bedside RF sleep reports, no watch/camera |
| **Local path** | `C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug` |
| **GitHub** | https://github.com/vikasiec/NightPlug |
| **Remote** | `origin` → `https://github.com/vikasiec/NightPlug.git` |
| **Default branch** | `main` |
| **Owner** | vikasiec (Vikas Sharma) |

## Always do this

1. **Work only inside this folder** for NightPlug features. Do not put NightPlug code into sibling projects (`RuView`, `Financial Planner`, etc.).
2. **Git remote is fixed:** `https://github.com/vikasiec/NightPlug.git`. Push/PR only to this repo.
3. **Before committing:** run relevant CLI checks (`python -m nightplug demo` or report on a sample night) when behavior changes.
4. **Commits:** use conventional, clear messages. Never force-push `main` unless the user explicitly asks.
5. **Privacy:** night logs under `data/nights/` are personal — keep them gitignored; never commit real sleep data or secrets.

## Related repos (reference only)

| Repo | Path | Use |
|------|------|-----|
| RuView | `...\Projects\RuView` | CSI firmware / sensing ideas for ESP32 bridge later |
| — | — | Do **not** merge RuView into this repo wholesale |

## Hardware (user context)

| Item | Detail |
|------|--------|
| Board | ESP32-S3 DevKit-style **N16R8** (~₹999 path; not the ₹4900 official N32R8V) |
| ETA | **2026-07-22** |
| Extra needed | USB data cable + wall adapter; home Wi‑Fi + PC |
| Post-arrival | Flash CSI node (RuView firmware), provision Wi‑Fi, wire ingest into NightPlug sample schema |

Until hardware arrives: develop with **simulator** (`python -m nightplug simulate` / `demo`).

## Product rules

- Personal wellness / screening — **not a medical device**. No diagnosis claims.
- Apnea-like events are **heuristics**, labeled as such in UI and copy.
- Local-first: no cloud required by default.
- Prefer transparent scoring (explainable penalties) over black-box grades.

## Commands (Windows)

```powershell
cd "C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug"
.\.venv\Scripts\Activate.ps1   # if venv exists
pip install -e .
python -m nightplug status
python -m nightplug demo
python -m nightplug report --latest
```

### Git push pattern

```powershell
cd "C:\Users\Vikas Sharma\OneDrive\Documents\Claude\Projects\NightPlug"
git status
git add <files>
git commit -m "message"
git push origin main
```

## Layout (do not scramble without reason)

```
NightPlug/
├── AGENTS.md                 ← this file
├── README.md
├── HARDWARE.md
├── src/nightplug/            ← application package
├── data/nights/              ← JSONL logs (gitignored content)
├── reports/                  ← HTML reports (gitignored content)
├── scripts/
└── pyproject.toml
```

## Out of scope unless user asks

- Full RuView platform port
- Clinical certification / medical marketing
- Force-push, secrets in repo, committing `.venv`
