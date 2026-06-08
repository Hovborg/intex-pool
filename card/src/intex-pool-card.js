/**
 * Intex Pool Card — an adaptive pool overview that renders only the sections
 * for the equipment present (water chemistry sensor / saltwater chlorinator /
 * sand-filter pump, any subset, any brand of pump via entity linking).
 *
 * Ships with and is served by the intex_pool integration.
 */
import { LitElement, html, css, nothing } from "lit";

const CARD_VERSION = "0.1.0";

// translation_key -> config role, grouped by device kind (language-independent)
const ROLE_MAP = {
  sensor: {
    ph: "ph_sensor", orp: "orp_sensor", free_chlorine: "fc_sensor",
    water_temp: "sensor_temp", battery: "battery", ph_indicator: "ph_indicator",
    orp_indicator: "orp_indicator", chlorine_indicator: "chlorine_indicator",
    maintenance: "maintenance", ph_target: "ph_target", orp_target: "orp_target",
    refresh: "refresh_button",
  },
  salt: {
    power: "power_switch", chlorination: "chlorination_switch", salinity: "salinity",
    status: "salt_status", alarm: "salt_alarm", self_clean: "self_clean",
    water_temp: "salt_temp", time_remaining: "time_remaining", error_code: "salt_error",
  },
  pump: { pump: "pump_switch" },
};
const SALT_KEYS = Object.keys(ROLE_MAP.salt);
const SENSOR_KEYS = Object.keys(ROLE_MAP.sensor);

function fireEvent(node, type, detail) {
  const ev = new Event(type, { bubbles: true, composed: true });
  ev.detail = detail;
  node.dispatchEvent(ev);
}

function detectEntities(hass) {
  const out = {};
  const ents = hass?.entities || {};
  const byDevice = {};
  for (const [eid, ent] of Object.entries(ents)) {
    if (ent.platform !== "intex_pool") continue;
    (byDevice[ent.device_id || "_"] ??= []).push({ eid, tk: ent.translation_key });
  }
  for (const list of Object.values(byDevice)) {
    let kind = "pump";
    if (list.some((x) => SALT_KEYS.includes(x.tk))) kind = "salt";
    else if (list.some((x) => SENSOR_KEYS.includes(x.tk))) kind = "sensor";
    for (const { eid, tk } of list) {
      const role = ROLE_MAP[kind]?.[tk];
      if (role && !out[role]) out[role] = eid;
    }
  }
  return out;
}

class IntexPoolCard extends LitElement {
  static properties = { _config: { state: true } };

  static getStubConfig(hass) {
    return { title: "Pool", ...detectEntities(hass) };
  }

