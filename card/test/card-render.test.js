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

function cardWithRenderedControls(config, states) {
  const card = new Card();
  card.setConfig({ type: "custom:intex-pool-card", ...config });
  card.hass = { states, entities: {} };
  const controls = [];
  card._ctrl = (entityId, _icon, label) => {
    if (!card._has(entityId)) return null;
    controls.push({ entityId, label });
    return entityId;
  };
  card.render();
  return { card, controls };
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

test("editor keeps expandable entity fields in the card's flat config shape", () => {
  const expandables = Card.getConfigForm().schema.filter(({ type }) => type === "expandable");

  assert.deepEqual(
    expandables.map(({ name, flatten }) => ({ name, flatten })),
    [
      { name: "water_chemistry", flatten: true },
      { name: "salt_system", flatten: true },
      { name: "pump", flatten: true },
    ],
  );
});

test("editor accepts ordinary Home Assistant switches for external saltwater control", () => {
  const saltSection = Card.getConfigForm().schema.find(({ name }) => name === "salt_system");
  const switches = saltSection.schema.filter(({ name }) =>
    ["power_switch", "chlorination_switch"].includes(name));

  assert.deepEqual(
    switches.map(({ name, selector }) => ({ name, entity: selector.entity })),
    [
      { name: "power_switch", entity: { domain: "switch" } },
      { name: "chlorination_switch", entity: { domain: "switch" } },
    ],
  );
});

test("card renders an external pump saved by the older nested editor shape", () => {
  const states = { "switch.pool_pump": { state: "off", attributes: {} } };

  assert.deepEqual(
    cardWithRenderedControls({ pump: { pump_switch: "switch.pool_pump" } }, states).controls,
    [{ entityId: "switch.pool_pump", label: "Pump" }],
  );
});

test("external saltwater control targets the configured ordinary HA switch", () => {
  const calls = [];
  const states = { "switch.shelly_salt": { state: "off", attributes: {} } };
  const card = new Card();
  card.setConfig({
    type: "custom:intex-pool-card",
    salt_system: { power_switch: "switch.shelly_salt" },
  });
  card.hass = {
    states,
    entities: {},
    callService: (...args) => {
      calls.push(args);
      return Promise.resolve();
    },
  };

  card._toggle(card._roles().power_switch);

  assert.deepEqual(calls, [[
    "homeassistant",
    "toggle",
    { entity_id: "switch.shelly_salt" },
  ]]);
});

test('legacy manual selection overrides stale flat autodetection', () => {
  const card = new Card();
  card.setConfig({pump_switch:'switch.auto',pump:{pump_switch:'switch.manual'}});
  card.hass={entities:{},states:{}};
  assert.equal(card._roles().pump_switch,'switch.manual');
});

test('editor migrates legacy data and emits flat edits without resurrecting cleared roles', () => {
  const Editor=definitions.get('intex-pool-card-editor');
  assert.ok(Editor,'canonical card editor must be registered');
  const editor=new Editor();
  editor.hass={entities:{},states:{}};
  editor.setConfig({type:'custom:intex-pool-card',title:'My pool',grid_options:{columns:6},pump_switch:'switch.auto',pump:{pump_switch:'switch.manual'}});
  assert.equal(editor._config.pump_switch,'switch.manual');
  assert.equal(editor._config.pump,undefined);
  const emitted=[];editor.dispatchEvent=e=>emitted.push(e.detail.config);
  editor._valueChanged({stopPropagation(){},detail:{value:{...editor._config,pump_switch:'switch.new'}}});
  assert.equal(emitted.at(-1).pump_switch,'switch.new');
  const cleared={...editor._config};delete cleared.pump_switch;
  editor._valueChanged({stopPropagation(){},detail:{value:cleared}});
  assert.equal(emitted.at(-1).pump_switch,'');
  assert.deepEqual(emitted.at(-1).grid_options,{columns:6});
  const card=new Card();card.setConfig(emitted.at(-1));card.hass={entities:{},states:{}};
  assert.equal(card._roles().pump_switch,'');
});

test('editor allows clearing a title without restoring the previous text', () => {
  const Editor=definitions.get('intex-pool-card-editor');
  const editor=new Editor();editor.hass={entities:{},states:{}};
  editor.setConfig({type:'custom:intex-pool-card',title:'Old title',grid_options:{columns:6}});
  let saved;editor.dispatchEvent=e=>{saved=e.detail.config;};
  editor._valueChanged({stopPropagation(){},detail:{value:{type:'custom:intex-pool-card',grid_options:{columns:6}}}});
  assert.equal(saved.title,undefined);
  assert.deepEqual(saved.grid_options,{columns:6});
});

test('loading both automatic and manual resource URLs registers one card-picker entry', async () => {
  await import('../src/intex-pool-card.js?manual-resource');
  assert.equal(window.customCards.filter(card=>card.type==='intex-pool-card').length,1);
});
