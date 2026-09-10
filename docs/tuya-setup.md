# Connect an Intex Water Analyzer or local pool device

The Water Analyzer uses a Tuya **developer cloud project**. The saltwater
system and a Tuya pump can use local LAN control.

## Do not mix up the two Tuya connections

Home Assistant's built-in **Tuya** integration and **Intex Pool** authenticate
separately:

| Connection | What you enter | What it provides to Intex Pool |
| --- | --- | --- |
| Home Assistant's built-in Tuya integration | Smart Life/Tuya Smart **User Code**, followed by an app QR scan | Nothing. It neither supplies nor validates this integration's developer credentials. |
| Intex Pool cloud setup | A Tuya developer project's **Access ID**, **Access Secret** and exact data-center region | Cloud access to the Water Analyzer, discovery/local keys, and cloud-backed schedules. |

You may install both integrations, but Intex Pool does not depend on the built-in
one. Seeing a device there does not validate the developer project, region or
IoT Core subscription. See Home Assistant's
[official Tuya setup](https://www.home-assistant.io/integrations/tuya/) for its
separate User Code and QR flow.

## Water Analyzer (WA510 / supported AGP water sensor)

### 1. Preserve the current Intex setup before changing apps

First check which mobile app owns each pool device. If the analyzer is already
in Smart Life, leave it paired and continue below.

If it exists only in Intex Link, do not assume that account can be linked to a
developer project. Tuya's documented flow uses **Smart Life** to scan the
project QR code. An Intex login is not an Access ID or Access Secret.

Moving a device from Intex Link to Smart Life is a separate, potentially
disruptive migration:

1. Record every Intex schedule, device link and automatic relationship.
2. Follow the **exact model's** pairing instructions. The clock/timer-button
   method reported in issue 13 was for an AGP pump, not a verified WA510 method.
3. Expect re-pairing to rotate the local key used by local integrations.

**Unknown:** this project has not verified that Water Analyzer-to-chlorinator
control or any other Intex Link automation survives moving one or both devices
to Smart Life. Intex Pool does not migrate or recreate vendor-app relationships.
Test the physical equipment and schedules before relying on them after a move.

### 2. Create and verify the Tuya developer project

1. At the [Tuya Developer Platform](https://iot.tuya.com/), open **Cloud →
   Development → Create Cloud Project** and choose **Smart Home**.
2. Choose the data center serving the Smart Life account's registered region.
   Find it in the app under **Me → Settings → Account and Security → Region**;
   see Tuya's [Smart Home guide](https://developer.tuya.com/en/docs/iot/Platform_Configuration_smarthome?id=Kamcgamwoevrx).
3. Authorize the APIs and confirm **IoT Core** is subscribed, authorized for
   this project and active.
4. Under **Devices → Link Tuya App Account → Add App Account**, scan the QR with
   Smart Life and confirm. See Tuya's [Link Devices](https://developer.tuya.com/en/docs/iot/link-devices?id=Ka471nu1sfmkl).
5. In the same data-center view, verify the analyzer under **All Devices**. Then
   copy **Access ID / Client ID** and **Access Secret / Client Secret** from the
   project's **Overview** page.

If IoT Core is **suspended or expired**, renew or subscribe to it and wait until
the portal shows it as active and authorized before retrying discovery. Tuya's
[global error list](https://developer.tuya.com/en/docs/iot/error-code?id=K989ruxx88swc)
identifies `28841002` as an expired cloud plan and `28841102` as an expired API
subscription. After renewal, verify **All Devices** again before retrying.

### 3. Select the exact Intex Pool region

Intex Pool passes the selected region to its pinned TinyTuya cloud client. The
supported values map to Tuya's current API endpoints as follows:

| Intex Pool value | Tuya data center | API endpoint |
| --- | --- | --- |
| `us` | Western America | `https://openapi.tuyaus.com` |
| `us-e` | Eastern America | `https://openapi-ueaz.tuyaus.com` |
| `eu` | Central Europe | `https://openapi.tuyaeu.com` |
| `eu-w` | Western Europe | `https://openapi-weaz.tuyaeu.com` |
| `cn` | China | `https://openapi.tuyacn.com` |
| `in` | India | `https://openapi.tuyain.com` |
| `sg` | Singapore | `https://openapi-sg.iotbing.com` |

`eu` and `eu-w` are distinct, as are `us` and `us-e`. Match the **data center
shown for the project/account link**, not the device's physical location. Tuya
lists the endpoints in its
[official request structure](https://developer.tuya.com/en/docs/iot/api-request?id=Ka4a8uuo1j4t4)
and explains account placement in
[Mappings Between OEM App Accounts and Data Centers](https://developer.tuya.com/en/docs/iot/oem-app-data-center-distributed?id=Kafi0ku9l07qb).

### 4. Add the device to Intex Pool

1. In Home Assistant, open **Settings → Devices & services → Add integration →
   Intex Pool**. For an existing entry, use **Reconfigure**.
2. Enter the developer project's Access ID, Access Secret and exact region from
   the table above.
3. Choose the analyzer under **Water sensor** and finish setup.

Manual Water Analyzer setup needs its **Device ID** from **All Devices** and
still calls Tuya cloud. It cannot bypass a wrong region, unlinked account,
missing permission or expired subscription. For empty discovery, verify **All
Devices**, active IoT Core/API authorization, credentials from the same project,
and the exact region code—in that order.

Since **0.21.3**, setup reports subscription/quota problems separately from
wrong credentials and missing API/device permissions. Discovery checks Tuya's
original responses, including later pages and per-account lookups, so a failed
request cannot silently become an empty or partial device list. Transient token
renewal failures are retried on a later poll. Cloud HTTP calls have a 5-second
connection timeout and 15-second read timeout per request.

Issue #13's reporter later confirmed that access worked after IoT Core renewal
had propagated. That confirms their account recovery; it does not verify
Water Analyzer-to-chlorinator automation after changing mobile apps.

## Local saltwater system / Tuya pump

Cloud discovery can retrieve a local device's ID and current local key. For
manual setup, obtain those values from the linked project or TinyTuya wizard.
The host/IP field is the device's private **LAN address from the router's DHCP
lease list**, not a Tuya cloud address. Home Assistant must be able to reach it.

Starting with **0.21.2**, protocol **auto** tries 3.4, 3.5, 3.3 and 3.1, then
stores the version that actually answered. Earlier releases could mistake a
protocol mismatch for a bad key; the SX2100 reporter in
[issue #18](https://github.com/Hovborg/intex-pool/issues/18) confirmed explicit
**3.5** worked for that device. On current versions you can still select the
version reported by a LAN scan. A failed connection is never accepted as
credential validation.

Keep Access Secret, local keys and TinyTuya `devices.json` private.
Intex Pool's normal debug logging no longer enables TinyTuya's raw debug logger,
which can include credentials. Do not enable or share raw `tinytuya: debug`
output when requesting support.

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