  static getConfigForm() {
    const ent = (domains) => ({ selector: { entity: { domain: domains, integration: "intex_pool" } } });
    const any = (domains) => ({ selector: { entity: { domain: domains } } });
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { type: "expandable", title: "Water chemistry", schema: [
          { name: "ph_sensor", ...ent("sensor") },
          { name: "orp_sensor", ...ent("sensor") },
          { name: "fc_sensor", ...ent("sensor") },
          { name: "sensor_temp", ...ent("sensor") },
          { name: "battery", ...ent("sensor") },
          { name: "refresh_button", ...ent("button") },
        ] },
        { type: "expandable", title: "Saltwater system", schema: [
          { name: "power_switch", ...ent("switch") },
          { name: "chlorination_switch", ...ent("switch") },
          { name: "salinity", ...ent("sensor") },
          { name: "salt_status", ...ent("sensor") },
          { name: "salt_alarm", ...ent("sensor") },
          { name: "self_clean", ...ent("select") },
          { name: "salt_temp", ...ent("sensor") },
          { name: "time_remaining", ...ent("sensor") },
        ] },
        { type: "expandable", title: "Sand filter pump (any brand)", schema: [
          { name: "pump_switch", ...any("switch") },
          { name: "pump_power", ...any("sensor") },
          { name: "pump_energy", ...any("sensor") },
          { name: "pump_temp", ...any("sensor") },
        ] },
      ],
    };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this.requestUpdate();
  }
  get hass() {
    return this._hass;
  }

  getCardSize() {
    return 6;
  }
  getGridOptions() {
    return { rows: 6, columns: 12, min_columns: 6 };
  }

  // resolve effective entity map: explicit config wins, else auto-detect
  _roles() {
    const detected = detectEntities(this._hass);
    return { ...detected, ...this._config };
  }

  _st(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }
  _has(id) {
    return Boolean(this._st(id));
  }
  _num(id) {
    const s = this._st(id);
    const v = s ? parseFloat(s.state) : NaN;
    return Number.isFinite(v) ? v : null;
  }
  _on(id) {
    return this._st(id)?.state === "on";
  }
  _name(id) {
    const s = this._st(id);
    return s?.attributes?.friendly_name || id;
  }
  _fmt(s) {
    // localized state + unit (e.g. "Working", "1500 ppm", "94 %")
    try {
      return this._hass.formatEntityState(s);
    } catch (e) {
      return s.state;
    }
  }
  _moreInfo(id) {
    if (id) fireEvent(this, "hass-more-info", { entityId: id });
  }
  _toggle(id) {
    this._hass.callService("homeassistant", "toggle", { entity_id: id });
  }
  _press(id) {
    this._hass.callService("button", "press", { entity_id: id });
  }

  _gauge(id, { min, max, unit, label, lo, hi, decimals = 1 }) {
    const v = this._num(id);
    const s = this._st(id);
    const txt = v == null ? (s?.state ?? "—") : v.toFixed(decimals);
    const frac = v == null ? 0 : Math.max(0, Math.min(1, (v - min) / (max - min)));
    const angle = -120 + frac * 240; // -120°..120°
    const inRange = v != null && (lo == null || v >= lo) && (hi == null || v <= hi);
    const color = v == null ? "var(--disabled-text-color)" : inRange ? "var(--success-color, #43a047)" : "var(--warning-color, #ffa600)";
    // arc path (240° sweep)
    const r = 40, cx = 50, cy = 50;
    const pol = (a) => [cx + r * Math.cos((a - 90) * Math.PI / 180), cy + r * Math.sin((a - 90) * Math.PI / 180)];
    const [sx, sy] = pol(-120), [ex, ey] = pol(120);
    const [nx, ny] = pol(angle);
    return html`
      <button class="gauge" @click=${() => this._moreInfo(id)} aria-label=${label}>
        <svg viewBox="0 0 100 78">
          <path d="M ${sx} ${sy} A ${r} ${r} 0 1 1 ${ex} ${ey}" fill="none"
                stroke="var(--divider-color)" stroke-width="7" stroke-linecap="round"/>
          <circle cx=${nx} cy=${ny} r="5.5" fill=${color}/>
          <text x="50" y="48" class="g-val" fill="var(--primary-text-color)">${txt}</text>
          <text x="50" y="62" class="g-unit" fill="var(--secondary-text-color)">${unit ?? ""}</text>
        </svg>
        <div class="g-label">${label}</div>
      </button>`;
  }

  _chip(id, { label, icon }) {
    const s = this._st(id);
    if (!s) return nothing;
    return html`
      <button class="chip" @click=${() => this._moreInfo(id)}>
        ${icon ? html`<ha-icon icon=${icon}></ha-icon>` : nothing}
        <span class="chip-label">${label}</span>
        <span class="chip-val">${this._fmt(s)}</span>
      </button>`;
  }

  _toggleBtn(id, icon, label) {
    if (!this._has(id)) return nothing;
    const on = this._on(id);
    return html`
      <button class="toggle ${on ? "on" : ""}" @click=${() => this._toggle(id)}
              aria-pressed=${on} aria-label=${label}>
        <ha-icon icon=${icon}></ha-icon>
        <span class="t-label">${label}</span>
        <span class="t-state">${on ? "ON" : "OFF"}</span>
      </button>`;
  }

  render() {
    if (!this._hass || !this._config) return nothing;
    const c = this._roles();

    const hasChem = ["ph_sensor", "orp_sensor", "fc_sensor", "sensor_temp", "battery"].some((k) => this._has(c[k]));
    const hasSalt = ["power_switch", "chlorination_switch", "salinity", "salt_status"].some((k) => this._has(c[k]));
    const hasPump = ["pump_switch", "pump_power", "pump_energy", "pump_temp"].some((k) => this._has(c[k]));

    return html`
      <ha-card>
        <div class="header">
          <ha-icon icon="mdi:pool"></ha-icon>
          <span class="title">${this._config.title ?? "Pool"}</span>
          ${this._headerStatus(c)}
        </div>
        <div class="body">
          ${hasChem ? this._chemistry(c) : nothing}
          ${hasSalt ? this._chlorinator(c) : nothing}
          ${hasPump ? this._pump(c) : nothing}
          ${!hasChem && !hasSalt && !hasPump
            ? html`<div class="empty">No pool devices configured. Edit the card to link entities.</div>`
            : nothing}
        </div>
      </ha-card>`;
  }

  _headerStatus(c) {
    const alarm = this._st(c.salt_alarm);
    const maint = this._st(c.maintenance);
    if (alarm && alarm.state !== "normal" && alarm.state !== "unknown" && alarm.state !== "unavailable")
      return html`<span class="pill alarm">${this._fmt(alarm)}</span>`;
    if (maint && maint.state === "red")
      return html`<span class="pill warn">Service</span>`;
    return html`<span class="pill ok">OK</span>`;
  }

  _chemistry(c) {
    return html`
      <div class="section">
        <div class="section-head">Water chemistry
          ${this._has(c.refresh_button)
            ? html`<button class="icon-btn" @click=${() => this._press(c.refresh_button)} title="Refresh">
                     <ha-icon icon="mdi:refresh"></ha-icon></button>`
            : nothing}
        </div>
        <div class="gauges">
          ${this._has(c.ph_sensor) ? this._gauge(c.ph_sensor, { min: 6.8, max: 8.0, unit: "pH", label: "pH", lo: 7.2, hi: 7.6, decimals: 1 }) : nothing}
          ${this._has(c.orp_sensor) ? this._gauge(c.orp_sensor, { min: 400, max: 900, unit: "mV", label: "ORP", lo: 650, hi: 750, decimals: 0 }) : nothing}
          ${this._has(c.sensor_temp) ? this._gauge(c.sensor_temp, { min: 0, max: 40, unit: "°C", label: "Temp", lo: 10, hi: 35, decimals: 1 }) : nothing}
        </div>
        <div class="chips">
          ${this._chip(c.fc_sensor, { label: "Free Cl", icon: "mdi:test-tube" })}
          ${this._chip(c.battery, { label: "Battery", icon: "mdi:battery" })}
        </div>
      </div>`;
  }

  _chlorinator(c) {
    const salt = this._st(c.salinity);
    const status = this._st(c.salt_status);
    return html`
      <div class="section">
        <div class="section-head">Saltwater system</div>
        <div class="toggles">
          ${this._toggleBtn(c.power_switch, "mdi:power", "Power")}
          ${this._toggleBtn(c.chlorination_switch, "mdi:flash", "Chlorine")}
        </div>
        <div class="chips">
          ${salt ? html`<button class="chip" @click=${() => this._moreInfo(c.salinity)}>
              <ha-icon icon="mdi:shaker-outline"></ha-icon><span class="chip-label">Salt</span>
              <span class="chip-val">${this._fmt(salt)}</span></button>` : nothing}
          ${status ? html`<button class="chip" @click=${() => this._moreInfo(c.salt_status)}>
              <ha-icon icon="mdi:state-machine"></ha-icon><span class="chip-label">Status</span>
              <span class="chip-val">${this._fmt(status)}</span></button>` : nothing}
          ${this._chip(c.salt_temp, { label: "Temp", icon: "mdi:thermometer" })}
          ${this._chip(c.time_remaining, { label: "Left", icon: "mdi:timer-sand" })}
          ${this._chip(c.self_clean, { label: "Clean", icon: "mdi:broom" })}
        </div>
      </div>`;
  }

  _pump(c) {
    return html`
      <div class="section">
        <div class="section-head">Sand filter pump</div>
        <div class="toggles">
          ${this._toggleBtn(c.pump_switch, "mdi:water-pump", "Pump")}
        </div>
        <div class="chips">
          ${this._chip(c.pump_power, { label: "Power", icon: "mdi:flash" })}
          ${this._chip(c.pump_energy, { label: "Energy", icon: "mdi:lightning-bolt" })}
          ${this._chip(c.pump_temp, { label: "Water", icon: "mdi:thermometer" })}
        </div>
      </div>`;
  }

  static styles = css`
    ha-card { padding: 12px 14px 16px; }
    .header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .header ha-icon { color: var(--primary-color); }
    .title { font-size: 1.15rem; font-weight: 600; flex: 1; }
    .pill { font-size: .72rem; font-weight: 600; padding: 3px 10px; border-radius: 999px;
            color: var(--text-primary-color, #fff); white-space: nowrap; }
    .pill.ok { background: var(--success-color, #43a047); }
    .pill.warn { background: var(--warning-color, #ffa600); }
    .pill.alarm { background: var(--error-color, #db4437); }
    .section { padding: 10px 0; border-top: 1px solid var(--divider-color); }
    .section:first-of-type { border-top: none; }
    .section-head { display: flex; align-items: center; justify-content: space-between;
                    font-size: .78rem; font-weight: 600; text-transform: uppercase;
                    letter-spacing: .04em; color: var(--secondary-text-color); margin-bottom: 8px; }
    .gauges { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 6px; }
    .gauge { background: none; border: none; cursor: pointer; padding: 0; }
    .gauge svg { width: 100%; height: auto; }
    .g-val { font-size: 17px; font-weight: 700; text-anchor: middle; }
    .g-unit { font-size: 9px; text-anchor: middle; }
    .g-label { font-size: .72rem; color: var(--secondary-text-color); margin-top: -2px; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .chip { display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
            background: var(--secondary-background-color); border: none; border-radius: 999px;
            padding: 5px 11px; font-size: .82rem; color: var(--primary-text-color); }
    .chip ha-icon { --mdc-icon-size: 17px; color: var(--secondary-text-color); }
    .chip-label { color: var(--secondary-text-color); }
    .chip-val { font-weight: 600; }
    .toggles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
    .toggle { display: flex; flex-direction: column; align-items: center; gap: 2px; cursor: pointer;
              border: 1px solid var(--divider-color); border-radius: 14px; padding: 12px 8px;
              background: var(--card-background-color); color: var(--primary-text-color);
              transition: background .2s, color .2s, border-color .2s; }
    .toggle ha-icon { --mdc-icon-size: 26px; }
    .toggle .t-label { font-size: .82rem; font-weight: 600; }
    .toggle .t-state { font-size: .68rem; color: var(--secondary-text-color); }
    .toggle.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
    .toggle.on .t-state { color: var(--text-primary-color, #fff); opacity: .85; }
    .icon-btn { background: none; border: none; cursor: pointer; color: var(--secondary-text-color); padding: 2px; }
    .empty { padding: 18px 4px; color: var(--secondary-text-color); text-align: center; }
    @media (prefers-reduced-motion: reduce) { .toggle { transition: none; } }
  `;
}

if (!customElements.get("intex-pool-card")) {
  customElements.define("intex-pool-card", IntexPoolCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "intex-pool-card",
  name: "Intex Pool",
  description: "Adaptive pool overview — chemistry, chlorinator and pump.",
  preview: true,
  documentationURL: "https://github.com/Hovborg/intex-pool",
});

console.info(`%c INTEX-POOL-CARD %c v${CARD_VERSION} `,
  "color:#fff;background:#0288d1;font-weight:700;border-radius:3px 0 0 3px;padding:2px 4px",
  "color:#0288d1;background:#fff;border-radius:0 3px 3px 0;padding:2px 4px");
