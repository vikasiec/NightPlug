# NightPlug hardware notes

## Ordered

| Item | Detail |
|------|--------|
| Board | ESP32-S3 DevKit-style **N16R8** (16 MB flash, 8 MB PSRAM), OceanLabz |
| ETA | ~~2026-07-22~~ arrived early — **received 2026-07-16** |
| Purpose | Bedside CSI node for contactless sleep sensing |

## Board facts (from OceanLabz card + silkscreen)

- Module: ESP32-S3 WROOM-1-N16R8, 2.4 GHz antenna
- CPU: dual-core Xtensa LX7 @ 240 MHz; 16 MB flash + 8 MB PSRAM
- Wireless: WiFi 802.11 b/g/n + Bluetooth 5 (LE)
- Programming: Arduino, MicroPython, ESP-IDF
- **Two USB-C ports** — silkscreen/diagram labels them "ESP32-S3 Direct Type-C, USB & OTG" (left) vs. "USB to Serial C-Type / CH343P" (right), but **empirically only the left port has been confirmed working** on this unit (see below) — treat the diagram's left/right guidance with caution, verify which is live per-session with the PowerShell check below rather than assuming.
- The **left port** enumerates as Windows "USB Serial Device", `VID_303A&PID_4001` (Espressif's own VID — this is the ESP32-S3's **built-in native USB-Serial/JTAG peripheral in silicon**, not the CH343P chip). No CH343SER driver needed for this path — Windows' inbox USB CDC driver handles it.
- The right/CH343P port was never confirmed enumerating in testing (2 cables, 2 laptop ports, driver installed, zero PnP events) — may be a dead solder joint on this specific board, or we were consistently testing the wrong physical port due to orientation confusion. Unconfirmed either way — don't assume it works.
- CH343SER driver from WCH (`https://www.wch.cn/downloads/CH343SER_EXE.html`) was installed as part of troubleshooting but turned out to be unnecessary for the working path — keep it installed in case the right port is used later.
- Other markings: Power chip, Integrated RGB LED (WS2812), RST button, BOOT button, PWR/TX/RX LEDs

## Preloaded test firmware (as shipped)

- Board ships with OceanLabz test firmware already flashed
- It hosts a WiFi AP: **SSID `OL-ESP32-AP`**, **password `12345678`**
- Useful as a sanity check that the board itself boots, independent of USB/serial

## Also needed

- USB **data** cable (not charge-only) — many bundled cables are charge-only and will show zero enumeration
- USB wall adapter (the “plug”)
- Home Wi‑Fi + this PC on the same network

## Connecting via Arduino IDE (2.3.10+)

1. Install the **CH343SER** driver (see above) — Windows has no inbox driver for this chip
2. File → Preferences → Additional Boards Manager URLs → add:
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
3. Tools → Board → Boards Manager → install **esp32 by Espressif Systems**
4. Plug into the **left** (native USB-OTG) port with a **Type-C to Type-C** cable, direct into a laptop port (no hub) — this is the port confirmed working on this unit
5. Tools → Port — a new `COM#` should appear. **Verify it's the real board**, not a pre-existing Bluetooth virtual COM port (e.g. this machine already has `COM3`/`COM4` as "Standard Serial over Bluetooth link" before the board is ever plugged in — don't mistake those for the ESP32). Confirmed board identity via Tools → Get Board Info: **VID `0x303A` (Espressif), PID `0x4001`, SN `123456`** — shows as "Unknown board" in the IDE, that's fine, VID/PID confirms it's genuine.
6. Select board: **ESP32S3 Dev Module**
7. The COM number is **not stable** — it can change (COM5 → COM7 etc.) each time the board is unplugged/replugged. Always re-check Tools → Port before uploading.

### Resolved: board not detected (root cause was the cable)

On this unit, a **Type-A→Type-C cable would not enumerate at all**, even confirmed "data" cables that worked for phone sync — zero USB events in Windows PnP logs across 2 cables and 2 laptop ports. Switching to a **Type-C→Type-C cable** fixed it immediately. **If the board isn't detected, try a C-to-C cable before suspecting the board or driver.**

General diagnosis, if it happens again:

- Confirm via PowerShell that a *new* device actually enumerates:
  `Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq 'Ports' }` — compare against the baseline Bluetooth-only COM ports before plugging in
  `pnputil /enum-devices /connected /class USB` — look for a new `USB\VID_303A&PID_4001` entry
  `Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Kernel-PnP/Configuration'; StartTime=(Get-Date).AddMinutes(-5)}` — should show connect/disconnect activity the moment you plug in; if this stays empty across multiple cable/port combos, it's an electrical/hardware issue, not a driver one
- Try a **Type-C to Type-C cable first** (this fixed it for us), a different laptop USB port (no hub), and if still nothing, test the board on a different PC/phone to isolate board vs. this laptop

### Uploading: auto-reset isn't wired — manual BOOT hold required

