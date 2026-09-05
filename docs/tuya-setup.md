# Connect an Intex Water Analyzer or local pool device

The Water Analyzer uses the Tuya developer cloud. Local Tuya access is for the
saltwater system and pump. Installing Home Assistant's built-in Tuya integration
is not a prerequisite and does not supply this integration's credentials.

## Water Analyzer (WA510 / supported AGP water sensor)

1. Check which app currently owns the device. The supported developer-project
   account-linking route uses **Smart Life** or **Tuya Smart**. If an Intex Link
   account cannot scan the project's authorization QR code, do not substitute
   the Intex account password for a developer secret.
2. If you choose to move the device, record existing schedules and paired-device
   relationships first. Follow the model's manual to remove it from the current
   app, enter Wi-Fi pairing mode, and add it to Smart Life/Tuya Smart. Pairing
   buttons differ by model. Moving a device rotates its local key; preservation
   of analyzer-to-chlorinator control after moving apps has not been verified by
   this project. Check that behavior before relying on it.
3. Create a **Smart Home** project in the [Tuya developer platform](https://iot.tuya.com/).
   Confirm **IoT Core** is active. In **Devices → Link App Account**, scan the QR
   with the app that owns the device. Wait for authorization to propagate and
   confirm the analyzer appears under **All Devices** in that project.
4. In **Settings → Devices & services → Add integration → Intex Pool**, enter the
   project's credentials below and choose the analyzer under **Water sensor**.
   To change an existing entry, use **Reconfigure**.

| Integration field | Value to use |
| --- | --- |
| Access ID | The cloud project's Access ID / Client ID |
| Access secret | The same project's Access Secret / Client Secret |
| Region | Exact project data center: `eu` Central Europe, `eu-w` Western Europe, `us` Western America, `us-e` Eastern America, `cn` China, `in` India, `sg` Singapore |
| Device ID (manual sensor setup) | The analyzer's ID under All Devices in that linked project |

If discovery is empty, check the project, linked app account, exact region and
IoT Core authorization before retrying. Manual analyzer setup still requires
cloud access; it cannot bypass missing project permissions or an expired trial.
Keep Access Secret, local keys and TinyTuya `devices.json` private.

## Local saltwater system / Tuya pump

Use cloud discovery to retrieve device details, or choose manual setup and use
the device ID and current local key from your linked project/TinyTuya wizard.
The IP is the device's **LAN address from your router's DHCP lease list**, not
the app/cloud's public internet address. Home Assistant must be able to reach it.

Starting with **0.21.2**, protocol **auto** tries 3.4, 3.5, 3.3 and 3.1, then
stores the version that actually answered. Earlier releases could mistake a
protocol mismatch for a bad key; the SX2100 reporter in
[issue #18](https://github.com/Hovborg/intex-pool/issues/18) confirmed explicit
**3.5** worked. On current versions you can still select the version reported
by a LAN scan. A failed connection is never accepted as credential validation.

## Refreshing measurements

A separate Water Analyzer receives its cloud refresh command. When the cloud
sensor and local saltwater system are configured with the **same device ID**,
refresh uses the saltwater system's local **Re-test now** action (DP 107).
Cloud-only saltwater properties reporting `retest_switch` use that property.
A failed command leaves the repair open for retry. A successful command only
confirms delivery; check **Last measurement** and the reported values to verify
a new reading actually arrived.

Setup context and user reports: [#13](https://github.com/Hovborg/intex-pool/issues/13),
[#18](https://github.com/Hovborg/intex-pool/issues/18),
[#20](https://github.com/Hovborg/intex-pool/issues/20).
