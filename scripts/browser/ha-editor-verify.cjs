"use strict";

const assert = require("node:assert/strict");

const {
  assertAuthenticatedIdentity,
  getChromium,
  getTestUrl,
  loadFreshAuth,
  installTestAuth,
} = require("./common.cjs");

const baseUrl = getTestUrl();

async function main() {
  const auth = await loadFreshAuth(baseUrl);
  const config = await assertAuthenticatedIdentity(baseUrl, auth.access_token);
  const browser = await getChromium().launch({ headless: true, channel: "chrome" });

  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await installTestAuth(page, auth, baseUrl);
    await page.goto(`${baseUrl}/pool-storage/masonry`);
    await page.locator("intex-pool-card").waitFor();

    await page.evaluate(async () => {
      const hass = document.querySelector("home-assistant").hass;
      const dashboard = await hass.callWS({
        type: "lovelace/config",
        url_path: "pool-storage",
      });
      dashboard.views[0].cards = [
        {
          type: "custom:intex-pool-card",
          title: "Legacy editor regression",
          pump_switch: "switch.pool_pump",
          pump: { pump_switch: "switch.saltwater_relay" },
        },
      ];
      await hass.callWS({
        type: "lovelace/config/save",
        url_path: "pool-storage",
        config: dashboard,
      });
    });

    await page.reload();
    await page.locator("intex-pool-card").waitFor();
    assert.equal(
      await page.locator("intex-pool-card").evaluate((card) => card._roles().pump_switch),
      "switch.saltwater_relay",
    );

    async function openEditor() {
      await page.getByRole("button", { name: "Edit dashboard", exact: true }).click();
      await page.getByRole("button", { name: "Edit", exact: true }).click();
      await page.locator("intex-pool-card-editor ha-form").first().waitFor();
    }

    async function savedDashboard() {
      return page.evaluate(() =>
        document.querySelector("home-assistant").hass.callWS({
          type: "lovelace/config",
          url_path: "pool-storage",
        }),
      );
    }

    await openEditor();
    const editor = page.locator("intex-pool-card-editor");
    assert.equal(await editor.evaluate((element) => element._config.pump_switch), "switch.saltwater_relay");
    await editor.locator("ha-form").first().evaluate((form) => {
      form.dispatchEvent(
        new CustomEvent("value-changed", {
          detail: { value: { ...form.data, pump_switch: "switch.pool_pump" } },
          bubbles: true,
          composed: true,
        }),
      );
    });
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.getByRole("button", { name: "Done", exact: true }).click();

    let dashboard = await savedDashboard();
    assert.equal(dashboard.views[0].cards[0].pump, undefined);
    assert.equal(dashboard.views[0].cards[0].pump_switch, "switch.pool_pump");

    await page.reload();
    await page.locator("intex-pool-card").waitFor();
    const before = await page.evaluate(
      () => document.querySelector("home-assistant").hass.states["switch.pool_pump"].state,
    );
    await page.getByRole("button", { name: "Pump", exact: true }).click();
    await page.waitForFunction(
      (previous) =>
        document.querySelector("home-assistant").hass.states["switch.pool_pump"].state !== previous,
      before,
      { timeout: 5_000 },
    );

    await openEditor();
    await page.locator("intex-pool-card-editor ha-form").first().evaluate((form) => {
      const value = { ...form.data };
      delete value.pump_switch;
      form.dispatchEvent(
        new CustomEvent("value-changed", {
          detail: { value },
          bubbles: true,
          composed: true,
        }),
      );
    });
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.getByRole("button", { name: "Done", exact: true }).click();

    dashboard = await savedDashboard();
    assert.equal(dashboard.views[0].cards[0].pump_switch, "");
    await page.reload();
    await page.locator("intex-pool-card").waitFor();
    assert.equal(await page.getByRole("button", { name: "Pump", exact: true }).count(), 0);
    assert.deepEqual(errors, []);
    console.log(
      `PASS HA ${config.version}: legacy override, canonical save, switch toggle and cleared autodetection`,
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
