# Contributing

Thanks for helping improve **Intex Pool**! This is a Home Assistant custom integration
for Intex / Tuya-based pool equipment.

## Development setup

```bash
# Python (HA test stack). Python 3.13.
python -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.13
pip install pytest-homeassistant-custom-component "tinytuya==1.20.0" ruff

# Run the tests + linter
pytest -q
ruff check custom_components tests
```

## The Lovelace card

The card lives in `card/src/` and is bundled (esbuild) into
`custom_components/intex_pool/frontend/intex-pool-card.js`, which **is committed**
(HACS ships the repo as-is). If you change `card/src/`, rebuild and commit the bundle:

```bash
cd card && npm ci && npm test && npm run build
```

CI fails if the committed bundle is out of date (`git diff --exit-code`).

## Versioning

The version lives in the integration manifest, `pyproject.toml`, `card/package.json`,
the npm lockfile and the built card banner. Run `python scripts/verify_release.py` to
check all of them after rebuilding. Add a `CHANGELOG.md` entry for every release
(Keep a Changelog format).

## Adding a new device model

Open an issue with your device's data points (Home Assistant diagnostics, a
`tinytuya` dump or the Tuya thing-model) and follow
[`docs/compatibility.md`](docs/compatibility.md). **Redact the local key, device id,
IP, access id, cloud secret and request signatures first.** State whether each
claim was verified on physical hardware, read from a thing model, or inferred.
Device data-point maps go in `const.py`.

When changing the TinyTuya version, run the complete offline suite first and then
verify local polling, one controlled write and cloud schedule readback on physical
SX/QS hardware before changing any datapoint or schedule semantics.

## Pull requests

Run the tests + ruff, rebuild the card if you touched it, bump the version, and add
a changelog entry. The PR template lists the checklist.
