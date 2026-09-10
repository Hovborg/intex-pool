# Contributing

Thanks for helping improve **Intex Pool**! This is a Home Assistant custom integration
for Intex / Tuya-based pool equipment.

## Development setup

```bash
# Run from the repository root with Python 3.13 (the CI test stack).
python -m venv .venv
source .venv/bin/activate
python -m pip install "pytest-homeassistant-custom-component==0.13.316" "tinytuya==1.20.0" ruff

# Run the tests + linter
python -m pytest -q
python -m ruff check custom_components tests
```

On Windows PowerShell, use `.venv\Scripts\Activate.ps1` instead of `source`.
The pinned test plugin currently installs Home Assistant 2026.2.3. This is
separate from the newer actual-HA [browser test fixture](scripts/browser/README.md).
Use Node.js 24 for the card, matching CI.

## The Lovelace card

The card lives in `card/src/` and is bundled (esbuild) into
`custom_components/intex_pool/frontend/intex-pool-card.js`, which **is committed**
(HACS ships the repo as-is). If you change `card/src/`, rebuild and commit the bundle:

```bash
npm --prefix card ci
npm --prefix card test
npm --prefix card run build
python scripts/verify_release.py
```

CI fails if the committed bundle is out of date (`git diff --exit-code`).

## Documentation and screenshots

Run from the repository root:

```bash
python -m pip install "PyYAML>=6,<7"
python scripts/check_docs.py
git diff --check
```

The documentation check validates local links, heading anchors, image files and
the YAML examples in the current user/developer guides. Check changed external
instructions against their official source and review the rendered Markdown too.

The current screenshots come from the actual bundled card inside an isolated HA
frontend using synthetic data. Reproduce them with the
[browser screenshot guide](scripts/browser/README.md#documentation-images).
Commit the refreshed images together with their captions. Never commit test tokens,
`.storage`, real cloud credentials or screenshots of private installations.

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

Run the checks relevant to the change, rebuild the card if its source changed,
and describe the observed results. Release changes must update every version field
and the changelog. Documentation-only work can target the current release without
changing the integration version. The PR template lists the checklist.
