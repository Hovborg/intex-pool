/**
 * Intex Pool Card — a compact, refined pool overview.
 *
 * One tight card: a header with overall status, a row of small metric tiles
 * (each with an at-a-glance in-range bar), and a row of compact control pills.
 * Adapts to whichever equipment is present (water sensor / saltwater system /
 * sand-filter pump, any subset, any brand of pump via entity linking).
 *
 * Ships with and is served by the intex_pool integration.
 */
import { LitElement, html, css, nothing } from "lit";
import {
  detectEntities,
  entitySuggestion,
  scheduleGroups,
} from "./entity-detection.js";

// Injected at build time from package.json via esbuild --define (see build.mjs).
// Falls back to "dev" for an un-defined source build.
const CARD_VERSION =
  typeof __CARD_VERSION__ !== "undefined" ? __CARD_VERSION__ : "dev";

// Selectable appearance variants. "auto" inherits the HA theme; the others
// override the CSS variables on the card so you can pick a look regardless of
// your HA theme. Gradient backgrounds go through --ha-card-background.
//
// Fix 7 — light palette: darkened primary/success/warning/error so that
// white text on the background reaches ≥ 4.5:1 (WCAG AA).
//   #0078a8  4.94:1  (was #0aa2e0  2.89:1)
//   #1e7d4f  5.12:1  (was #2bb673  2.61:1)
//   #a66200  4.81:1  (was #f5a623  2.03:1)
//   #b83224  5.97:1  (was #e0533d  3.84:1)
const VARIANTS = {
  light: {
    "--primary-color": "#0078a8", "--primary-text-color": "#16202a", "--secondary-text-color": "#5b6b78",
    "--card-background-color": "#ffffff", "--ha-card-background": "#ffffff", "--secondary-background-color": "#eef3f7",
    "--divider-color": "#e1e8ee", "--success-color": "#1e7d4f", "--warning-color": "#a66200",
    "--error-color": "#b83224", "--text-primary-color": "#ffffff",
  },
  dark: {
    "--primary-color": "#23b5f0", "--primary-text-color": "#e9eef2", "--secondary-text-color": "#9aa7b2",
    "--card-background-color": "#1b2228", "--ha-card-background": "#1b2228", "--secondary-background-color": "#252e36",
    "--divider-color": "#333d46", "--success-color": "#37c98a", "--warning-color": "#f5b342",
    "--error-color": "#ec6a55", "--text-primary-color": "#06222f",
  },
  ocean: {
    "--primary-color": "#2bd4c7", "--primary-text-color": "#e7f3f8", "--secondary-text-color": "#8fb3c2",
    "--card-background-color": "#0e2230", "--ha-card-background": "linear-gradient(155deg, #0c3145, #071620)",
    "--secondary-background-color": "rgba(255,255,255,.07)", "--divider-color": "rgba(255,255,255,.10)",
    "--success-color": "#34e0b0", "--warning-color": "#ffc24b", "--error-color": "#ff7a66", "--text-primary-color": "#04202a",
  },
  midnight: {
    "--primary-color": "#7aa2ff", "--primary-text-color": "#e4e9f2", "--secondary-text-color": "#8b93a7",
    "--card-background-color": "#11151c", "--ha-card-background": "linear-gradient(160deg, #161b26, #0a0d13)",
    "--secondary-background-color": "#1c2230", "--divider-color": "#2a3140",
    "--success-color": "#56d99a", "--warning-color": "#f3b94f", "--error-color": "#f0736a", "--text-primary-color": "#0a0d13",
  },
};

class IntexPoolCard extends LitElement {
  static properties = { _config: { state: true } };

  // Fix 5 — busy set to guard double-taps
  _busy = new Set();

  // Feature 2 — 5-minute interval handle for stale-age re-render
  _staleTimer = null;

  connectedCallback() {
    super.connectedCallback();
    this._staleTimer = setInterval(() => this.requestUpdate(), 5 * 60 * 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._staleTimer);
    this._staleTimer = null;
  }

  static getStubConfig(hass) {
    return { ...detectEntities(hass) };
  }

