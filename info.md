# Intex Pool

Water readings, saltwater controls and your pump in one Home Assistant integration,
with its own adaptive dashboard card. Set up and edit through the UI; YAML is optional.

- **Water Analyzer:** pH, ORP, free-chlorine reference, temperature and battery through Tuya developer-cloud access.
- **Supported Tuya saltwater system or pump:** local LAN control, plus cloud schedules when configured.
- **Existing HA pump switch:** link a switch from Shelly, Zigbee or another integration without a Tuya account for that path.
- **Saltwater relay:** manual power control from the card using an existing HA switch.

## After downloading

1. Restart Home Assistant.
2. Open **Settings → Devices & services → Add integration → Intex Pool**.
3. Set up Tuya access, or choose manual setup to link an existing pump switch.
4. Fully reload the browser or Companion App, then **Add card → Intex Pool** on your dashboard.

The integration must be configured and loaded before the card is available.
There is no separate frontend download. For updates, restart HA and reload the frontend again.

[Installation guide](https://github.com/Hovborg/intex-pool/blob/main/docs/installation.md) ·
[Tuya setup](https://github.com/Hovborg/intex-pool/blob/main/docs/tuya-setup.md) ·
[Dashboard guide](https://github.com/Hovborg/intex-pool/blob/main/docs/dashboard.md) ·
[Troubleshooting](https://github.com/Hovborg/intex-pool/blob/main/docs/troubleshooting.md)

See [supported devices and limitations](https://github.com/Hovborg/intex-pool/blob/main/docs/compatibility.md)
before re-pairing equipment. Tuya cloud access requires an active plan and API authorization;
continued free access is not guaranteed.
