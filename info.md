# Intex Pool

Native Home Assistant integration for **Intex / AGP (Tuya-based) pool equipment** + an
adaptive dashboard card. UI setup, no MQTT, no YAML.

Works with any combination of:

- 💧 **Water quality sensor** (cloud) — pH, ORP, free chlorine, temperature, battery, writable targets
- 🧂 **Saltwater system** (local) — power, chlorine production, salinity, self-clean, status/alarm
- 🌀 **Sand filter pump** — a Tuya pump **or any existing HA switch** (any brand: Shelly, Zigbee, …)

Includes a self-loading `custom:intex-pool-card` that shows only the sections for the gear
you actually have.

See the [README](https://github.com/Hovborg/intex-pool) for setup details.
