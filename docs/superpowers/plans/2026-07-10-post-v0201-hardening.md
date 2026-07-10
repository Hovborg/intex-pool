# Post-v0.20.1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a verified maintenance release candidate with current dependencies, automatically recovering optional schedules, complete card schedule support, and release-drift prevention.

**Architecture:** Standalone Tuya credentials are wrapped in a shared lazy provider consumed by schedule coordinators; coordinator polling supplies recovery without reloading local devices. Card entity detection becomes a pure tested module. A repository verifier makes versions and generated artefacts an enforceable release contract.

**Tech Stack:** Python 3.13, Home Assistant DataUpdateCoordinator, pytest, JavaScript ES modules, Lit 3, Node test runner, esbuild 0.28, GitHub Actions.

## Global Constraints

- Preserve local control availability during every optional-cloud failure.
- Preserve required sensor-cloud setup and authentication semantics.
- Do not change DP102 or schedule byte interpretation without hardware evidence.
- Never log or copy cloud secrets into diagnostics, tests, or generated artefacts.
- Every behaviour change uses a witnessed red-green test cycle.

---

### Task 1: Dependency and release consistency

**Files:**
- Modify: `.github/workflows/hassfest.yaml`
- Modify: `.github/workflows/lint.yaml`
- Modify: `.github/workflows/tests.yaml`
- Modify: `.github/workflows/validate.yaml`
- Modify: `card/package.json`
- Modify: `card/package-lock.json`
- Modify: `custom_components/intex_pool/manifest.json`
- Create: `scripts/verify_release.py`
- Create: `tests/test_release_consistency.py`

**Interfaces:**
- Consumes: version strings from manifest, pyproject, package metadata, lockfile, and built card.
- Produces: `python scripts/verify_release.py` with exit 0 only for a synchronized release tree.

- [ ] Write a failing test that invokes the verifier against fixtures with a stale lockfile root version and mismatched compiled card version.
- [ ] Run `pytest tests/test_release_consistency.py -q` and confirm the verifier is missing or the stale fixture is not rejected.
- [ ] Implement `scripts/verify_release.py` with JSON/TOML parsing and a compiled-version regular expression; report every mismatch in one run.
- [ ] Run the targeted test and confirm it passes.
- [ ] Update Actions to checkout v7, setup-python v6, setup-node v6, and Ruff action SHA `278981a28ce3188b1e39527901f38254bf3aac89`.
- [ ] Restrict workflow push events to `branches: ["**"]` so version tags do not duplicate branch CI.
- [ ] Update esbuild to 0.28.1, regenerate the lockfile, and verify `npm audit --audit-level=moderate` exits 0.
- [ ] Test tinytuya 1.20.0 with the full suite; retain 1.18.1 if any API or behavioural regression is found and document the evidence.
- [ ] Build the card and run the verifier against the real tree.

### Task 2: Recovering standalone cloud schedules

**Files:**
- Modify: `custom_components/intex_pool/coordinator.py`
- Modify: `custom_components/intex_pool/__init__.py`
- Modify: `tests/test_init.py`
- Modify: `tests/test_coordinator.py`

**Interfaces:**
- Produces: `CloudClientProvider.async_get() -> CloudClient`.
- Extends: `ScheduleCoordinator(..., client: CloudClient | None, provider: CloudClientProvider | None = None, optional_cloud: bool = False)`.

- [ ] Extend `test_pump_only_stays_loaded_when_standalone_cloud_is_down` to require a present but unavailable pump schedule coordinator.
- [ ] Add a test whose cloud constructor fails once, succeeds on the next refresh, and proves schedule data recovers without reloading the entry.
- [ ] Add a test proving salt and pump schedule coordinators share one successfully constructed standalone cloud client.
- [ ] Add a test proving standalone cloud auth starts reauth while the local pump remains loaded.
- [ ] Run these tests and confirm their expected failures against v0.20.1.
- [ ] Implement the provider, lazy client acquisition, optional auth handling, and shared provider wiring in `_build_data`.
- [ ] Run the targeted tests and then all coordinator/setup tests.

### Task 3: Pump schedules and Home Assistant card suggestions

**Files:**
- Create: `card/src/entity-detection.js`
- Create: `card/test/entity-detection.test.js`
- Modify: `card/src/intex-pool-card.js`
- Modify: `card/package.json`
- Modify: `custom_components/intex_pool/frontend/intex-pool-card.js`
- Modify: `custom_components/intex_pool/frontend/intex-pool-card.js.map`

**Interfaces:**
- Produces: `detectEntities(hass)`, `entitySuggestion(hass, entityId)`, and the exported `ROLE_MAP`.
- Consumes: Home Assistant entity-registry objects with `platform`, `device_id`, and `translation_key`.

- [ ] Add Node tests proving pump `translation_key: "schedules"` maps to `pump_schedules_sensor`, salt schedules remain separate, and non-Intex entity suggestions return null.
- [ ] Run `node --test card/test/*.test.js` and confirm the new expectations fail.
- [ ] Extract entity detection, add pump schedule mapping, and implement the suggestion contract.
- [ ] Add `npm test`, card-editor field `pump_schedules_sensor`, and labelled salt/pump schedule groups.
- [ ] Run Node tests, build, and verify the committed bundle and source map exactly match the source.

### Task 4: Targeted config-flow and compatibility evidence

**Files:**
- Modify: `tests/test_config_flow.py`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Create: `docs/compatibility.md`

**Interfaces:**
- Consumes: existing config/reauth flow schemas and diagnostics fields.
- Produces: documented hardware verification records for model, firmware, protocol, datapoints, and schedule semantics.

- [ ] Run branch coverage for `config_flow.py` and identify unexecuted credential, timeout, and reauth branches.
- [ ] Add one minimal failing test per uncovered user-visible branch, then implement only real defects revealed by those tests.
- [ ] Document verified SX2100/QS behaviour separately from DP102 and schedule inferences.
- [ ] Add contributor instructions for redacted diagnostics and physical-device verification after tinytuya upgrades.

### Task 5: Full completion audit

**Files:**
- Modify: `CHANGELOG.md`
- Inspect: every changed file and generated artefact.

**Interfaces:**
- Consumes: Tasks 1-4 outputs.
- Produces: an evidence-backed release candidate with no unverified completion claims.

- [ ] Update the changelog with user-visible changes, recovery semantics, dependency changes, and remaining hardware caveats.
- [ ] Run `pytest --cov=custom_components.intex_pool --cov-report=term-missing` and confirm zero failures.
- [ ] Run Ruff, Node tests, card build, npm audit, release verifier, YAML parse, and `git diff --check`.
- [ ] Rebuild once more and confirm `git diff` does not change generated files.
- [ ] Review `git diff` for credentials, unrelated changes, version drift, and every design requirement.
- [ ] Inspect current GitHub issues, PRs, and Actions before any publication or closure action.