Every upload fails with `Failed to connect to ESP32-S3: No serial data received` unless you manually force bootloader mode, because this board's CH343P DTR/RTS aren't wired to auto-trigger BOOT/EN:

1. **Press and hold BOOT** first — before clicking Upload
2. **While still holding BOOT**, click **Upload** in Arduino IDE
3. **Keep holding BOOT** through the whole "Connecting......." phase
4. Release BOOT once it starts writing (or clearly fails)

If it still fails with BOOT held throughout, try dropping Tools → Upload Speed to `115200` (default is often 921600).

## After it enumerates

1. ~~Install USB serial driver (CP210x or CH340 — check the board)~~ → CH343SER (see above) — **done, working (2026-07-16)**
2. Flash RuView `esp32-csi-node` firmware (from sibling `RuView` repo) — **done, v0.6.7 flashed 2026-07-16** via:
   ```
   python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
     write_flash --flash_mode dio --flash_size 16MB \
     0x0     firmware/esp32-csi-node/release_bins/bootloader.bin \
     0x8000  firmware/esp32-csi-node/release_bins/partition-table.bin \
     0xf000  firmware/esp32-csi-node/release_bins/ota_data_initial.bin \
     0x20000 firmware/esp32-csi-node/release_bins/esp32-csi-node.bin
   ```
   (needs `pip install esptool`; no BOOT-hold needed here — esptool resets via the native USB-Serial/JTAG mode automatically)
3. Provision Wi-Fi + PC IP as sensing sink — **done**, via:
   ```
   python firmware/esp32-csi-node/provision.py --port COM7 \
     --ssid "Airtel_Vikas_Home" --password "<redacted>" --target-ip 192.168.1.9
   ```
   (needs `pip install esp-idf-nvs-partition-gen`). **Important: the ESP32-S3 is 2.4GHz-only** — provision it against your router's 2.4GHz SSID, not a `_5ghz` one, or it will never associate.
4. Point NightPlug ingest at the live feature stream — **done**: `python -m nightplug live --minutes N` (see `src/nightplug/ingest.py`, `src/nightplug/cli.py`). Listens on UDP 5005, parses the board's actual on-wire packet — **ADR-081 `rv_feature_state_t`, magic `0xC5110006`, 60 bytes** (not the older ADR-039 vitals packet documented in the RuView README as primary; that's now a fallback the firmware may not even send). Writes real Samples to `data/nights/*.jsonl`, same format the simulator produces, so `nightplug report` works unmodified on real data.

### Resolved: CSI yield stuck at 0pps (fixed 2026-07-17)

Board connected to WiFi fine (confirmed via serial log, RSSI ~-60dBm, UDP packets arriving at the target IP), but `presence`/`motion`/`respiration_bpm` all read constantly 0 because the underlying CSI engine mostly wasn't firing (`adaptive_ctrl: medium tick: ... yield=0pps` nearly always, serial-log-confirmed over multiple minutes).

Root-caused via source read of `firmware/esp32-csi-node/main/csi_collector.c`: the firmware relies on a "self-ping" mechanism (RuView issues #521/#954) — pinging the router at 50Hz to guarantee a steady stream of OFDM reply frames that trigger the CSI callback, since ambient network traffic alone is too sparse. The self-ping session was dying shortly after WiFi reconnect (esp_ping sessions can terminate on transient errors like ARP failure even with `COUNT_INFINITE`) and the old no-op callbacks meant nothing restarted it — CSI yield dropped to 0 and stayed there.

**Fix:** `csi_collector.c`'s `on_ping_end` callback now clears `s_self_ping`, so `csi_start_self_ping()` spins up a fresh session on the next tick instead of leaving a dead one in place. Committed in the sibling `RuView` repo (`aa8e2e59`, "fix(csi): restart self-ping session on end instead of going silent").

**Build/flash notes for next time:** the README's documented Docker build command uses `espressif/idf:v5.2`, but that's stale — it fails with `Failed to resolve component 'esp_driver_uart'`. Use `espressif/idf:v5.4` (matches `.github/workflows/firmware-ci.yml`) instead:
```
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd)/firmware/esp32-csi-node:/project" -w /project \
  espressif/idf:v5.4 bash -c \
  "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
```

**Confirmed on hardware (2026-07-17):** after reflashing, CSI yield sustained ~29-34pps over a 90-second serial capture (previously dropped to 0pps within seconds), `presence`/`motion`/`breathing_bpm` all read live non-zero values, and `python -m nightplug live` wrote 47 real Samples end-to-end to `data/nights/2026-07-17.jsonl`.

## Local flash buffer + offline resilience (added 2026-07-17)

The board previously sent sensing output over fire-and-forget UDP with no local storage — if the PC wasn't running `nightplug live` at that exact moment, the reading was lost forever. Since the PC won't be on 24/7, this meant most of every night was silently dropped.

Fixed by adding a flash-backed ring buffer on the board itself (`firmware/esp32-csi-node/main/sample_buffer.c`, RuView repo) — persists readings on the previously-unused `spiffs` partition, independent of whether the live UDP send succeeds. A local HTTP API on the existing OTA server (port 8032) exposes it:

- `GET http://<esp32-ip>:8032/data/status` — buffer coverage summary
- `GET http://<esp32-ip>:8032/data/pull?since=<unix_s>&limit=<n>` — pull buffered records

On the PC side, `python -m nightplug sync --host <esp32-ip>` pulls whatever was buffered while nothing was listening and merges it into the right night's file, deduping against anything `live` already captured. Run it any time the PC comes back online — no need to have `live` running continuously.

**Capacity:** ~17.6 hours (`spiffs` partition extended 2026-07-17 from 0x1E0000 to 0x3E0000, claiming previously-unallocated space in the 8MB partition table — up from the initial ~8.6h). Older data is overwritten once full (ring buffer, not a log). A further ~2x is available by expanding into the board's unused second 8MB of physical flash (it's a 16MB chip but only 8MB is currently declared/partitioned) — not done yet, would need more careful partition-table surgery.

