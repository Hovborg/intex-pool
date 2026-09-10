"use strict";

// Render the shipped card with synthetic readings inside the real HA frontend.
// No device state or service is changed. Authentication remains in .spike.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
  assertAuthenticatedIdentity, getChromium, getTestUrl, loadFreshAuth, installTestAuth,
} = require("./common.cjs");

async function main() {
  const baseUrl = getTestUrl();
  const auth = await loadFreshAuth(baseUrl);
  const config = await assertAuthenticatedIdentity(baseUrl, auth.access_token);
  const version = JSON.parse(fs.readFileSync("custom_components/intex_pool/manifest.json", "utf8")).version;
  const browser = await getChromium().launch({ headless: true, channel: "chrome" });
  const directory = path.resolve("docs/images");
  fs.mkdirSync(directory, { recursive: true });
  const output = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await installTestAuth(page, auth, baseUrl);
    await page.goto(`${baseUrl}/pool-yaml/masonry`);
    await page.locator("intex-pool-card").first().waitFor({ timeout: 30_000 });
    await page.evaluate(async (version) => {
      const liveHass = document.querySelector("home-assistant").hass;
      const states = {};
      function state(key, value, attributes = {}) {
        const id = key.includes(".") ? key : `sensor.demo_${key}`;
        states[id] = { entity_id: id, state: String(value), attributes: { friendly_name: key, ...attributes },
          last_changed: new Date().toISOString(), last_updated: new Date().toISOString(), context: {} };
        return id;
      }
      const chemistry = {
        ph_sensor: state("ph", 7.4), orp_sensor: state("orp", 712),
        fc_sensor: state("free_chlorine", 1.8), sensor_temp: state("water_temperature", 26.4),
        battery: state("battery", 94), refresh_button: state("button.demo_refresh", "unknown"),
      };
      const salt = {
        salt_temp: state("salt_temperature", 26.1), salinity: state("salinity", 950),
        salt_status: state("status", "working"), salt_alarm: state("alarm", "normal"),
        power_switch: state("switch.demo_power", "on"),
        chlorination_switch: state("switch.demo_chlorination", "on"),
      };
      const pump = { pump_switch: state("switch.demo_pump", "on") };
      const full = { ...chemistry, ...salt, ...pump };
      const schedules = {
        schedules_sensor: state("salt_schedules", 1, { schedules: ["Daily 09:00 · 2h · on"] }),
        pump_schedules_sensor: state("pump_schedules", 1, { schedules: ["Daily 08:00 · 4h · on"] }),
      };
      const demoHass = {
        ...liveHass, states, entities: {}, devices: {},
        formatEntityState: (entity) => entity.state === "working" ? "Working" : entity.state,
        callService: async () => { throw new Error("Documentation preview is read-only"); },
      };
      const stage = document.createElement("div");
      stage.id = "docs-stage";
      stage.style.cssText = "position:relative;box-sizing:border-box;padding:28px;background:#eef3f7;color:#16202a;font-family:Roboto,Arial,sans-serif;";
      document.body.append(stage);
      const style = document.createElement("style");
      style.textContent = "body{margin:0!important;background:#eef3f7!important}body>home-assistant{display:none!important}#docs-stage *{box-sizing:border-box}#docs-stage intex-pool-card{display:block;width:100%}#docs-stage .gallery{display:grid;gap:20px;align-items:start}#docs-stage figure{margin:0;min-width:0}#docs-stage figcaption{margin:0 0 12px;font-size:14px;line-height:1.4;font-weight:600}#docs-stage footer{margin-top:20px;font-size:12px;color:#637282;line-height:1.5}";
      document.head.append(style);
      window.renderDocumentation = async (mode, variant) => {
        stage.replaceChildren();
        const gallery = document.createElement("div");
        gallery.className = "gallery";
        let definitions;
        if (mode === "variants") {
          stage.style.width = "1436px";
          gallery.style.gridTemplateColumns = "repeat(3,minmax(0,1fr))";
          definitions = [["Water Analyzer", chemistry, "light"], ["Analyzer + saltwater + pump", full, "light"], ["Linked pump", pump, "light"]];
        } else if (mode === "styles") {
          stage.style.width = "1436px";
          gallery.style.gridTemplateColumns = "repeat(3,minmax(0,1fr))";
          definitions = [["Dark", full, "dark"], ["Ocean", full, "ocean"], ["Midnight", full, "midnight"]];
        } else {
          stage.style.width = mode === "mobile" ? "360px" : "476px";
          definitions = [[null, mode === "schedules" ? { ...full, ...schedules } : full, variant || "light"]];
        }
        for (const [label, entities, appearance] of definitions) {
          const figure = document.createElement("figure");
          if (label) {
            const caption = document.createElement("figcaption");
            caption.textContent = label;
            figure.append(caption);
          }
          const card = document.createElement("intex-pool-card");
          card.setConfig({ type: "custom:intex-pool-card", title: "Pool", variant: appearance, ...entities });
          card.hass = demoHass;
          figure.append(card);
          gallery.append(figure);
        }
        stage.append(gallery);
        const footer = document.createElement("footer");
        footer.textContent = `Intex Pool ${version} · Demo readings`;
        stage.append(footer);
        await Promise.all([...stage.querySelectorAll("intex-pool-card")].map((card) => card.updateComplete));
        await document.fonts.ready;
      };
    }, version);
    const cases = [
      ["card-light.png", "single", "light"], ["card-dark.png", "single", "dark"],
      ["card-ocean.png", "single", "ocean"], ["card-midnight.png", "single", "midnight"],
      ["card-variants.png", "variants"], ["card-styles.png", "styles"],
      ["card-mobile.png", "mobile"], ["card-schedules.png", "schedules"],
    ];
    for (const [filename, mode, variant] of cases) {
      await page.evaluate(({ mode, variant }) => window.renderDocumentation(mode, variant), { mode, variant });
      await page.locator("#docs-stage ha-icon").first().waitFor();
      await page.waitForFunction(() => [...document.querySelectorAll("#docs-stage intex-pool-card")].every((card) =>
        [...card.shadowRoot.querySelectorAll("ha-icon")].every((icon) =>
          icon.shadowRoot?.querySelector("ha-svg-icon")?.shadowRoot?.querySelector("path")?.getAttribute("d"))));
      const overflow = await page.locator("#docs-stage intex-pool-card").evaluateAll((cards) => cards.some((card) => {
        const inner = card.shadowRoot.querySelector("ha-card");
        return inner.scrollWidth > inner.clientWidth + 1;
      }));
      assert.equal(overflow, false, `${filename} overflows`);
      await page.locator("#docs-stage").screenshot({ path: path.join(directory, filename), animations: "disabled" });
      output.push(filename);
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ home_assistant: config.version, card: version, synthetic_readings: true, images: output, errors }));
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error.message); process.exitCode = 1; });
