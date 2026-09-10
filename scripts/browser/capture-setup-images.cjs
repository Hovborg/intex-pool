"use strict";

// Only the isolated HA fixture is allowed. Open/cancel setup and edit a demo
// dashboard; never complete device setup or submit cloud credentials.
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  assertAuthenticatedIdentity, getChromium, getTestUrl, loadFreshAuth, installTestAuth,
} = require("./common.cjs");

async function main() {
  const baseUrl = getTestUrl();
  const auth = await loadFreshAuth(baseUrl);
  const config = await assertAuthenticatedIdentity(baseUrl, auth.access_token);
  const browser = await getChromium().launch({ headless: true, channel: "chrome" });
  const images = [];
  try {
    let page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 });
    const errors = [];
    let navigating = true;
    let navigationDisconnects = 0;
    const onPageError = (error) => {
      // HA rejects pending websocket calls when a full navigation tears down
      // the old frontend. Keep actual capture-phase errors fatal.
      if (navigating && error.message === "disconnected") navigationDisconnects += 1;
      else errors.push(error.message);
    };
    page.on("pageerror", onPageError);
    await installTestAuth(page, auth, baseUrl);
    await page.goto(`${baseUrl}/config/integrations`);
    await page.getByRole("button", { name: "Add integration", exact: true }).click();
    navigating = false;
    await page.getByPlaceholder("Search for a brand name").fill("Intex");
    await page.getByRole("button", { name: "Intex Pool", exact: true }).click();
    await page.getByRole("textbox", { name: "Access ID", exact: true }).waitFor();

    async function capture(name) {
      await documentReady();
      await page.getByRole("dialog").last().screenshot({ path: path.resolve("docs/images", name), animations: "disabled" });
      images.push(name);
    }
    async function documentReady() {
      await page.evaluate(() => document.fonts.ready);
      await page.getByRole("button", { name: "Submit", exact: true }).waitFor();
    }
    assert.equal(await page.getByRole("textbox", { name: "Access ID", exact: true }).inputValue(), "");
    assert.equal(await page.getByRole("textbox", { name: "Access secret", exact: true }).inputValue(), "");
    await capture("setup-cloud.png");
    await page.getByRole("checkbox", { name: "Set up manually instead (no cloud)", exact: true }).check({ force: true });
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    await page.getByRole("checkbox", { name: "Sand filter pump", exact: true }).waitFor();
    await page.getByRole("checkbox", { name: "Sand filter pump", exact: true }).check({ force: true });
    await capture("setup-equipment.png");
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    // The default pump mode is an existing entity. Submit only this mode step.
    await page.getByText("How is your pump controlled?", { exact: true }).waitFor();
    await capture("setup-pump-type.png");
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    await page.getByText("Link any pump (any brand) by selecting its switch and, optionally, its power/energy sensors.", { exact: true }).waitFor();
    await capture("setup-pump-entity.png");
    assert.deepEqual(errors, []);
    navigating = true;
    page.removeListener("pageerror", onPageError);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.close();
    page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 });
    page.on("pageerror", onPageError);
    await installTestAuth(page, auth, baseUrl);
    await page.goto(`${baseUrl}/pool-yaml/masonry`);
    await page.locator("intex-pool-card").waitFor();
    navigating = false;
    await page.evaluate(async () => {
      const hass = document.querySelector("home-assistant").hass;
      const dashboards = await hass.callWS({ type: "lovelace/dashboards/list" });
      if (!dashboards.some((dashboard) => dashboard.url_path === "pool-docs")) {
        await hass.callWS({ type: "lovelace/dashboards/create", url_path: "pool-docs",
          title: "Pool documentation demo", mode: "storage", show_in_sidebar: false, require_admin: false });
      }
      await hass.callWS({ type: "lovelace/config/save", url_path: "pool-docs", config: {
        title: "Pool documentation demo", views: [{ title: "Pool", path: "pool", type: "masonry", cards: [{
          type: "custom:intex-pool-card", title: "Pool", variant: "light",
          pump_switch: "switch.pool_pump", power_switch: "switch.saltwater_relay",
        }] }],
      } });
    });
    assert.deepEqual(errors, []);
    navigating = true;
    page.removeListener("pageerror", onPageError);
    await page.close();
    page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 });
    page.on("pageerror", onPageError);
    await installTestAuth(page, auth, baseUrl);
    await page.goto(`${baseUrl}/pool-docs/pool`);
    await page.locator("intex-pool-card").waitFor();
    navigating = false;
    await page.getByRole("button", { name: "Edit dashboard", exact: true }).click();
    await page.getByRole("button", { name: "Edit", exact: true }).click();
    await page.locator("intex-pool-card-editor ha-form").first().waitFor();
    await page.getByText("Sand filter pump (any brand)", { exact: true }).click();
    await page.getByText("Pump switch", { exact: true }).waitFor();
    await page.evaluate(() => document.fonts.ready);
    await page.getByRole("dialog").last().screenshot({ path: path.resolve("docs/images/card-editor.png"), animations: "disabled" });
    images.push("card-editor.png");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ home_assistant: config.version, fixture_only: true, images,
      navigation_disconnects: navigationDisconnects, errors }));
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
