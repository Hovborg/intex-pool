# GitHub Feedback Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-autonomous:subagent-driven-development (recommended) or superpowers-autonomous:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reproducible setup failures reported in issues #13 and #18 and eliminate the schedule lost-update race documented in PR #16, without importing PR #16's unsafe fixed-slot Quick Run design.

**Architecture:** Local protocol auto-detection validates every supported protocol candidate, persists the proven version, and uses one attempt per candidate to keep the setup latency bounded. Cloud-region selection mirrors TinyTuya 1.20's actual endpoint map. Schedule read-modify-write operations run behind the coordinator's write lock through a mutation callback, and known stale provider shadows cannot replace the latest optimistic generation.

**Tech Stack:** Python 3.13, Home Assistant config flows/entities, TinyTuya 1.20.0, pytest-homeassistant-custom-component, Ruff 0.16.1.

## Global Constraints

- Keep `main` and all external GitHub issues/PRs untouched; work only on `codex/fix-issue-comments-pr-race`.
- Write and observe each regression test failing before production changes.
- Preserve explicit protocol selection and its immediate-auth-failure behavior.
- Keep secrets out of tests, logs, documentation, and error details.
- Update README, translations, `strings.json`, compatibility notes, and CHANGELOG with behavior changes.

---

### Task 1: Complete Tuya setup choices and guidance

**Files:**
- Modify: `custom_components/intex_pool/config_flow.py`
- Modify: `custom_components/intex_pool/strings.json`
- Modify: `custom_components/intex_pool/translations/en.json`
- Modify: `custom_components/intex_pool/translations/da.json`
- Modify: `tests/test_config_flow.py`
- Modify: `README.md`
- Modify: `docs/compatibility.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: TinyTuya 1.20 region codes `cn`, `in`, `sg`, `us`, `us-e`, `eu`, `eu-w`.
- Produces: config-flow region selectors that can address every TinyTuya cloud endpoint used by this integration.

- [x] **Step 1: Write a failing config-schema test**

Assert that the user-step region selector exposes `eu-w`, `us-e`, and `sg` in addition to the current regions.

- [x] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_config_flow.py -k region_options -q`

Expected: FAIL because `_REGION_OPTIONS` currently contains only `eu`, `us`, `cn`, and `in`.

- [x] **Step 3: Implement the complete region list**

Set `_REGION_OPTIONS` to:

```python
_REGION_OPTIONS = ["eu", "eu-w", "us", "us-e", "cn", "in", "sg"]
```

Update field descriptions so Central and Western Europe are distinguishable.

- [x] **Step 4: Document the supported account-linking path**

Add concise README guidance based on Tuya's official flow: Smart Home cloud project, active IoT Core, `Devices -> Link App Account`, scan through Tuya Smart or Smart Life, wait for authorization propagation, and select the data center matching the project. State that re-pairing can rotate the local key and may affect vendor-app relationships.

- [x] **Step 5: Run the focused test and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_config_flow.py -k region_options -q`

Expected: PASS.

### Task 2: Make manual protocol auto-detection real

**Files:**
- Modify: `custom_components/intex_pool/config_flow.py`
- Modify: `custom_components/intex_pool/strings.json`
- Modify: `custom_components/intex_pool/translations/en.json`
- Modify: `custom_components/intex_pool/translations/da.json`
- Modify: `tests/test_config_flow.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `VERSION_CANDIDATES = [3.4, 3.5, 3.3, 3.1]` and `LocalClient.status()`.
- Produces: `validate_local(hass, ui) -> float`, returning and persisting the proven version after validating candidates for `version="auto"`.

- [x] **Step 1: Write failing protocol tests**

Add tests proving:

```python
# auto: 3.4 returns TuyaAuthError, 3.5 succeeds -> validation succeeds
# explicit 3.4: TuyaAuthError -> validation stops immediately
# auto: every candidate returns TuyaAuthError -> invalid auth after all candidates
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_config_flow.py -k 'auto_protocol or explicit_protocol' -q`

