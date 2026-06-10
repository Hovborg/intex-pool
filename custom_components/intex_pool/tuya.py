"""Thin, blocking tinytuya wrappers — no Home Assistant imports.

These are plain synchronous callables so the coordinator can run them via
``hass.async_add_executor_job``. They never touch the event loop themselves.

Design notes ported from the proven 01-drift/13-pool-kontrol bridge:
* Local polling uses a FRESH, NON-persistent socket per call. A persistent
  socket was observed to hang and serve stale DP values (dp125/dp127 froze)
  and to swallow commands (dp103 rolled back). A new socket per call fixes it.
* The cloud path uses the thing-model shadow-properties API, which returns
  named typed properties even for the `rs`-category devices that the local /
  sharing paths miss.
"""
from __future__ import annotations

import json
from typing import Any

import tinytuya


class TuyaError(Exception):
    """Raised when a Tuya local/cloud operation fails."""


class TuyaAuthError(TuyaError):
    """Raised when credentials are rejected — a bad local key or cloud secret.

    The coordinators turn this into ``ConfigEntryAuthFailed`` so Home Assistant
    starts a reauth flow (the Intex/Tuya ``local_key`` rotates when the device is
    re-paired in the app, which is the most common cause).
    """


# tinytuya local error code for "Check device key or version".
_LOCAL_AUTH_ERR = {"914"}
# Tuya cloud response codes for bad sign / token / permission (auth, not transport).
_CLOUD_AUTH_CODES = {1004, 1010, 1011, 1100, 1106, 2406, 28841002}


def _check_cloud(resp: Any, what: str) -> None:
    """Raise the right error from a Tuya cloud response (auth vs transport).

    Only the response ``code``/``msg`` fields are quoted — never the full body,
    which can carry request-signature material on auth failures.
    """
    if isinstance(resp, dict) and resp.get("success"):
        return
    if isinstance(resp, dict):
        code = resp.get("code")
        msg = f"{what} failed: code={code} msg={str(resp.get('msg'))[:120]}"
    else:
        code = None
        msg = f"{what} failed: unexpected response ({type(resp).__name__})"
    if code in _CLOUD_AUTH_CODES:
        raise TuyaAuthError(msg)
    raise TuyaError(msg)


def scan_lan(timeout: int = 5) -> dict[str, tuple[str, float | None]]:
    """Broadcast-scan the LAN for Tuya devices -> {device_id: (ip, version)}.

    Lets setup auto-resolve a device's local IP + protocol version so the user
    never has to find or type them.
    """
    found = tinytuya.deviceScan(False, timeout) or {}
    out: dict[str, tuple[str, float | None]] = {}
    for ip, info in found.items():
        gw = info.get("gwId") or info.get("id")
        if gw:
            ver = info.get("version")
            out[gw] = (ip, float(ver) if ver else None)
    return out


class LocalClient:
    """Local LAN access to a single Tuya device via tinytuya."""

    def __init__(self, device_id: str, local_key: str, host: str, version: float = 3.3) -> None:
        self._id = device_id
        self._key = local_key
        self._host = host
        self._version = float(version)

    @property
    def version(self) -> float:
        return self._version

    def set_version(self, version: float) -> None:
        self._version = float(version)

    def _device(self) -> Any:
        dev = tinytuya.Device(self._id, self._host, self._key, version=self._version)
        dev.set_socketPersistent(False)
        dev.set_socketTimeout(5)
        return dev

    def status(self) -> dict[str, Any]:
        """Return the device's DP dict, or raise TuyaError/TuyaAuthError."""
        data = self._device().status()
        if isinstance(data, dict) and "dps" in data:
            return data["dps"]
        self._raise_local("unexpected status response", data)

    def set_value(self, dp: str | int, value: Any) -> None:
        """Set a single DP (fresh dedicated connection, no poll-thread race).

        tinytuya's ``set_value`` does not raise on failure — it returns an error
        dict (offline, bad key, …). Check it so a rejected/undelivered command
        surfaces to the caller instead of silently looking like success.
        """
        resp = self._device().set_value(int(dp), value)
        if isinstance(resp, dict) and resp.get("Err"):
            self._raise_local(f"set dp {dp}", resp)

    def _raise_local(self, what: str, data: Any) -> None:
        """Raise TuyaAuthError/TuyaError from a tinytuya error response.

        Quotes only the Err/Error fields — never the full payload.
        """
        if isinstance(data, dict):
            err = str(data.get("Err") or "")
            msg = f"{what} failed: Err={err or '?'} ({str(data.get('Error'))[:80]})"
        else:
            err = ""
            msg = f"{what} failed: unexpected response ({type(data).__name__})"
        if err in _LOCAL_AUTH_ERR:
            raise TuyaAuthError(msg)
        raise TuyaError(msg)


class CloudClient:
    """Tuya developer-cloud access (for cloud-only devices like the battery sensor)."""

    def __init__(self, region: str, access_id: str, access_secret: str) -> None:
        # NOTE: constructing tinytuya.Cloud performs a blocking token fetch —
        # build this inside an executor job, never on the event loop.
        self._cloud = tinytuya.Cloud(
            apiRegion=region, apiKey=access_id, apiSecret=access_secret
        )

    def list_devices(self) -> list[dict[str, Any]]:
        """List the project's devices with their local keys (for auto-discovery).

        Returns ``[{id, name, key, category, product_id}, ...]`` — the local
        ``key`` lets setup skip manual key extraction entirely.
        """
        devs = self._cloud.getdevices(verbose=False)
        if not isinstance(devs, list):
            _check_cloud(devs, "cloud getdevices")  # raises auth vs transport
            raise TuyaError(f"cloud getdevices failed: {str(devs)[:160]}")
        return [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "key": d.get("key") or d.get("local_key"),
                "category": d.get("category"),
                "product_id": d.get("product_id"),
            }
            for d in devs
            if d.get("id")
        ]

    def properties(self, device_id: str) -> dict[str, Any]:
        """Return {code: value} for the device's thing-model shadow properties.

        Each property's report time (epoch ms) is preserved under the reserved
        ``_times`` key (``{code: epoch_ms}``) — it feeds the "Last measurement"
        sensor and staleness detection. ``_times`` cannot collide with a real
        property code (Tuya codes never start with an underscore).
        """
        path = f"/v2.0/cloud/thing/{device_id}/shadow/properties"
        resp = self._cloud.cloudrequest(path)
        _check_cloud(resp, "cloud properties")
        props = (resp.get("result") or {}).get("properties", []) or []
        out: dict[str, Any] = {p["code"]: p.get("value") for p in props if p.get("code")}
        out["_times"] = {
            p["code"]: p.get("time") for p in props if p.get("code") and p.get("time")
        }
        return out

    def issue(self, device_id: str, code: str, value: Any) -> None:
        """Write a single property via the property-issue API."""
        path = f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue"
        body = {"properties": json.dumps({code: value})}
        resp = self._cloud.cloudrequest(path, post=body)
        _check_cloud(resp, f"cloud issue {code}")
