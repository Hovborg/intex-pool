# GitHub issue implementation checks — 2026-09-05

Baseline: `fdc9bc03e36e595ba9a29ad7fdb57bf71a141f7b` (main, v0.21.2).
All issue bodies and comments for #13, #18, #20 and #22 were read through the
GitHub connector. Work used an isolated checkout, with no live pool/HA calls.

## Findings and changes

- **#13:** v0.21.2 already documents Smart Life/Tuya Smart linking, active IoT
  Core, exact data-center selection and authorization delay. Its config flow
  already exposes the distinct regions. Added a standalone setup guide and
  clarified that manual Water Analyzer setup still requires developer-cloud
  credentials; the built-in HA Tuya integration is not a prerequisite.
- **#18:** the reporter confirmed protocol 3.5 solved the SX2100 connection.
  `validate_local` in the baseline already tries all supported protocols after
  Err 914 in auto mode and persists the successful version. Existing positive,
  all-rejected and explicit-version regression tests pass. No credential
  checking or authentication logic was changed.
- **#20:** refresh unconditionally wrote `refresh_switch`, including a
  chlorinator whose schema has `retest_switch`. Entry construction now connects
  the sensor to the local salt coordinator only when both device IDs match.
  Measurement refresh then uses the existing serialized DP 107 write path.
  Without a matching local salt device, a reported `retest_switch` selects that
  cloud property; separate analyzers retain `refresh_switch`. The dashboard
  button uses the same routing. A command error leaves the repair form open
  with a translated retry message.
- **#22:** the header selected one temperature with a fallback expression.
  It now renders both available sources as Temp WA and Temp salt, deduplicates
  identical entity assignments, and retains Temp for a single available value.
- **#21:** applied the esbuild 0.28.1 → 0.28.2 package/lockfile update and rebuilt
  the shipped JavaScript and source map.

## Verification

- Before the backend change, targeted Python tests reported four failures:
  wrong cloud command, missing local re-test, unhandled repair command failure
  and the button still writing the wrong command. After the change all six
  selected tests passed, including the unchanged separate-analyzer path.
- Before the header change, `npm test` reported 1 failed / 6 passed; the new
  test observed only the analyzer temperature. Afterward: **7 passed, 0 failed**.
- Full CI-pinned Python suite on Linux/Python 3.13:
  `docker exec intex-pool-test-20260905 python -m pytest -o addopts='' -p no:cacheprovider -q`
  → **237 passed in 17.77s**.
- Dependencies match CI: `pytest-homeassistant-custom-component==0.13.316`
  (Home Assistant 2026.2.3), `tinytuya==1.20.0`. A fresh disposable
  `python:3.13-slim` container mounts the checkout read-only; gcc/libc headers
  were installed inside that container to build CI's lru-dict dependency.
- Windows Python 3.14 cannot load this HA test plugin because HA imports
  Unix-only `fcntl`. Linux verification above ran the actual plugin and HA
  framework, without compatibility mocks for those imports.
- `.venv/Scripts/ruff.exe check custom_components tests` → **All checks passed!**
- `npm run build` → **Built intex-pool-card v0.21.2** using esbuild 0.28.2.
- `python scripts/verify_release.py` → **Release metadata and card artefacts
  agree on v0.21.2**. Release versions remain unchanged for this unreleased patch.
- `git diff --check` → exit 0.

Physical verification remains required: confirm DP 107 produces a new
measurement/timestamp on AGP SALTWATER SYSTEM R1, check cloud-only retest on
actual firmware, and inspect the two temperature tiles in the HA browser/app.
No claim is made that app migration preserves vendor control relationships.