**Known limits:** the local HTTP API has no authentication (same LAN-trust posture as the existing OTA endpoint — fine for a home network, a gap to close before shipping to anyone else). Requires the 8MB partition table; not available on 4MB boards (no spare partition).

Board's IP can change if your router doesn't reserve it — find it via `arp -a` (search for MAC `d4:05:92:79:93:b0`) or your router's DHCP client list if `sync` can't connect.

## Local dashboard + experimental heart rate (added 2026-07-17)

`python -m nightplug ui [--host <esp32-ip>]` launches a local web dashboard (stdlib `http.server`, no new dependency) with three pages:

- **Tonight** — interactive version of the old static report: score, key metrics, motion/breathing charts, state timeline, "why this score."
- **Trends** — score and breathing-rate history across nights, plus which nights needed `sync` to fill a gap. Net-new; nothing in the project showed multi-night history before this.
- **Device** — buffer coverage, firmware version, a "Sync now" button. Only shows fields actually queryable over the device's HTTP API (`/ota/status`, `/data/status`) — no fabricated RSSI/uptime/CSI-yield, since those aren't exposed there (serial-log-only today).

**Experimental heart rate**: the on-wire packet (`rv_feature_state_t`) always carried `heartbeat_bpm`/`heartbeat_conf`, but both the live-UDP parser and the buffer/sync path were silently discarding them. Now surfaced on the Tonight page with a visible "EXPERIMENTAL" badge and deliberately excluded from the sleep score — the firmware's `heartbeat_conf` is a binary plausible-range check (not a real confidence score), and this board has no mmWave hardware, so CSI-only heart rate is known to be far less reliable than presence/motion/breathing.

## Future: mmWave hardware upgrade for real heart rate / HRV (researched, not purchased — 2026-07-17)

Investigated what it would take to get reliable heart rate (and eventually HRV/stress, like RuView's `examples/medical/vitals_suite.py` and `examples/stress/hrv_stress_monitor.py`) instead of the CSI-only experimental estimate above.

**Key finding: the firmware already fully supports this, unused.** `firmware/esp32-csi-node/main/mmwave_sensor.c`/`.h` (RuView repo) has a complete driver for Seeed's MR60BHA2 (60GHz, heart rate + breathing + presence) with auto-detection on boot — and `edge_processing.c` already has fusion logic wired in: the moment the firmware detects an mmWave sensor on the UART, it automatically switches to sending fused vitals using the mmWave's reading instead of the CSI-only estimate. This was built by RuView's team but never populated with real hardware on our board. A cheaper presence-only alternative (HLK-LD2410, 24GHz, no vitals) is also already supported.

**Cost:** Seeed MR60BHA2 sensor kit (bundled with its own XIAO ESP32C6 MCU, which we wouldn't need) is **$22.90–24.90** ([Seeed Studio](https://www.seeedstudio.com/MR60BHA2-60GHz-mmWave-Sensor-Breathing-and-Heartbeat-Module-p-5945.html), [Mouser](https://www.mouser.com/new/seeed-studio/seeed-studio-mr60bha2-sensor-kit/)). The bare module (predecessor MR60BHA1, same UART protocol, 5V, ~85-90% claimed accuracy per Seeed's own specs — [bare module listing](https://www.seeedstudio.com/60GHz-mmWave-Radar-Sensor-Breathing-and-Heartbeat-Module-p-5305.html)) is the right part to wire directly into the ESP32-S3's UART instead of using its bundled MCU — realistic estimate **$15–30** including shipping either way.

**Effort:** roughly an hour — wire 4 wires (VCC, GND, TX, RX) to a free UART on the ESP32-S3 (verify 3.3V vs 5V logic-level compatibility before connecting), flash the existing firmware as-is (no code changes needed, auto-detects at boot), mount near the bed alongside the existing board.

**Not done yet** — revisit once the current local-buffer + dashboard work has proven itself over a few real nights.

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
