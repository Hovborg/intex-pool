"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");

const {
  artifactPath,
  assertAuthenticatedIdentity,
  getChromium,
  getTestUrl,
  loadAuth,
} = require("./common.cjs");

const baseUrl = getTestUrl();

async function main() {
  const auth = loadAuth(baseUrl);
  const config = await assertAuthenticatedIdentity(baseUrl, auth.access_token);
  const chromium = getChromium();
  const browser = await chromium.launch({ headless: true, channel: "chrome" });

  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(
      (savedAuth) => localStorage.setItem("hassTokens", JSON.stringify(savedAuth)),
      auth,
    );
    await page.goto(`${baseUrl}/pool-yaml/masonry`);
    await page.locator("intex-pool-card").waitFor({ timeout: 30_000 });

    const card = {
      type: "custom:intex-pool-card",
      title: "Pool compatibility",
      pump_switch: "switch.pool_pump",
      power_switch: "switch.saltwater_relay",
    };
    const views = ["masonry", "sections", "panel", "sidebar"].map((type) => ({
      title: type,
      path: type,
      type,
      ...(type === "sections"
        ? { sections: [{ type: "grid", cards: [card] }] }
        : { cards: [card] }),
    }));

    await page.evaluate(async (storageViews) => {
      const hass = document.querySelector("home-assistant").hass;
      const dashboards = await hass.callWS({ type: "lovelace/dashboards/list" });
      if (!dashboards.some((dashboard) => dashboard.url_path === "pool-storage")) {
        await hass.callWS({
          type: "lovelace/dashboards/create",
          url_path: "pool-storage",
          title: "Pool storage tests",
          mode: "storage",
          show_in_sidebar: true,
          require_admin: false,
        });
      }
      await hass.callWS({
        type: "lovelace/config/save",
        url_path: "pool-storage",
        config: { title: "Pool storage tests", views: storageViews },
      });
    }, views);

    const results = [];
    errors.length = 0;
    const dashboards = [
      ["pool-yaml", ["masonry", "sections", "panel", "sidebar", "wrappers", "detail"]],
      ["pool-storage", ["masonry", "sections", "panel", "sidebar"]],
    ];

    for (const width of [1280, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      for (const [dashboard, paths] of dashboards) {
        for (const viewPath of paths) {
          await page.goto(`${baseUrl}/${dashboard}/${viewPath}`);
          const cards = page.locator("intex-pool-card");
          await cards.first().waitFor({ timeout: 20_000 });

          const pump = cards.first().getByRole("button", { name: "Pump", exact: true });
          await pump.waitFor();
          const before = await page.evaluate(
            () => document.querySelector("home-assistant").hass.states["switch.pool_pump"].state,
          );
          await pump.click();
          await page.waitForFunction(
            (previous) =>
              document.querySelector("home-assistant").hass.states["switch.pool_pump"].state !==
              previous,
            before,
            { timeout: 5_000 },
          );

          const geometry = await cards.evaluateAll((elements) =>
            elements.map((element) => {
              const outer = element.getBoundingClientRect();
              const inner = element.shadowRoot.querySelector("ha-card").getBoundingClientRect();
              return {
                width: outer.width,
                height: outer.height,
                innerHeight: inner.height,
                overflow: element.shadowRoot.querySelector("ha-card").scrollWidth > inner.width + 1,
              };
            }),
          );
          assert(geometry.every((item) => item.width > 0 && !item.overflow));
          results.push({ width, dashboard, viewPath, cards: await cards.count(), geometry });

          if (viewPath === "sections" || viewPath === "wrappers") {
            await page.screenshot({
              path: artifactPath(`ha-${dashboard}-${viewPath}-${width}.png`),
              fullPage: true,
            });
          }
        }
      }
    }

    assert.deepEqual(errors, []);
    fs.writeFileSync(
      artifactPath("ha-dashboard-results.json"),
      JSON.stringify({ ha: config.version, results, errors }, null, 2),
    );
    console.log(`PASS HA ${config.version}: ${results.length} dashboard matrix cases`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
