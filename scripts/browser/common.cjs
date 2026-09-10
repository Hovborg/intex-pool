"use strict";

const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const EXPECTED_LOCATION = "Intex Pool compatibility test";
const DEFAULT_HASS_URL = "http://127.0.0.1:18123";
const AUTH_FILE = path.resolve(
  process.env.HA_TEST_AUTH_FILE || path.join(".spike", "ha-test-auth.json"),
);
const TEST_CONTAINER = process.env.HA_TEST_CONTAINER || "intex-pool-ha-compat";
const FIXTURE_CONFIG = path.resolve(
  "scripts",
  "browser",
  "ha-config",
  "configuration.yaml",
);

function getTestUrl() {
  const url = new URL(process.env.HASS_TEST_URL || DEFAULT_HASS_URL);
  const loopbackHosts = new Set(["127.0.0.1", "localhost", "[::1]"]);

  assert.equal(url.protocol, "http:", "The browser harness only accepts a local HTTP test URL");
  assert(loopbackHosts.has(url.hostname), `Refusing non-loopback Home Assistant host: ${url.hostname}`);
  assert.equal(url.username, "", "The test URL must not contain credentials");
  assert.equal(url.password, "", "The test URL must not contain credentials");
  assert.equal(url.pathname, "/", "HASS_TEST_URL must contain only the origin");
  assert.equal(url.search, "", "HASS_TEST_URL must not contain a query string");
  assert.equal(url.hash, "", "HASS_TEST_URL must not contain a fragment");
  if (url.hostname === "localhost") url.hostname = "127.0.0.1";
  return url.origin;
}

async function requestJson(baseUrl, requestPath, options = {}) {
  const response = await fetch(`${baseUrl}${requestPath}`, {
    ...options,
    signal: AbortSignal.timeout(30_000),
    redirect: "error",
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${requestPath} returned HTTP ${response.status}`);
  }
  if (!body) return null;
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(`${requestPath} returned invalid JSON`);
  }
}

function docker(...args) {
  return childProcess.execFileSync("docker", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: 30_000,
  });
}

function normalizeLineEndings(value) {
  return value.replace(/\r\n?/g, "\n");
}

function assertDockerFixture(baseUrl) {
  assert.match(
    TEST_CONTAINER,
    /^[A-Za-z0-9][A-Za-z0-9_.-]+$/,
    "HA_TEST_CONTAINER contains invalid characters",
  );

  const url = new URL(baseUrl);
  const requestedPort = url.port || "80";
  const running = docker(
    "inspect",
    "--format",
    "{{.State.Running}}",
    TEST_CONTAINER,
  ).trim();
  assert.equal(running, "true", `Docker test container ${TEST_CONTAINER} is not running`);

  const ports = JSON.parse(
    docker(
      "inspect",
      "--format",
      "{{json .NetworkSettings.Ports}}",
      TEST_CONTAINER,
    ),
  );
  const bindings = ports["8123/tcp"] || [];
  const requestedAddress = url.hostname === "[::1]" ? "::1" : "127.0.0.1";
  assert(
    bindings.some(
      (binding) =>
        binding.HostIp === requestedAddress && binding.HostPort === requestedPort,
    ),
    `Container ${TEST_CONTAINER} must bind 8123/tcp to loopback port ${requestedPort}`,
  );

  const committedConfig = fs.readFileSync(FIXTURE_CONFIG, "utf8");
  const mountedConfig = docker(
    "exec",
    TEST_CONTAINER,
    "cat",
    "/config/configuration.yaml",
  );
  assert.equal(
    normalizeLineEndings(mountedConfig),
    normalizeLineEndings(committedConfig),
    `Container ${TEST_CONTAINER} is not using the committed browser fixture configuration`,
  );
}

async function assertAuthenticatedIdentity(baseUrl, accessToken) {
  assert(accessToken, `Missing access token in ${AUTH_FILE}`);
  const config = await requestJson(baseUrl, "/api/config", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  assert.equal(
    config.location_name,
    EXPECTED_LOCATION,
    `Refusing Home Assistant instance named ${JSON.stringify(config.location_name)}`,
  );
  return config;
}

function loadAuth(baseUrl) {
  let auth;
  try {
    auth = JSON.parse(fs.readFileSync(AUTH_FILE, "utf8"));
  } catch {
    throw new Error(`Cannot read saved test authentication: ${AUTH_FILE}`);
  }
  assert(auth && typeof auth === "object", "Invalid saved test authentication");
  assert(auth.access_token, `Missing access token in ${AUTH_FILE}`);
  let savedOrigin;
  try {
    savedOrigin = new URL(auth.hassUrl).origin;
  } catch {
    throw new Error("Saved test authentication has an invalid HA URL");
  }
  assert.equal(savedOrigin, baseUrl, "Saved test auth belongs to another URL");
  return auth;
}

async function loadFreshAuth(baseUrl) {
  assertDockerFixture(baseUrl);
  const auth = loadAuth(baseUrl);
  if (Number(auth.expires) > Date.now() + 60_000) return auth;
  assert(auth.refresh_token, "Test session expired; no saved refresh token is available");
  const renewed = await requestJson(baseUrl, "/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: auth.refresh_token,
      client_id: auth.clientId || `${baseUrl}/`,
    }),
  });
  const lifetime = Number(renewed.expires_in);
  assert(typeof renewed.access_token === "string" && renewed.access_token
    && Number.isFinite(lifetime) && lifetime > 0, "Invalid test-session renewal");
  // Keep the verified origin/client and original refresh token. A token endpoint
  // does not get to redirect the later browser session through extra JSON fields.
  const fresh = { ...auth, access_token: renewed.access_token,
    expires_in: lifetime, expires: Date.now() + lifetime * 1000 };
  await assertAuthenticatedIdentity(baseUrl, fresh.access_token);
  fs.writeFileSync(AUTH_FILE, JSON.stringify(fresh), { mode: 0o600 });
  return fresh;
}

async function installTestAuth(page, auth, baseUrl) {
  await page.addInitScript(({ savedAuth, expectedOrigin }) => {
    if (location.origin === expectedOrigin) {
      localStorage.setItem("hassTokens", JSON.stringify(savedAuth));
    }
  }, { savedAuth: auth, expectedOrigin: baseUrl });
}

function artifactPath(filename) {
  assert.equal(path.basename(filename), filename, "Artifact name must not contain a path");
  const directory = path.resolve(".spike");
  fs.mkdirSync(directory, { recursive: true });
  return path.join(directory, filename);
}

function getChromium() {
  const playwrightModule = process.env.PLAYWRIGHT_MODULE || "playwright";
  return require(playwrightModule).chromium;
}

module.exports = {
  AUTH_FILE,
  EXPECTED_LOCATION,
  artifactPath,
  assertAuthenticatedIdentity,
  assertDockerFixture,
  getChromium,
  getTestUrl,
  loadAuth,
  loadFreshAuth,
  installTestAuth,
  requestJson,
};
