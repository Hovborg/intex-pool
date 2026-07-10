/** Pure Home Assistant entity-registry mapping for the Intex Pool card. */

export const ROLE_MAP = {
  sensor: {
    ph: "ph_sensor", orp: "orp_sensor", free_chlorine: "fc_sensor",
    water_temp: "sensor_temp", battery: "battery",
    ph_indicator: "ph_indicator", orp_indicator: "orp_indicator",
    refresh: "refresh_button",
    orp_trend: "orp_trend", last_measurement: "last_measurement",
  },
  salt: {
    power: "power_switch", chlorination: "chlorination_switch", salinity: "salinity",
    status: "salt_status", alarm: "salt_alarm",
    water_temp: "salt_temp", schedules: "schedules_sensor",
  },
  pump: {
    pump: "pump_switch", schedules: "pump_schedules_sensor",
  },
};


function makeDiscriminators() {
  const roles = Object.keys(ROLE_MAP);
  const result = {};
  for (const role of roles) {
    const ownKeys = new Set(Object.keys(ROLE_MAP[role]));
    for (const other of roles) {
      if (other === role) continue;
      for (const key of Object.keys(ROLE_MAP[other])) ownKeys.delete(key);
    }
    result[role] = ownKeys;
  }
  return result;
}


const DISCRIMINATORS = makeDiscriminators();
let detectionCache = null;


export function detectEntities(hass) {
  const entities = hass?.entities || {};
  if (detectionCache?.ref === entities) return detectionCache.result;

  const detected = {};
  const entitiesByDevice = {};
  for (const [entityId, entity] of Object.entries(entities)) {
    if (entity.platform !== "intex_pool") continue;
    (entitiesByDevice[entity.device_id || "_"] ??= []).push({
      entityId,
      translationKey: entity.translation_key,
    });
  }

  for (const deviceEntities of Object.values(entitiesByDevice)) {
    let role = "pump";
    if (deviceEntities.some((entity) => DISCRIMINATORS.salt.has(entity.translationKey))) {
      role = "salt";
    } else if (
      deviceEntities.some((entity) => DISCRIMINATORS.sensor.has(entity.translationKey))
    ) {
      role = "sensor";
    }
    for (const { entityId, translationKey } of deviceEntities) {
      const configKey = ROLE_MAP[role]?.[translationKey];
      if (configKey && !detected[configKey]) detected[configKey] = entityId;
    }
  }

  detectionCache = { ref: entities, result: detected };
  return detected;
}


export function entitySuggestion(hass, entityId) {
  if (hass?.entities?.[entityId]?.platform !== "intex_pool") return null;
  return {
    config: {
      type: "custom:intex-pool-card",
      ...detectEntities(hass),
    },
  };
}


export function scheduleGroups(hass, config) {
  const definitions = [
    [config.schedules_sensor, "Saltwater schedules"],
    [config.pump_schedules_sensor, "Pump schedules"],
  ];
  const seen = new Set();
  const groups = [];
  for (const [entityId, label] of definitions) {
    if (!entityId || seen.has(entityId)) continue;
    const schedules = hass?.states?.[entityId]?.attributes?.schedules || [];
    if (!schedules.length) continue;
    seen.add(entityId);
    groups.push({ entityId, label, schedules });
  }
  return groups;
}
