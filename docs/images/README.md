# Documentation image provenance

[Project overview](../../README.md) · [Capture instructions](../../scripts/browser/README.md#documentation-images)

The card gallery was regenerated on **2026-09-10** from the actual shipped
**Intex Pool v0.21.3** JavaScript bundle, inside **Home Assistant 2026.9.1**
(frontend **20260826.6**) in an isolated local test installation.

All values, entity names and schedules in the card gallery are **synthetic demo data**.
They are not measurements from the maintainer's pool or another user's equipment.
Captions are outside the card; the card markup, icons, layout and styles come from
the shipped component. The gallery does not replace physical-device verification.

| Images | What they show |
| --- | --- |
| `card-light.png`, `card-dark.png`, `card-ocean.png`, `card-midnight.png` | The full card in each fixed appearance |
| `card-variants.png` | Water Analyzer only, all equipment and linked pump only |
| `card-styles.png` | Dark, Ocean and Midnight compared |
| `card-mobile.png` | The full card wrapping in a 360-pixel preview |
| `card-schedules.png` | Separate saltwater and pump schedule summaries |
| `setup-cloud.png` | Actual integration setup with blank credentials |
| `setup-equipment.png`, `setup-pump-type.png`, `setup-pump-entity.png` | Actual manual linked-pump setup steps |
| `card-editor.png` | The actual HA visual editor using fixture switches |

The setup/editor captures use the same isolated HA installation. They contain no
real Tuya credentials. Setup is cancelled before creating a new device entry.

Reproduce the images using the two scripts documented in the
[browser guide](../../scripts/browser/README.md#documentation-images), then inspect
the PNGs and the rendered README before committing them.
