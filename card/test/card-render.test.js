import assert from "node:assert/strict";
import test from "node:test";

globalThis.window = { customCards: [] };
const definitions = new Map();
globalThis.customElements = {
  get: (name) => definitions.get(name),
  define: (name, component) => definitions.set(name, component),
};
await import("../src/intex-pool-card.js");
const Card = definitions.get("intex-pool-card");

function renderedTiles(config, states) {
  const card = new Card();
  card.setConfig({ type: "custom:intex-pool-card", ...config });
  card.hass = { states, entities: {} };
  const tiles = [];
  card._tile = (entityId, options) => {
    tiles.push({ entityId, label: options.label });
    return entityId;
  };
  card.render();
  return tiles;
}

const config = { sensor_temp: "sensor.analyzer", salt_temp: "sensor.salt" };
const states = {
  "sensor.analyzer": { state: "26", attributes: {} },
  "sensor.salt": { state: "25", attributes: {} },
};

test("header renders both temperatures with distinct source labels", () => {
  assert.deepEqual(renderedTiles(config, states), [
    { entityId: "sensor.analyzer", label: "Temp WA" },
    { entityId: "sensor.salt", label: "Temp salt" },
  ]);
});

test("header keeps a single Temp tile when only one reading is available", () => {
  assert.deepEqual(renderedTiles(config, { "sensor.salt": states["sensor.salt"] }), [
    { entityId: "sensor.salt", label: "Temp" },
  ]);
});

test("header does not duplicate a temperature assigned to both roles", () => {
  assert.deepEqual(renderedTiles({ ...config, salt_temp: config.sensor_temp }, states), [
    { entityId: "sensor.analyzer", label: "Temp" },
  ]);
});