Expected: the auto fallback test fails because current code raises after candidate 3.4.

- [x] **Step 3: Implement candidate-aware validation**

For explicit versions, retain four transport retries and immediate auth rejection. For `auto`, construct a fresh `LocalClient` and make one attempt for each candidate, moving on after either version/auth mismatch or transport failure. Return and persist the successful version. Report `TuyaAuthError` only if all candidates reject authentication; otherwise preserve the transport error without multiplying the socket timeout by nested retries.

- [x] **Step 4: Clarify UI errors and troubleshooting**

Change `invalid_auth` to say that all selected/automatic protocol candidates rejected the connection, and document that the IP is the device's current LAN address while `auto` now tries 3.4, 3.5, 3.3, and 3.1.

- [x] **Step 5: Run focused config-flow tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_config_flow.py -q`

Expected: PASS.

### Task 3: Make schedule mutations atomic

**Files:**
- Modify: `custom_components/intex_pool/coordinator.py`
- Modify: `custom_components/intex_pool/entity.py`
- Modify: `custom_components/intex_pool/switch.py`
- Modify: `custom_components/intex_pool/number.py`
- Modify: `custom_components/intex_pool/time.py`
- Modify: `custom_components/intex_pool/__init__.py`
- Modify: `tests/test_schedule_entity.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: `ScheduleCoordinator.async_update_slots(mutator: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]) -> list[dict[str, Any]]`.
- Preserves: `ScheduleCoordinator.async_write_slots(slots)` for intentional whole-blob replacement and existing tests.
- Consumes: pure `schedule.set_slot()` transformations.

- [x] **Step 1: Write a failing concurrent-mutation test**

Start two `async_update_slots` calls concurrently, one updating slot 1 and one updating slot 2, and assert the final optimistic/coordinator state contains both changes.

- [x] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/python -m pytest tests/test_schedule_entity.py -k concurrent -q`

Expected: FAIL because `async_update_slots` does not exist.

- [x] **Step 3: Implement the locked mutation primitive**

Acquire `_write_lock`, snapshot the current normalized slots inside the lock, call the synchronous mutator, issue the encoded blob, publish optimistic state, release after the existing settle delay, then refresh. Preserve the optimistic generation while the provider still returns a known pre-write blob, but accept a matching readback or an unknown external update.

- [x] **Step 4: Route every production read-modify-write through it**

Change schedule switch toggles including Boost suspend/restore, duration numbers, start times, and the `set_schedule` service to pass mutation callbacks. Keep post-write bookkeeping committed only after a successful cloud write.

- [x] **Step 5: Run schedule and service tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_schedule.py tests/test_schedule_entity.py tests/test_v012_features.py -q`

Expected: PASS.

### Task 4: Full verification and handoff

**Files:**
- Inspect all modified files and branch diff.

- [x] **Step 1: Run the complete Python suite**

Run: `.venv/bin/python -m pytest -q`

Expected: 0 failures.

- [x] **Step 2: Run lint and release consistency**

Run: `.venv/bin/ruff check custom_components tests`

Run: `.venv/bin/python scripts/verify_release.py`

Expected: both exit 0.

- [x] **Step 3: Run card tests/build even though card source is unchanged**

Run: `npm test --prefix card && npm run build --prefix card && git diff --exit-code -- custom_components/intex_pool/frontend`

Expected: card tests/build pass and generated frontend artifacts remain unchanged.

- [x] **Step 4: Review the final diff and external boundaries**

Run: `git diff --check && git status --short --branch && git diff --stat origin/main...HEAD && git diff origin/main...HEAD`

Confirm no issue comment, PR update, push, release, or deployment occurred.

- [x] **Step 5: Report evidence and residual uncertainty**

Report offline coverage separately from hardware evidence. The issue #18 regression is simulated with TinyTuya-compatible errors; physical SX2100 setup on 3.5 remains not freshly hardware-verified in this turn. PR #16 Quick Run remains unmerged and requires a separate safe slot-ownership design.