  static getConfigForm() {
    const ent = (d) => ({ selector: { entity: { domain: d, integration: "intex_pool" } } });
    const any = (d) => ({ selector: { entity: { domain: d } } });
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "variant", selector: { select: { mode: "dropdown", options: [
          { value: "auto", label: "Auto (follow Home Assistant theme)" },
          { value: "light", label: "Light" },
          { value: "dark", label: "Dark" },
          { value: "ocean", label: "Ocean (dark teal)" },
          { value: "midnight", label: "Midnight (deep dark)" },
        ] } } },
        // Fix 8 — unique name keys on expandable sections
        { type: "expandable", name: "water_chemistry", title: "Water chemistry", schema: [
          { name: "ph_sensor", ...ent("sensor") }, { name: "orp_sensor", ...ent("sensor") },
          { name: "fc_sensor", ...ent("sensor") }, { name: "sensor_temp", ...ent("sensor") },
          { name: "battery", ...ent("sensor") }, { name: "refresh_button", ...ent("button") },
          { name: "orp_trend", ...ent("sensor") }, { name: "last_measurement", ...ent("sensor") },
        ] },
        // Fix 4 — removed pump_power / pump_energy
        { type: "expandable", name: "salt_system", title: "Saltwater system", schema: [
          { name: "power_switch", ...ent("switch") }, { name: "chlorination_switch", ...ent("switch") },
          { name: "salinity", ...ent("sensor") }, { name: "salt_status", ...ent("sensor") },
          { name: "salt_alarm", ...ent("sensor") }, { name: "salt_temp", ...ent("sensor") },
          { name: "schedules_sensor", ...ent("sensor") },
        ] },
        { type: "expandable", name: "pump", title: "Sand filter pump (any brand)", schema: [
          { name: "pump_switch", ...any("switch") },
          { name: "pump_schedules_sensor", ...ent("sensor") },
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
    return 3;
  }
  getGridOptions() {
    return { rows: 3, columns: 12, min_columns: 6 };
  }

  _paletteStyle() {
    const palette = VARIANTS[this._config?.variant];
    if (!palette) return "";  // "auto" / unset -> inherit HA theme
    return Object.entries(palette).map(([k, v]) => `${k}:${v}`).join(";");
  }

  _roles() {
    return { ...detectEntities(this._hass), ...this._config };
  }
  _st(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }
  _has(id) {
    const s = this._st(id);
    return Boolean(s) && s.state !== "unavailable";
  }
  _num(id) {
    const s = this._st(id);
    const v = s ? parseFloat(s.state) : NaN;
    return Number.isFinite(v) ? v : null;
  }
  _on(id) {
    return this._st(id)?.state === "on";
  }
  _fmt(s) {
    try {
      return this._hass.formatEntityState(s);
    } catch (e) {
      return s.state;
    }
  }
  _moreInfo(id) {
    if (id) fireEvent(this, "hass-more-info", { entityId: id });
  }

  // Fix 5 — promise handling + double-tap guard
  _toggle(id) {
    if (this._busy.has(id)) return;
    this._busy.add(id);
    this.requestUpdate();
    this._hass.callService("homeassistant", "toggle", { entity_id: id })
      .catch((err) => {
        console.error("[intex-pool-card] toggle failed:", err);
        fireEvent(this, "hass-notification", { message: `Toggle failed: ${err?.message ?? err}` });
      })
      .finally(() => {
        this._busy.delete(id);
        this.requestUpdate();
      });
  }
  _press(id) {
    if (this._busy.has(id)) return;
    this._busy.add(id);
    this.requestUpdate();
    this._hass.callService("button", "press", { entity_id: id })
      .catch((err) => {
        console.error("[intex-pool-card] press failed:", err);
        fireEvent(this, "hass-notification", { message: `Press failed: ${err?.message ?? err}` });
      })
      .finally(() => {
        this._busy.delete(id);
        this.requestUpdate();
      });
  }

  // Fix 3 — resolve indicator color for a given indicator entity id.
  // Returns "good", "warn", "bad", or null when no indicator is present/valid.
  _indicatorCls(indicatorId) {
    if (!indicatorId) return null;
    const s = this._st(indicatorId);
    if (!s || s.state === "unavailable") return null;
    const st = s.state.toLowerCase();
    if (st === "green") return "good";
    if (st === "yellow") return "warn";
    if (st === "red") return "bad";
    // ORP indicator's fourth state: the device says salt/water conditions
    // invalidate the reading — that's a problem, never "looks fine".
    if (st === "saltwater_abnormal") return "bad";
    return null; // "off" / unknown -> fall back to the numeric heuristic
  }

  // Feature 2 — human-readable relative age from an ISO datetime entity state.
  // Returns e.g. "5h", "3d", "45m". Returns null when id is absent/unavailable
  // or state is not a parseable date.
  _ageText(id) {
    if (!id) return null;
    const s = this._st(id);
    if (!s || s.state === "unavailable" || s.state === "unknown") return null;
    const ts = Date.parse(s.state);
    if (!Number.isFinite(ts)) return null;
    const diffMs = Date.now() - ts;
    if (diffMs < 0) return null;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins}m`;
    const hours = Math.floor(mins / 60);
    if (hours < 48) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
  }

  // Feature 2 — amber stale-badge shown next to the battery mini-button when
  // last_measurement is older than 3 hours. Returns nothing when fresh/absent.
  _staleBadge(id) {
    if (!id) return nothing;
    const s = this._st(id);
    if (!s || s.state === "unavailable" || s.state === "unknown") return nothing;
    const ts = Date.parse(s.state);
    if (!Number.isFinite(ts)) return nothing;
    const diffMs = Date.now() - ts;
    if (diffMs < 3 * 60 * 60 * 1000) return nothing; // fresh — no badge
    const age = this._ageText(id) ?? "?";
    const title = `Last measurement: ${age} ago — readings may be outdated`;
    return html`<span class="stale-badge" title=${title} aria-label=${title}>
      <span class="stale-dot"></span><span class="stale-age">${age}</span>
    </span>`;
  }

  // a compact metric tile: big value, small label, in-range bar
  // Fix 3 — accepts optional indicatorId; Fix 6 — aria-label
  // Feature 1 — accepts optional orpTrendId for ORP trend superscript marker
  _tile(id, { label, digits = 0, lo, hi, unit, indicatorId, orpTrendId } = {}) {
    const s = this._st(id);
    if (!s) return nothing;
    const v = this._num(id);
    const val = v == null ? (s.state ?? "—") : v.toFixed(digits);
    const numericOk = v == null ? null : (lo == null || v >= lo) && (hi == null || v <= hi);
    // Indicator overrides numeric heuristic when present.
    const indCls = this._indicatorCls(indicatorId);
    let cls;
    if (indCls !== null) {
      cls = indCls; // "good" / "warn" / "bad"
    } else {
      cls = numericOk === null ? "" : numericOk ? "good" : "warn";
    }
    const ariaLabel = `${label}: ${val}${unit ? " " + unit : ""}`;

    // Feature 1 — ORP trend superscript: ▴ with opacity by level (none/unavailable = hidden)
    let trendMarker = nothing;
    if (orpTrendId) {
      const ts = this._st(orpTrendId);
      if (ts && ts.state !== "unavailable" && ts.state !== "unknown") {
        const lvl = ts.state.toLowerCase();
        const opacityMap = { low: 0.45, mid: 0.7, high: 1.0 };
        const opacity = opacityMap[lvl];
        if (opacity != null) {
          const trendLabel = `ORP trend: ${lvl}`;
          trendMarker = html`<sup class="orp-trend" style="opacity:${opacity}"
            title=${trendLabel} aria-label=${trendLabel}>▴</sup>`;
        }
      }
    }

    return html`
      <button class="tile" aria-label=${ariaLabel} @click=${() => this._moreInfo(id)}>
        <div class="v">${val}${unit ? html`<span class="u">${unit}</span>` : nothing}${trendMarker}</div>
        <div class="l">${label}</div>
        <div class="bar ${cls}"></div>
      </button>`;
  }

  _ctrl(id, icon, label, press = false) {
    if (!this._has(id)) return nothing;
    const on = press ? false : this._on(id);
    const busy = this._busy.has(id);
    // Fix 5 — disabled while busy; Fix 6 — aria-pressed
    return html`
      <button class="pill ${on ? "on" : ""} ${busy ? "busy" : ""}"
        aria-label=${label} aria-pressed=${on}
        ?disabled=${busy}
        @click=${() => (press ? this._press(id) : this._toggle(id))}>
        <ha-icon icon=${icon}></ha-icon><span>${label}</span>
      </button>`;
  }

  _statusPill(c) {
    const alarm = this._st(c.salt_alarm);
    // e93 = standby, not a real fault — don't show it as an alarm.
    if (alarm && !["normal", "unknown", "unavailable", "e93"].includes(alarm.state))
      return html`<span class="status alarm">${this._fmt(alarm)}</span>`;
    const st = this._st(c.salt_status);
    if (st && this._has(c.salt_status))
      return html`<span class="status ok">${this._fmt(st)}</span>`;
    // Salt entities configured but no live data (device unreachable): never
    // show a reassuring green OK — that hid a 4-day outage. Grey Offline pill.
    if (c.salt_alarm || c.salt_status)
      return html`<span class="status off">Offline</span>`;
    return html`<span class="status ok">OK</span>`;
  }

  render() {
    if (!this._hass || !this._config) return nothing;
    const c = this._roles();
    const tempId = this._has(c.sensor_temp) ? c.sensor_temp : c.salt_temp;

    const tiles = [
      this._has(c.ph_sensor)
        ? this._tile(c.ph_sensor, { label: "pH", digits: 1, lo: 7.2, hi: 7.6, indicatorId: c.ph_indicator })
        : nothing,
      this._has(c.orp_sensor)
        ? this._tile(c.orp_sensor, { label: "ORP", unit: "mV", lo: 650, hi: 750, indicatorId: c.orp_indicator, orpTrendId: c.orp_trend })
        : nothing,
      // Fix 2 — free-chlorine tile
      this._has(c.fc_sensor)
        ? this._tile(c.fc_sensor, { label: "Cl₂", digits: 2, unit: "ppm", lo: 1, hi: 3 })
        : nothing,
      this._has(tempId) ? this._tile(tempId, { label: "Temp", digits: 1, unit: "°", lo: 10, hi: 35 }) : nothing,
      this._has(c.salinity) ? this._tile(c.salinity, { label: "Salt", lo: 800, hi: 1800 }) : nothing,
    ].filter((t) => t !== nothing);

    const ctrls = [
      this._ctrl(c.power_switch, "mdi:power", "Power"),
      this._ctrl(c.chlorination_switch, "mdi:flash", "Chlorine"),
      this._ctrl(c.pump_switch, "mdi:water-pump", "Pump"),
    ].filter((x) => x !== nothing);

    const hasBattery = this._has(c.battery);
    const hasRefresh = this._has(c.refresh_button);
    const schedules = scheduleGroups(this._hass, c);
    const empty = tiles.length === 0 && ctrls.length === 0 && schedules.length === 0;

    return html`
      <ha-card style=${this._paletteStyle()}>
        <div class="head">
          <ha-icon class="logo" icon="mdi:pool"></ha-icon>
          <span class="title">${this._config.title ?? "Pool"}</span>
          ${this._statusPill(c)}
        </div>
        ${empty
          ? html`<div class="empty">No pool devices. Edit the card to select entities.</div>`
          : html`
            ${tiles.length ? html`<div class="metrics">${tiles}</div>` : nothing}
            ${ctrls.length || hasBattery || hasRefresh
              ? html`<div class="ctrls">
                  ${ctrls}
                  <span class="spacer"></span>
                  ${hasBattery
                    ? html`<button class="mini" aria-label="Battery"
                        @click=${() => this._moreInfo(c.battery)} title="Battery">
                        <ha-icon icon="mdi:battery"></ha-icon>${this._num(c.battery) ?? "?"}%</button>`
                    : nothing}
                  ${this._staleBadge(c.last_measurement)}
                  ${hasRefresh
                    ? html`<button class="mini" @click=${() => this._press(c.refresh_button)} title="Refresh measurement">
                        <ha-icon icon="mdi:refresh"></ha-icon></button>`
                    : nothing}
                </div>`
              : nothing}
            ${this._scheduleSection(schedules)}`}
      </ha-card>`;
  }

  _scheduleSection(groups) {
    if (!groups.length) return nothing;
    return html`
      ${groups.map((group) => html`
        <div class="sched" @click=${() => this._moreInfo(group.entityId)}>
          <div class="sched-head">
            <ha-icon icon="mdi:calendar-clock"></ha-icon><span>${group.label}</span>
            <span class="sched-count">${group.schedules.length}</span>
          </div>
          ${group.schedules.map((schedule) => html`
            <div class="sched-row">${schedule}</div>
          `)}
        </div>
      `)}`;
  }

  static styles = css`
    ha-card { padding: 12px 14px; }
    .head { display: flex; align-items: center; gap: 8px; }
    .logo {
      --mdc-icon-size: 22px; color: var(--text-primary-color, #fff);
      background: var(--primary-color); border-radius: 9px; padding: 4px;
      box-sizing: content-box; width: 22px; height: 22px;
    }
    .title { font-size: 1.05rem; font-weight: 600; flex: 1; letter-spacing: .01em; }
    .status {
      font-size: .7rem; font-weight: 600; padding: 3px 9px; border-radius: 999px;
      color: var(--text-primary-color, #fff); white-space: nowrap; max-width: 50%;
      overflow: hidden; text-overflow: ellipsis;
    }
    .status.ok { background: var(--success-color, #2e9e5b); }
    .status.warn { background: var(--warning-color, #f5a300); }
    .status.alarm { background: var(--error-color, #db4437); }
    .status.off { background: var(--disabled-text-color, #757575); }

    .metrics {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(56px, 1fr));
      gap: 6px; margin-top: 12px;
    }
    .tile {
      position: relative; border: none; cursor: pointer; padding: 9px 4px 8px;
      border-radius: 13px; background: var(--secondary-background-color);
      color: var(--primary-text-color); text-align: center; overflow: hidden;
      transition: transform .12s ease;
    }
    .tile:hover { transform: translateY(-1px); }
    .tile .v { font-size: 1.12rem; font-weight: 700; line-height: 1.1; }
    .tile .v .u { font-size: .62rem; font-weight: 600; margin-left: 1px; opacity: .65; }
    .tile .l {
      font-size: .6rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: .06em; color: var(--secondary-text-color); margin-top: 2px;
    }
    .tile .bar { position: absolute; left: 22%; right: 22%; bottom: 0; height: 3px;
      border-radius: 3px 3px 0 0; background: transparent; }
    .tile .bar.good { background: var(--success-color, #2e9e5b); }
    .tile .bar.warn { background: var(--warning-color, #f5a300); }
    .tile .bar.bad  { background: var(--error-color, #db4437); }

    /* Feature 1 — ORP trend superscript marker */
    .orp-trend {
      font-size: .55rem; font-weight: 700; margin-left: 2px;
      vertical-align: super; line-height: 1; color: var(--primary-color);
      transition: opacity .2s;
    }

    .ctrls { display: flex; align-items: center; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
    .spacer { flex: 1; }
    .pill {
      display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
      padding: 6px 12px 6px 9px; border-radius: 999px; font-size: .8rem; font-weight: 600;
      border: 1.5px solid var(--divider-color); background: var(--card-background-color);
      color: var(--primary-text-color); transition: background .18s, color .18s, border-color .18s;
    }
    .pill ha-icon { --mdc-icon-size: 18px; }
    .pill.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
    .pill.busy, .pill:disabled { opacity: .45; cursor: not-allowed; pointer-events: none; }
    .mini {
      display: inline-flex; align-items: center; gap: 3px; cursor: pointer; border: none;
      background: none; color: var(--secondary-text-color); font-size: .78rem; font-weight: 600; padding: 4px;
    }
    .mini ha-icon { --mdc-icon-size: 17px; }

    /* Feature 2 — stale-measurement badge */
    .stale-badge {
      display: inline-flex; align-items: center; gap: 3px;
      color: var(--warning-color, #f5a300); font-size: .72rem; font-weight: 600;
    }
    .stale-dot {
      display: inline-block; width: 6px; height: 6px; border-radius: 50%;
      background: var(--warning-color, #f5a300); flex-shrink: 0;
    }
    .stale-age { line-height: 1; }

    .sched { margin-top: 12px; padding-top: 9px; border-top: 1px solid var(--divider-color); cursor: pointer; }
    .sched-head { display: flex; align-items: center; gap: 6px; font-size: .72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: .05em; color: var(--secondary-text-color); margin-bottom: 5px; }
    .sched-head ha-icon { --mdc-icon-size: 16px; }
    .sched-count { margin-left: auto; background: var(--secondary-background-color);
      border-radius: 999px; padding: 1px 9px; color: var(--primary-text-color); }
    .sched-row { font-size: .82rem; line-height: 1.5; padding-left: 22px; color: var(--primary-text-color); }
    .empty { padding: 14px 2px; color: var(--secondary-text-color); text-align: center; font-size: .85rem; }
    @media (prefers-reduced-motion: reduce) { .tile, .pill { transition: none; } }
  `;
}

function fireEvent(node, type, detail) {
  const ev = new Event(type, { bubbles: true, composed: true });
  ev.detail = detail;
  node.dispatchEvent(ev);
}

if (!customElements.get("intex-pool-card")) {
  customElements.define("intex-pool-card", IntexPoolCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "intex-pool-card",
  name: "Intex Pool",
  description: "Compact pool card for chemistry, chlorinator, pump, and schedules.",
  preview: true,
  documentationURL: "https://github.com/Hovborg/intex-pool",
  getEntitySuggestion: entitySuggestion,
});

console.info(`%c INTEX-POOL-CARD %c v${CARD_VERSION} `,
  "color:#fff;background:#0288d1;font-weight:700;border-radius:3px 0 0 3px;padding:2px 4px",
  "color:#0288d1;background:#fff;border-radius:0 3px 3px 0;padding:2px 4px");
