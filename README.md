# Intex Pool for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/Hovborg/intex-pool/actions/workflows/validate.yaml/badge.svg)](https://github.com/Hovborg/intex-pool/actions/workflows/validate.yaml)
[![hassfest](https://github.com/Hovborg/intex-pool/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/Hovborg/intex-pool/actions/workflows/hassfest.yaml)

A native Home Assistant integration for **Intex / AGP (Tuya-based) pool equipment**, plus a
dedicated, adaptive dashboard card. Set it up from the UI — no MQTT broker, no YAML, no
separate service.

The official Tuya integration maps these `rs`-category pool devices to empty `climate`
shells; LocalTuya/tuya-local have no working profile, and the water sensor is cloud-only.
This integration talks to each device the way that actually works and exposes clean,
named entities.

## Supported equipment

Pick **any combination** — one, two, or all three:

| Device | How it connects | What you get |
|---|---|---|
| 💧 **Water quality sensor** (AGP Smart Sensor / Intex Water Analyzer) | Tuya developer cloud | pH, ORP, free chlorine, water temp, battery; writable pH/ORP targets; force-refresh button |
| 🧂 **Saltwater system** (Intex/AGP QS-series, e.g. QS1600 Plus) | Local LAN (tinytuya) | Power & chlorine-production switches, salinity, water temp, self-clean cycle, runtime, decoded status/alarm/error |
| 🌀 **Sand filter pump** | Local Tuya **or any existing HA switch** | On/off + (when linked) power/energy/water-temp |

> **Any brand of pump works.** If your pump isn't a Tuya/Intex device (e.g. a Shelly plug,
> a Zigbee relay, or any other smart switch), choose **"Existing Home Assistant entity"** in
> setup and link its switch + optional sensors. It then appears in the pool card and works
> alongside the Intex devices.

## The dashboard card

The integration ships its own Lovelace card (`custom:intex-pool-card`) — it loads
automatically, no separate install. It **adapts** to the equipment you have: it shows a
chemistry section (pH/ORP/temperature gauges), a chlorinator section (big toggles, salinity,
status), and a pump section — hiding whatever you don't have. Add it from the card picker
("Intex Pool") and it auto-detects your entities.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/Hovborg/intex-pool`, category **Integration**.
2. Search for **Intex Pool** in HACS, download it, and restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Intex Pool**.
4. Tick the devices you have and fill in the details for each (see below).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hovborg&repository=intex-pool&category=integration)

## Getting the device details

**Local devices (saltwater system, Tuya pump)** need a Tuya **device id**, **local key**, and
**IP address**. Get them with [tinytuya](https://github.com/jasonacox/tinytuya)
(`python -m tinytuya wizard`) or the Tuya IoT platform. Protocol version can be left on
**auto**.

**Water sensor (cloud)** needs Tuya **IoT developer-cloud** credentials (region, Access ID,
Access secret) from a project at [iot.tuya.com](https://iot.tuya.com) that your app account
is linked to, plus the sensor's device id. The sensor sleeps and reports about once an hour;
use the **Refresh measurement** button to force a fresh reading.

## Options

After setup, **Configure** lets you tune the local and cloud polling intervals.

## Notes & limitations

- The water sensor's free-chlorine value is **calculated from ORP+pH** by the device and is
  "for reference only" — confirm with a test strip. High cyanuric acid (CYA) skews ORP.
- ORP requires a working probe; a stuck reading usually means the probe needs service.
- This is a community project, not affiliated with Intex or AGP.

## Development

```bash
# Python tests (HA integration)
pip install pytest-homeassistant-custom-component tinytuya
pytest -q

# Card (Lit + esbuild)
cd card && npm install && npm run build
```

## License

MIT © Brian Hovborg Mikkelsen
