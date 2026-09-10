# Home Assistant browser compatibility harness

These scripts exercise the Intex Pool card in a disposable Home Assistant
container. They cover YAML and storage dashboards, current layout types,
wrappers, narrow viewports, editor migration and long schedule content.

The harness defaults to `http://127.0.0.1:18123` and the container name
`intex-pool-ha-compat`. Before onboarding, setup verifies through Docker that
the named container is running, exposes `8123/tcp` only on the requested
loopback port, and has the exact committed fixture configuration mounted.
Authenticated checks also require Home Assistant to report the location name
`Intex Pool compatibility test` before later mutations. The fixture switches
control only the two fixture `input_boolean` entities.

The browser runs use the installed Chrome channel. Install Playwright in the
ignored test-tools directory so the main project gains no dependency:

```powershell
New-Item -ItemType Directory -Force .spike\test-tools | Out-Null
npm install --prefix .spike\test-tools playwright
$env:PLAYWRIGHT_MODULE = (Resolve-Path '.spike\test-tools\node_modules\playwright').Path
```

## Start the disposable fixture

Run these commands from the repository root. They copy the committed fixture
into `.spike`, where Home Assistant may create its private `.storage` state:

```powershell
New-Item -ItemType Directory -Force .spike\ha-config | Out-Null
Copy-Item scripts\browser\ha-config\configuration.yaml .spike\ha-config\configuration.yaml -Force
Copy-Item scripts\browser\ha-config\pool-dashboards.yaml .spike\ha-config\pool-dashboards.yaml -Force

$projectRoot = (Get-Location).Path
$haConfig = Join-Path $projectRoot '.spike\ha-config'
$customComponents = Join-Path $projectRoot 'custom_components'

docker run --detach --name intex-pool-ha-compat `
  --publish 127.0.0.1:18123:8123 `
  --mount "type=bind,source=$haConfig,target=/config" `
  --mount "type=bind,source=$customComponents,target=/config/custom_components,readonly" `
  ghcr.io/home-assistant/home-assistant:2026.9.1
```

Wait until `docker logs intex-pool-ha-compat` shows that Home Assistant has
started. Initialize only this disposable instance:

```powershell
node scripts\browser\setup-ha-test.cjs
```

The setup creates `.spike\ha-test-auth.json`. It contains a bearer token. Never
print, share, attach or commit that file.

## Run the checks

Run the matrix first because it creates the storage dashboard used by the
editor and stress checks:

```powershell
node scripts\browser\ha-matrix.cjs
node scripts\browser\ha-editor-verify.cjs
node scripts\browser\ha-layout-stress.cjs
```

Screenshots and the matrix JSON remain under `.spike`. The harness was proven
against Home Assistant `2026.9.1` with frontend `20260826.6`; the result files
record the Home Assistant version reported by the actual test instance.

To use another disposable loopback port, change the host side of `--publish`
(for example, to `127.0.0.1:18124:8123`), then set the overrides before setup
and keep the same values for every command:

```powershell
$env:HASS_TEST_URL = 'http://127.0.0.1:18124'
$env:HA_TEST_AUTH_FILE = (Join-Path (Get-Location) '.spike\ha-test-auth-18124.json')
$env:HA_TEST_CONTAINER = 'intex-pool-ha-full-20260910'
```

Do not aim `HASS_TEST_URL` at a normal Home Assistant installation. The scripts
intentionally create dashboards, change test entities and edit card config.
They will still refuse it unless its location name exactly matches the fixture.

When finished, remove only the named disposable container:

```powershell
docker rm --force intex-pool-ha-compat
```
