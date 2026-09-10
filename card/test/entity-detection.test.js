import assert from "node:assert/strict";
import test from "node:test";


async function detectionModule() {
  try {
    return await import("../src/entity-detection.js");
  } catch (error) {
    assert.fail(`entity-detection.js must be importable: ${error.message}`);
  }
}


function hassFixture() {
  return {
    entities: {
      "switch.salt_power": {
        platform: "intex_pool", device_id: "salt", translation_key: "power",
      },
      "sensor.salt_schedules": {
        platform: "intex_pool", device_id: "salt", translation_key: "schedules",
      },
      "switch.pump": {
        platform: "intex_pool", device_id: "pump", translation_key: "pump",
      },
      "sensor.pump_schedules": {
        platform: "intex_pool", device_id: "pump", translation_key: "schedules",
      },
      "sensor.unrelated": {
        platform: "other_integration", device_id: "other", translation_key: "schedules",
      },
    },
  };
}


test("detectEntities keeps salt and pump schedules separate", async () => {
  const { detectEntities } = await detectionModule();

  assert.deepEqual(detectEntities(hassFixture()), {
    power_switch: "switch.salt_power",
    schedules_sensor: "sensor.salt_schedules",
    pump_switch: "switch.pump",
    pump_schedules_sensor: "sensor.pump_schedules",
  });
});


test("detectEntities resolves the linked external pump switch from the Intex selector", async () => {
  const { detectEntities } = await detectionModule();
  const hass = {
    entities: {
      "select.pool_pump_switch": {
        platform: "intex_pool", device_id: "pump", translation_key: "pump_switch_select",
      },
    },
    states: {
      "select.pool_pump_switch": { state: "switch.pool_pump", attributes: {} },
      // The linked switch belongs to another integration and is deliberately
      // absent from hass.entities: only its ordinary HA state is required.
      "switch.pool_pump": { state: "off", attributes: {} },
    },
  };

  assert.deepEqual(detectEntities(hass), { pump_switch: "switch.pool_pump" });
});


test("detectEntities follows a changed pump selector state with the same registry", async () => {
  const { detectEntities } = await detectionModule();
  const entities = {
    "select.pool_pump_switch": {
      platform: "intex_pool", device_id: "pump", translation_key: "pump_switch_select",
    },
  };
  const hass = {
    entities,
    states: {
      "select.pool_pump_switch": { state: "switch.first_pump", attributes: {} },
      "switch.first_pump": { state: "off", attributes: {} },
    },
  };

  assert.equal(detectEntities(hass).pump_switch, "switch.first_pump");

  hass.states = {
    "select.pool_pump_switch": { state: "switch.second_pump", attributes: {} },
    "switch.second_pump": { state: "on", attributes: {} },
  };
  assert.equal(detectEntities(hass).pump_switch, "switch.second_pump");
});


test("entitySuggestion populates the card for an Intex entity", async () => {
  const { entitySuggestion } = await detectionModule();
  const hass = hassFixture();

  assert.deepEqual(entitySuggestion(hass, "switch.pump"), {
    config: {
      type: "custom:intex-pool-card",
      power_switch: "switch.salt_power",
      schedules_sensor: "sensor.salt_schedules",
      pump_switch: "switch.pump",
      pump_schedules_sensor: "sensor.pump_schedules",
    },
  });
});


test("entitySuggestion rejects entities from other integrations", async () => {
  const { entitySuggestion } = await detectionModule();

  assert.equal(entitySuggestion(hassFixture(), "sensor.unrelated"), null);
  assert.equal(entitySuggestion(hassFixture(), "sensor.missing"), null);
});


test("scheduleGroups labels salt and pump schedules independently", async () => {
  const { scheduleGroups } = await detectionModule();
  const hass = {
    states: {
      "sensor.salt_schedules": {
        attributes: { schedules: ["Daily 03:00 · 3h · on"] },
      },
      "sensor.pump_schedules": {
        attributes: { schedules: ["Daily 08:00 · 2h · on"] },
      },
    },
  };

  assert.deepEqual(
    scheduleGroups(hass, {
      schedules_sensor: "sensor.salt_schedules",
      pump_schedules_sensor: "sensor.pump_schedules",
    }),
    [
      {
        entityId: "sensor.salt_schedules",
        label: "Saltwater schedules",
        schedules: ["Daily 03:00 · 3h · on"],
      },
      {
        entityId: "sensor.pump_schedules",
        label: "Pump schedules",
        schedules: ["Daily 08:00 · 2h · on"],
      },
    ],
  );
});
