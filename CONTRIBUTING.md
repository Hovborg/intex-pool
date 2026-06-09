# Contributing

Thanks for helping improve **Intex Pool**! This is a Home Assistant custom integration
for Intex / Tuya-based pool equipment.

## Development setup

```bash
# Python (HA test stack). Python 3.13.
python -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.13
pip install pytest-homeassistant-custom-component "tinytuya==1.18.1" ruff

# Run the tests + linter
pytest -q
ruff check custom_components tests
```

## The Lovelace card

The card lives in `card/src/` and is bundled (esbuild) into
`custom_components/intex_pool/frontend/intex-pool-card.js`, which **is committed**
(HACS ships the repo as-is). If you change `card/src/`, rebuild and commit the bundle:

```bash
cd card && npm ci && npm run build
```

CI fails if the committed bundle is out of date (`git diff --exit-code`).

## Versioning

The version lives in **three** files that must stay in sync:
`custom_components/intex_pool/manifest.json`, `pyproject.toml`, and `card/package.json`.
The card injects its version from `card/package.json` at build time. Add a
`CHANGELOG.md` entry for every release (Keep a Changelog format).

## Adding a new device model

Open an issue with your device's data points (a `tinytuya` dump or the Tuya
thing-model) — **redact the local key and cloud secret first**. Device data-point
maps go in `const.py`.

## Pull requests

Run the tests + ruff, rebuild the card if you touched it, bump the version, and add
a changelog entry. The PR template lists the checklist.
