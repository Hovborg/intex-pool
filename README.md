<div align="center">

<img src="custom_components/intex_pool/brand/icon.png" width="100" alt="Intex Pool logo" />

# Intex Pool for Home Assistant

**A native Home Assistant integration + a compact, adaptive dashboard card for Intex / AGP (Tuya-based) pool equipment.**

Water-quality sensor · saltwater system · any-brand sand-filter pump — set up from the UI, no MQTT, no YAML.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![Release](https://img.shields.io/github/v/release/Hovborg/intex-pool?style=flat-square&color=0aa2e0)](https://github.com/Hovborg/intex-pool/releases)
[![Validate](https://img.shields.io/github/actions/workflow/status/Hovborg/intex-pool/validate.yaml?style=flat-square&label=HACS%20validate)](https://github.com/Hovborg/intex-pool/actions/workflows/validate.yaml)
[![hassfest](https://img.shields.io/github/actions/workflow/status/Hovborg/intex-pool/hassfest.yaml?style=flat-square&label=hassfest)](https://github.com/Hovborg/intex-pool/actions/workflows/hassfest.yaml)
[![License: MIT](https://img.shields.io/github/license/Hovborg/intex-pool?style=flat-square)](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/card-dark.png" />
  <img src="docs/images/card-light.png" width="430" alt="Intex Pool dashboard card" />
</picture>

<br/>

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hovborg&repository=intex-pool&category=integration)

</div>

---

## ✨ Why this exists

Home Assistant's official Tuya integration maps these `rs`-category pool devices to empty
`climate` shells; LocalTuya / tuya-local have no working profile; and the water sensor is
cloud-only. **Intex Pool** talks to each device the way that actually works and gives you
clean, named entities — plus a card that looks good out of the box.

## 🧩 Supported equipment

Pick **any combination** — one, two, or all three:

| | Device | Connection | What you get |
|---|---|---|---|
| 💧 | **Water quality sensor** (AGP Smart Sensor / Water Analyzer) | Tuya cloud | pH, ORP, free chlorine, temp, battery · writable pH/ORP targets · refresh button |
| 🧂 | **Saltwater system** (Intex/AGP QS-series) | Local LAN | Power & chlorine switches, salinity, water temp, self-clean & temp-unit selects, decoded status/alarm/error |
| 🌀 | **Sand-filter pump** | Local Tuya **or any HA switch** | On/off + Tuya timer schedules, or linked power / energy |

> 🔌 **Any brand of pump works.** Not a Tuya device? Link any existing HA switch (Shelly,
> Zigbee relay, …) and it joins the pool card alongside the Intex gear.

> 🔄 **Pump auto mode.** With a linked pump, a **Pump auto mode** switch makes the pump follow
> the saltwater system: it runs while chlorination is on and stops when it's off — no
> automation needed.

<details>
<summary>📋 Full entity reference</summary>

**Water sensor (cloud):** pH, ORP, free chlorine (reference only), water temperature, battery,
**Last measurement** timestamp, pH/ORP/chlorine indicators, **ORP trend**, maintenance,
error code, link status, connectivity, **Measurement schedules** · pH target & ORP target
numbers · reporting-cadence & temperature-unit selects · stabilizer (CYA) flag switch ·
**Refresh measurement** button · **Error** event · pH/ORP calibration-coefficient diagnostics
(disabled by default).

**Saltwater system (local):** power & chlorine-production switches (a second, unverified
"Chlorine production 2" switch ships disabled), salinity, water temperature, cell runtime,
**cell wear**, time remaining, status, **Alarm** (sensor + event), error code, **Cold water**
guard, **Action required** roll-up (with `reasons`), mesh/pump-mesh status, connectivity ·
self-clean & temperature-unit selects · **Re-test now** button · **Schedules** sensor +
per-slot toggle/duration/start-time entities (slot 0 = **Boost**) · **Salt to add** advisor
(enable by setting your pool volume under ⋮ → Configure).

**Pump:** on/off switch (Tuya mode) or your own linked switch + **Pump auto mode** and a
**Pump switch** selector (entity mode), connectivity (Tuya mode).
</details>

> 🧂 **Salt dose advisor.** Set your pool volume (the **Pool volume** entity on the device
> page, or **⋮ → Configure**; litres or US gallons via the **Volume unit** select) and the
> **Salt to add** sensor tells you how many kg reach the target salinity (default 950 ppm,
> the QS-series optimum) — or, above 1800 ppm, how much water to drain per the manual.
> Advisory only; it never actuates anything.

> ⚖️ **LSI water balance.** Enter your latest test-strip/drop-kit results in the
> **Total alkalinity / Calcium hardness / Cyanuric acid (test)** entities and the **LSI**
> sensor computes the Langelier Saturation Index live from the (calibrated) pH and water
> temperature — with a **Water balance** sensor interpreting it (balanced −0.3…+0.3 per
> CDC MAHC; corrosive below, scaling above). For saltwater pools the TDS term
> automatically uses the live salinity. Math follows the published industry tables
> (Taylor watergram / CDC MAHC / Wojtowicz).

> 🧪 **Calibrate against your own test.** Took a strip or drop test? Call
> **`intex_pool.calibrate`** with what it showed (e.g. `parameter: ph`,
> `reference_value: 7.4`) and the pH reading is aligned via a software offset — the raw
> value stays in the `raw_value` attribute. Guardrails reject offsets beyond ±0.5 pH
> (that's clean-and-recalibrate territory), and the offsets auto-reset when you run the
> real buffer calibration in the Intex app. A drop test kit is the recommended reference —
> strips are coarse (±0.3–0.5 pH). The app's buffer-powder calibration every 4 months
> remains the authoritative baseline; this is the drift bridge in between.

## 📸 The card adapts to what you have

It shows only the sections for the equipment you own — chemistry-only, full, or pump-only:

<div align="center">
<img src="docs/images/card-variants.png" width="820" alt="The card adapts: sensor only, all three, pump only" />
</div>

The card is served **by the integration itself** — no separate HACS plugin to install. After
installing or updating through HACS, **restart Home Assistant and fully reload the browser tab
or companion app** so its frontend module is loaded. Then add **“Intex Pool”** from the card
picker; it auto-detects your entities.

If it still does not appear in the picker, first verify that
`/intex_pool/intex-pool-card.js` opens on your Home Assistant host. As a fallback, add that URL
as a **JavaScript module** under **Settings → Dashboards → Resources**, reload the frontend,
and use the YAML card type shown below.

## 🎨 Choose your look

A **`variant`** option lets you pick the style right in the card editor — `auto` (follows your
Home Assistant theme), `light`, `dark`, and two designed dark looks: **ocean** (teal gradient)
and **midnight** (deep indigo):

<div align="center">
<img src="docs/images/card-styles.png" width="860" alt="Dark style variants: dark, ocean, midnight" />
</div>

```yaml
type: custom:intex-pool-card
variant: ocean   # auto | light | dark | ocean | midnight
```

## 🗓️ Schedules

The saltwater system's built-in schedules live only in the cloud as an encoded blob, so they're
normally invisible. This integration **decodes them**: a read-only **Schedules** sensor shows
how many are active and lists each (daily/one-time, time, duration, on/boost). Each slot also gets
its own **toggle**, **duration** and **start-time** entities under the device, so you can turn a
schedule on/off and retune it without the service call.

> **Slot 0 = Boost.** The first slot is the device's **Boost** cycle. It runs for a set number of
> hours rather than at a clock time (the app ignores a start time for it), so it's exposed as
> **Boost** + **Boost duration** only — no start-time entity. Turning **Boost on suspends your
> timed schedules** (they're remembered, then restored when Boost is turned off) — mirroring how
> the unit reverts to its normal schedule after a boost completes, and confirmed against the
> device's Tuya thing-model (`working_indicator` reports `boost`).

You can also **edit** any slot from HA with the **`intex_pool.set_schedule`** service (writes back via the cloud):

```yaml
service: intex_pool.set_schedule
data:
  slot: 4          # 0–6
  enable: true     # off behaves like the boost cycle
  hour: 22
  minute: 0
  duration: 2
  days: 255        # 255 = every day, 0 = one-time (then set month/date)
```

> Schedules are cloud-only. Cloud discovery keeps the credentials for a pump-only or
> saltwater-only setup; manual local setup still controls the device but has no schedules.
> Use **Reconfigure** and enter Tuya cloud credentials to enable them. The byte format
> round-trips exactly; the exact units of duration/days are best-effort.

## 🚀 Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hovborg&repository=intex-pool&category=integration)

1. Click the button above (or HACS → ⋮ → **Custom repositories** → `https://github.com/Hovborg/intex-pool`, category **Integration**).
2. Download **Intex Pool** in HACS and **restart Home Assistant**.
3. **Settings → Devices & Services → Add Integration → Intex Pool**.
4. Enter your Tuya cloud credentials and pick your devices (see below).

## ⚙️ Setup — the easy way (cloud auto-discovery)

You only need **Tuya IoT developer-cloud credentials** once: a free project at
[iot.tuya.com](https://iot.tuya.com) (region, Access ID, Access secret) with your Smart
Life / Tuya app account linked. Enter those and the integration will:

- 🔑 **fetch your devices and their local keys automatically** (no `tinytuya wizard`), and
- 📡 **scan your network for their IPs + protocol version automatically** (no IP typing).

Then pick the discovered **saltwater system**, **water sensor** and/or **Tuya pump** you own.
Alternatively, link any existing Home Assistant switch as your sand-filter pump.

> 🔁 The water sensor sleeps and reports about once an hour — tap **Refresh measurement** to
> force a fresh reading.

<details>
<summary>🔧 Manual setup (fallback, no cloud)</summary>

Tick **“set up manually”** in the first step and enter each device's **device id**, **local
key** and **IP** by hand (get them with [tinytuya](https://github.com/jasonacox/tinytuya)).
Protocol version can be left on **auto**. Note: local devices still need their local key,
which for these `rs` devices ultimately comes from the Tuya cloud — so the cloud path is
usually simplest.
</details>

## 🔧 Keeping it running

Pools get re-paired and gear gets replaced — both are handled from the UI, with no need to
delete and re-add the integration:

- 🔑 **Local key changed?** Re-pairing a device in the Tuya / Smart Life app rotates its
  **local key**, which breaks the local connection (saltwater system or a Tuya pump). Home
  Assistant then starts **re-authentication** automatically — just type the new local key
  (and, for the cloud sensor, the access secret). Each local device has its own key field,
  so any combination works.
- 🔁 **Replaced a device?** When you swap a physical unit, the new one gets a new Tuya id.
  Open **Settings → Devices & Services → Intex Pool → ⋮ → Reconfigure** to re-run discovery
  and pick the new device. The existing entry is updated **in place** — your entity ids and
  history are kept, and unchanged devices keep their stored IP/key (no re-scan needed). The
  old device can then be deleted from its device page.
- ⏱️ **Polling intervals** are tunable under **⋮ → Configure** (local default 15 s, cloud
  default 120 s — well inside the Tuya free-tier API quota).

## 🩺 Troubleshooting

- 🚨 **Repairs**: actionable problems show up in **Settings → Repairs** — saltwater alarms
  (low flow E90, salt out of range E91/E92, electrode/temperature faults, …) with the
  manual's fix steps, a **maintenance** reminder when the sensor probes need cleaning or
  calibration, and a **stale data** warning when the sensor (which reports ~1×/hour) hasn't
  measured for hours.
- 📄 **Diagnostics**: the integration page's **Download diagnostics** includes the raw device
  data for bug reports — local keys and cloud credentials are redacted automatically.
- ⏰ **Alarm/error events**: `event.…_alarm` and `event.…_error` fire on every transition, so
  you can build notifications without templating against the enum sensors.
- ☁️ **Tuya cloud trial expired?** The free IoT Core trial eventually lapses; renew it for
  free at [iot.tuya.com](https://iot.tuya.com) → Cloud → your project → **View Details** →
  extend trial. The integration surfaces auth failures as a re-authentication prompt.
- 📉 **No measurement-history backfill**: Tuya's device-log APIs do not return data-point
  report history on the free IoT Core tier (verified live — only online/offline events come
  back), so readings taken while Home Assistant was down cannot be recovered. History
  accumulates normally in HA's own recorder while it runs.

<details>
<summary>🗑️ Removing the integration</summary>

**Settings → Devices & Services → Intex Pool → ⋮ → Delete.** This removes the entry, its
devices and entities. To finish the cleanup, remove the HACS download (HACS → Intex Pool →
remove) and restart Home Assistant. Nothing is left on the devices themselves — they keep
working in the Intex Link / Smart Life app.
</details>

## 🧪 Compatibility

Built and **live-verified** against the **AGP / Intex QS-series saltwater chlorinator**
(QS1600 Plus) and the **AGP Smart Sensor / Water Analyzer (WA510 and T3U)**. Other Intex/Tuya pool models connect the
same way, but their data-point numbering may differ — some entities could be missing or
wrong. Have a different model? [Open an issue](https://github.com/Hovborg/intex-pool/issues)
with your device's data points and it can be added. The sand-filter pump works with **any**
brand via the “existing switch” link.

## 🛠️ Development

```bash
# Python tests (Home Assistant integration)
pip install pytest-homeassistant-custom-component tinytuya
pytest -q

# Dashboard card (Lit + esbuild)
cd card && npm install && npm run build   # -> custom_components/intex_pool/frontend/intex-pool-card.js
```

## 📄 License

MIT © Brian Hovborg Mikkelsen — not affiliated with Intex or AGP.
