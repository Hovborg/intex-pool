# Troubleshooting

[Overview](../README.md) · [Installation](installation.md) · [Dashboard guide](dashboard.md) · [Tuya setup](tuya-setup.md)

## Find the right check

| Symptom | Start here |
| --- | --- |
| Intex Pool is missing from Add integration | [Installation and restart steps](installation.md#install-through-hacs) |
| Card is missing or says “Custom element doesn't exist” | [Card resource loading](dashboard.md#card-not-found-or-custom-element-doesnt-exist) |
| Card exists but the pump/control is missing | Check the original switch's state, then [select it in the card](dashboard.md#external-pump-and-saltwater-relays) |
| Wrong pool/device appears in the card | [Override auto-detection and clear unrelated fields](dashboard.md#showing-only-selected-equipment) |
| Cloud setup fails or lists no devices | [Cloud setup](#cloud-setup) below |
| Local controls work but schedules do not | [Schedule access](#local-controls-work-but-schedules-are-missing) |

Start with the path that is failing: Tuya developer cloud, local LAN control,
schedule access, or measurement refresh. They use different credentials and a
successful check on one path does not prove another path works.

## Cloud setup

### Wrong credentials

An **invalid authentication** error means the Tuya cloud rejected the Access ID,
Access Secret, or token. Copy the ID and secret from the same project's Overview
page and verify that Intex Pool uses that project's exact data-center region.

### Missing, expired, or exhausted cloud access

A **subscription** error means the plan or API subscription is missing, expired,
or out of quota. Check the Tuya Developer Platform for the current status of IoT
Core and every API authorized to that project. The integration cannot guarantee
that a trial is renewable or free; the available terms are determined by Tuya.

### Permission error

A **permission** error means the project cannot access a requested device or
API. Check all of the following in the same Tuya project:

1. the Smart Life/Tuya Smart account is linked;
2. the device appears under **All Devices**;
3. the required APIs are authorized; and
4. the project and integration use the same data center.

### Cloud connects but no devices appear

The setup flow reports **no devices** instead of opening an empty picker. Verify
the linked app account and **All Devices** first. Manual Water Analyzer setup is
not a cloud bypass: it still validates the developer credentials, region, and
device ID against Tuya cloud.

## Local saltwater system or Tuya pump

The local setup requires the device ID, current local key, private LAN IP, and a
working protocol version. The IP must be reachable from Home Assistant. Reserve
it in DHCP if possible.

Protocol **auto** tries `3.4`, `3.5`, `3.3`, and `3.1` and stores the first
version that returns a valid status. A connection failure is not accepted as
credential validation. If the device is on another VLAN or subnet, cloud
discovery may find its ID/key while the LAN scan cannot find its IP; use manual
setup or manual reconfiguration and enter the reachable address.

Re-pairing a device rotates its local key. Re-authentication can update the
saltwater key, the Tuya pump key, and the cloud Access Secret. Use
**Reconfigure** instead when the device ID, IP, protocol, device selection, or
pump mode must change.

## Local controls work but schedules are missing

Saltwater and Tuya-pump schedule blobs are read through Tuya cloud. A manual
local-only entry intentionally has no schedule entities. Reconfigure the entry
with working developer-cloud credentials to add them.

If the entry was originally created through cloud discovery without a Water
Analyzer, the integration still stores shared credentials for saltwater/pump
schedules. A temporary cloud failure can make those schedule entities
unavailable while local controls continue working; they retry on the normal
schedule poll without requiring the entry to be recreated.

The Water Analyzer's measurement schedules are read-only. The
`intex_pool.set_schedule` action writes only the saltwater schedule. Edit Tuya
pump schedules through their per-slot Home Assistant entities.

## A schedule action targets the wrong entry

When multiple Intex Pool entries are loaded, include `config_entry_id` in
`intex_pool.set_schedule`, `intex_pool.get_schedule`,
`intex_pool.calibrate`, and `intex_pool.clear_calibration`. Without it, the
action selects the first loaded entry that provides the requested capability.

For `intex_pool.set_schedule`, use `clear: true` to empty a slot. `enable:
false` changes the slot's on/boost byte and can describe a Boost-style cycle; it
does not disable or remove the schedule.

## Refresh was accepted but the values did not change

The refresh button sends the command and immediately requests a new cloud poll.
The analyzer may still be asleep or may not have produced a later sample. Check
**Last measurement** and the raw measurement timestamp before concluding that a
new reading arrived.

When the Water Analyzer and local saltwater system use the same device ID, the
refresh path uses the saltwater system's local Re-test command (`DP107`). A
separate analyzer receives its cloud refresh command. A successful action means
the command was delivered; it does not by itself prove a new measurement.

## Pump auto mode is missing or does not switch the pump

Pump auto mode exists only for an entry that contains both a local saltwater
system and a pump linked as an existing Home Assistant switch. It is not created
for a local Tuya pump, a dashboard-only relay selection, or two devices split
across different integration entries.

The mode follows chlorine production (`DP103`), not the saltwater system's
master power. If that production value is unavailable or invalid, automatic
switching pauses. Restore local communication with the saltwater system and
check the linked switch's own integration before retrying.

## Changed keys or replacement equipment

Use the repair/re-authentication prompt for changed secrets or local keys. Each
local device has its own key field. Use **Settings → Devices & services → Intex
Pool → Reconfigure** to replace devices, change connection details, switch
between a Tuya pump and an existing Home Assistant switch, or remove a device.

In manual reconfiguration, unticked existing devices are retained. Use the
explicit **Remove** checkbox for a device you intend to delete from the entry.

A replacement with a new Tuya device ID creates new HA entity identities. Check
cards and automations that referred to the old equipment; history is not automatically
moved to the new entities. Unchanged devices keep their identities when only their
IP address or local key is updated.

## Reporting a problem

Use the [bug report form](https://github.com/Hovborg/intex-pool/issues/new?template=bug_report.yml).
Include the Intex Pool and Home Assistant versions, model, connection path, exact
error and what you expected. For card problems, include the saved card YAML,
UI/YAML dashboard type, view layout, browser or Companion App, and whether a full
frontend reload changes the result.

Download diagnostics from the integration page and review the file before
sharing it. The integration redacts stored local keys and cloud credentials, but
raw TinyTuya debug output can contain credentials. Do not publish Access IDs,
Access Secrets, local keys, device IDs, private IP addresses, request
signatures, or `devices.json`.

For a device-mapping problem, include the exact model and firmware, the protocol
version, the observed data-point IDs/values before and after one controlled
action, and whether the result came from physical hardware, a Tuya thing model,
or inference.
