"use strict";

const assert = require("node:assert/strict");

const {
  artifactPath,
  assertAuthenticatedIdentity,
  getChromium,
  getTestUrl,
  loadAuth,
  requestJson,
} = require("./common.cjs");

const baseUrl = getTestUrl();

async function main() {
  const auth = loadAuth(baseUrl);
  const config = await assertAuthenticatedIdentity(baseUrl, auth.access_token);

  await requestJson(baseUrl, "/api/states/sensor.test_schedules", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${auth.access_token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      state: "7",
      attributes: {
        schedules: Array.from(
          { length: 7 },
          (_, index) =>
            `Daily schedule ${index + 1}: 08:00, circulation and chlorination for 12 hours`,
        ),
      },
    }),
  });

  const browser = await getChromium().launch({ headless: true, channel: "chrome" });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 900 } });
    await page.addInitScript(
      (savedAuth) => localStorage.setItem("hassTokens", JSON.stringify(savedAuth)),
      auth,
    );
    // The editor regression replaces storage views; bootstrap from stable YAML.
    await page.goto(`${baseUrl}/pool-yaml/sections`);
    await page.locator("intex-pool-card").waitFor();

    await page.evaluate(async () => {
      const hass = document.querySelector("home-assistant").hass;
      const dashboard = await hass.callWS({
        type: "lovelace/config",
        url_path: "pool-storage",
      });
      dashboard.views = dashboard.views.filter((view) => view.path !== "stress");
      dashboard.views.push({
        title: "Stress",
        path: "stress",
        type: "sections",
        sections: [
          {
            type: "grid",
            cards: [
              {
                type: "custom:intex-pool-card",
                title: "Long content",
                pump_switch: "switch.pool_pump",
                schedules_sensor: "sensor.test_schedules",
                pump_schedules_sensor: "sensor.test_schedules",
              },
              {
                type: "custom:intex-pool-card",
                title: "Following card",
                pump_switch: "switch.pool_pump",
              },
            ],
          },
        ],
      });
      await hass.callWS({
        type: "lovelace/config/save",
        url_path: "pool-storage",
        config: dashboard,
      });
    });

    await page.goto(`${baseUrl}/pool-storage/stress`);
    const cards = page.locator("intex-pool-card");
    await cards.nth(1).waitFor();
    await page.screenshot({ path: artifactPath("ha-stress-after.png"), fullPage: true });
    const geometry = await cards.evaluateAll((elements) =>
      elements.map((element) => ({
        title: element._config.title,
        card: element.shadowRoot.querySelector("ha-card").getBoundingClientRect().toJSON(),
      })),
    );
    const gap = geometry[1].card.top - geometry[0].card.bottom;
    assert(gap >= 7, JSON.stringify(geometry));
    console.log(`PASS HA ${config.version}: sections schedule overflow gap ${gap}px`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
