<div align="center">

<img src="custom_components/intex_pool/brand/icon.png" width="88" alt="Intex Pool logo" />

# Intex Pool for Home Assistant

**Your pool readings and controls, together in one adaptive dashboard card.**

Water Analyzer · saltwater system · sand-filter pump<br>
Set up through the Home Assistant UI. YAML is optional.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://www.hacs.xyz/docs/faq/custom_repositories/)
[![Release](https://img.shields.io/github/v/release/Hovborg/intex-pool?style=flat-square&color=0aa2e0)](https://github.com/Hovborg/intex-pool/releases/latest)
[![Tests](https://img.shields.io/github/actions/workflow/status/Hovborg/intex-pool/tests.yaml?style=flat-square&label=tests)](https://github.com/Hovborg/intex-pool/actions/workflows/tests.yaml)
[![HACS validation](https://img.shields.io/github/actions/workflow/status/Hovborg/intex-pool/validate.yaml?style=flat-square&label=HACS)](https://github.com/Hovborg/intex-pool/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/github/license/Hovborg/intex-pool?style=flat-square)](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/card-dark.png" />
  <img src="docs/images/card-light.png" width="476" alt="Intex Pool 0.21.3 with water readings, separate analyzer and saltwater temperatures, and power, chlorine and pump controls" />
</picture>

*The shipped v0.21.3 card, rendered in Home Assistant 2026.9.1 with demo readings.*

[Install](#install-in-five-steps) · [Choose your setup](#choose-your-setup) · [Guides](#guides) · [Get help](#get-help)

[![Open Intex Pool in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hovborg&repository=intex-pool&category=integration)

</div>

## Install in five steps

You need **Home Assistant 2025.8 or newer** and [HACS](https://www.hacs.xyz/docs/use/download/download/).
The current card was browser-tested on **HA 2026.9.1**. Check your equipment in the
[compatibility guide](docs/compatibility.md) before changing its app or connection.

1. **Add the repository.** Use the HACS button above, or open HACS → menu →
   **Custom repositories** and add `https://github.com/Hovborg/intex-pool` as an **Integration** repository.
2. **Download Intex Pool**, then restart Home Assistant.
3. **Add the integration:** Settings → Devices & services → Add integration → **Intex Pool**.
4. **Choose your connection.** Use a [Tuya developer cloud project](docs/tuya-setup.md)
   for a Water Analyzer or device discovery. For an existing pump switch, tick
   **Set up manually instead**, choose **Sand filter pump**, then **Existing Home
   Assistant entity** and select the switch.
5. **Add the card.** Fully reload the browser or Companion App. Edit a customizable
   dashboard → Add card → **Intex Pool**, check the selected entities, and save.

**Already installed?** Update in HACS, restart HA, then fully reload every browser/app
that displays the card. The integration includes the card; it is one download.

The [installation guide](docs/installation.md) includes manual installation,
first-run checks, updates and removal.

## Choose your setup

Configure any supported combination. You do not need all three types of equipment.

| Equipment you have | Connection and requirements | Available functions |
| --- | --- | --- |
| **Water Analyzer** — WA510 / supported AGP sensor | Tuya developer cloud project, linked app account, active API access | pH, ORP, free-chlorine reference, temperature, battery, targets and measurement refresh |
| **Supported Tuya saltwater system** — QS-series | Local LAN with device ID, local key and IP; optional cloud access for schedules | Power, chlorine production, salinity, temperature, self-cleaning, status and alarms |
| **Supported Tuya pump** — for example SX2100 | Local LAN; optional cloud access for schedules | Pump control, device status and available schedule entities |
| **Pump controlled by an existing HA switch** — Shelly, Zigbee relay or another integration | Select that working switch; no Tuya account needed for this path | Manual control, optional power/energy sensors and linked-pump auto mode when a supported saltwater coordinator is present |
| **Non-Wi-Fi chlorinator on a relay** | Select its HA switch in the card after Intex Pool is configured | Manual power control; see [relay setup](docs/dashboard.md#external-pump-and-saltwater-relays) for scope and prerequisites |

**Seeing a device in the official HA Tuya integration does not link it to Intex Pool.**
The two integrations authenticate separately. Follow the [Tuya guide](docs/tuya-setup.md)
for account linking, exact data-center selection and local keys.

## A card that fits your equipment

The card uses the entities available to it. It can show chemistry readings, saltwater
controls, a pump, or a combination. Tap a reading for HA's entity details; use the
buttons for the configured switches and measurement refresh.

![Current card examples: Water Analyzer, analyzer with saltwater system and pump, and linked pump only](docs/images/card-variants.png)

The full card distinguishes **Temp WA** from **Temp salt**. A single temperature
appears as **Temp**. Pump and saltwater schedules have separate headings when present.
Missing or unavailable equipment does not create substitute readings.

### Pick a style

Choose **Variant** in the visual editor: `auto` follows your HA theme; `light`, `dark`,
`ocean` and `midnight` select a fixed appearance.

![The same current card in Dark, Ocean and Midnight styles](docs/images/card-styles.png)

```yaml
type: custom:intex-pool-card
variant: ocean
```

Auto-detection is a starting point. Select your own entities in the editor, especially
if you have more than one pool. The [dashboard guide](docs/dashboard.md) explains every
card option, manual switches, blank fields and YAML examples.

### Dashboard compatibility

The v0.21.3 card was checked in an actual HA 2026.9.1 frontend across:

| Dashboard setup | Checked |
| --- | --- |
| UI-managed and YAML dashboards | Sections, Masonry, Panel and Sidebar |
| Container cards and navigation | Vertical stack, horizontal stack, grid, conditional card and subview |
| Display widths | Desktop 1280 px; mobile 390 px and 320 px |
| Editing and long content | Save/reload, explicit selections and clears, long schedules without overlap |

These checks cover native, customizable Lovelace views. They do not claim support
for every third-party layout or built-in page that cannot host custom cards.
See [dashboard examples](docs/dashboard.md) and the [full verification report](docs/github-issues-2026-09-10.md).

## More than a dashboard

- **Device entities and schedules:** use HA's device pages for targets, maintenance,
  status, available schedule controls and measurement refresh.
- **Linked-pump auto mode:** with a supported local saltwater coordinator, a linked
  pump can follow chlorine production and continue for one hour afterward. See
  [how auto mode behaves](docs/features.md#linked-pump-auto-mode) before enabling it.
- **Calibration and calculated values:** software pH/ORP offsets, pool volume, a salt
  estimate and LSI water-balance indicators are described in the
  [feature guide](docs/features.md). These are informational tools, not automatic dosing.

## Guides

| I want to… | Read this |
| --- | --- |
| Install, update, or remove Intex Pool | [Installation and first-run checks](docs/installation.md) |
| Connect Tuya devices or recover cloud/local access | [Tuya setup and account linking](docs/tuya-setup.md) |
| Add or customize the card, relays, and dashboard layouts | [Dashboard guide and configuration reference](docs/dashboard.md) |
| Use schedules, auto mode, calibration, and calculated entities | [Features and everyday use](docs/features.md) |
| Solve a problem or provide a useful bug report | [Troubleshooting](docs/troubleshooting.md) |

[Supported models and evidence](docs/compatibility.md) ·
[Release notes](CHANGELOG.md) · [Developer guide](CONTRIBUTING.md)

## Get help

Start with [troubleshooting](docs/troubleshooting.md). If the problem persists,
[open an issue](https://github.com/Hovborg/intex-pool/issues/new/choose) with your
HA and Intex Pool versions, device model, connection path and a description of what
you expected. For card problems, include the dashboard layout and card YAML.
Review diagnostics and screenshots for private details before sharing them.

The project is tested with both offline regressions and isolated HA browser checks;
the [compatibility guide](docs/compatibility.md) distinguishes that evidence from
physical-device verification. Support for another model depends on its actual data points.

## License

MIT © Brian Hovborg Mikkelsen. Not affiliated with Intex, AGP or Tuya.
