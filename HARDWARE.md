# NightPlug hardware notes

## Ordered

| Item | Detail |
|------|--------|
| Board | ESP32-S3 DevKit-style **N16R8** (16 MB flash, 8 MB PSRAM) |
| ETA | **2026-07-22** |
| Purpose | Bedside CSI node for contactless sleep sensing |

## Also needed

- USB **data** cable (not charge-only)
- USB wall adapter (the “plug”)
- Home Wi‑Fi + this PC on the same network

## After arrival

1. Install USB serial driver (CP210x or CH340 — check the board)
2. Flash RuView `esp32-csi-node` firmware (from sibling `RuView` repo)
3. Provision Wi‑Fi + PC IP as sensing sink
4. Point NightPlug ingest at the live feature stream (adapter TBD in `src/nightplug/`)

## Placement

- Nightstand, 1–2 m from mattress
- Avoid metal enclosures
- Same room as sleeper

## Software bridge (planned)

```
ESP32 CSI → RuView sensing server / UDP → nightplug ingest → JSONL → report
```

Until then, use:

```powershell
python -m nightplug demo
```
