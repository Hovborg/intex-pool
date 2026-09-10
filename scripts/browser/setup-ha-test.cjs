"use strict";

const crypto = require("node:crypto");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  AUTH_FILE,
  assertAuthenticatedIdentity,
  assertDockerFixture,
  getTestUrl,
  loadFreshAuth,
  requestJson,
} = require("./common.cjs");

const baseUrl = getTestUrl();
let token;

async function api(requestPath, data, form = false) {
  const headers = {};
  if (data) {
    headers["Content-Type"] = form
      ? "application/x-www-form-urlencoded"
      : "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token.access_token}`;
  }

  return requestJson(baseUrl, requestPath, {
    method: data ? "POST" : "GET",
    headers,
    body: data
      ? form
        ? new URLSearchParams(data)
        : JSON.stringify(data)
      : undefined,
  });
}

async function main() {
  // Before onboarding can create a user, prove that this URL belongs to the
  // named running Docker fixture with the exact committed test configuration.
  assertDockerFixture(baseUrl);

  const onboarding = await api("/api/onboarding");
  if (onboarding.some((step) => step.step === "user" && step.done)) {
    token = await loadFreshAuth(baseUrl);
  } else {
    const user = await api("/api/onboarding/users", {
      name: "Pool Test",
      username: "pooltest",
      password: crypto.randomBytes(24).toString("hex"),
      client_id: `${baseUrl}/`,
      language: "en",
    });
    token = await api(
      "/auth/token",
      {
        grant_type: "authorization_code",
        code: user.auth_code,
        client_id: `${baseUrl}/`,
      },
      true,
    );
    token.hassUrl = baseUrl;
    token.clientId = `${baseUrl}/`;
    token.expires = Date.now() + token.expires_in * 1000;
    fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
    fs.writeFileSync(AUTH_FILE, JSON.stringify(token), { mode: 0o600 });
  }

  // Re-check the authenticated API identity before changing onboarding state
  // or creating the integration entry.
  const config = await assertAuthenticatedIdentity(baseUrl, token.access_token);
  for (const step of ["core_config", "analytics", "integration"]) {
    if (onboarding.some((item) => item.step === step && item.done)) continue;
    await api(`/api/onboarding/${step}`, step === "integration" ? {
      client_id: `${baseUrl}/`, redirect_uri: `${baseUrl}/?auth_callback=1`,
    } : {});
  }

  const entries = await api("/api/config/config_entries/entry");
  if (entries.some((entry) => entry.domain === "intex_pool")) {
    console.log(`Home Assistant ${config.version}; Intex Pool entry already exists`);
    return;
  }

  const flow = await api("/api/config/config_entries/flow", {
    handler: "intex_pool",
    show_advanced_options: true,
  });
  await api(`/api/config/config_entries/flow/${flow.flow_id}`, { manual: true });
  await api(`/api/config/config_entries/flow/${flow.flow_id}`, {
    has_sensor: false,
    has_salt: false,
    has_pump: true,
  });
  await api(`/api/config/config_entries/flow/${flow.flow_id}`, { pump_mode: "entity" });
  const result = await api(`/api/config/config_entries/flow/${flow.flow_id}`, {
    pump_switch: "switch.pool_pump",
  });
  assert.equal(result.type, "create_entry", "Intex Pool setup did not create an entry");
  console.log(`Home Assistant ${config.version}; integration setup: ${result.type}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
