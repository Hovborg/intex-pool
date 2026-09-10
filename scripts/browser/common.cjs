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
  return url.origin;
}

async function requestJson(baseUrl, requestPath, options = {}) {
  const response = await fetch(`${baseUrl}${requestPath}`, {
    ...options,
    signal: AbortSignal.timeout(30_000),
  });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${requestPath} returned HTTP ${response.status}`);
  }
  return body ? JSON.parse(body) : null;
}

function docker(...args) {
  return childProcess.execFileSync("docker", args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
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
  const loopbackAddresses = new Set(["127.0.0.1", "::1"]);
  assert(
    bindings.some(
      (binding) =>
        loopbackAddresses.has(binding.HostIp) && binding.HostPort === requestedPort,
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
  const auth = JSON.parse(fs.readFileSync(AUTH_FILE, "utf8"));
  assert(auth.access_token, `Missing access token in ${AUTH_FILE}`);
  assert.equal(new URL(auth.hassUrl).origin, baseUrl, "Saved test auth belongs to another URL");
  return auth;
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
  requestJson,
};
