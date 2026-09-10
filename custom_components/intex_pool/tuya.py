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
from threading import Lock
from types import FunctionType
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


class TuyaSubscriptionError(TuyaError):
    """Cloud plan or API subscription expired; changing credentials cannot fix it."""


class TuyaPermissionError(TuyaError):
    """Project is not authorized for the requested device or API."""


# tinytuya local error code for "Check device key or version".
_LOCAL_AUTH_ERR = {"914"}
# Tuya cloud response codes for bad sign / token / permission (auth, not transport).
_CLOUD_AUTH_CODES = {1001, 1004, 1005}
_CLOUD_TOKEN_CODES = {1002, 1010, 1011, 1012, 1400}
_CLOUD_PERMISSION_CODES = {1106, 2406, 28841105}
_CLOUD_SUBSCRIPTION_CODES = {
    28841001, 28841002, 28841003, 28841004,
    28841101, 28841102, 28841103, 28841104, 28841106,
}


def _cloud_code(resp: Any) -> int | None:
    try:
        return int(resp.get("code")) if isinstance(resp, dict) else None
    except (TypeError, ValueError):
        return None


def _check_cloud(resp: Any, what: str) -> None:
    """Raise the right error from a Tuya cloud response (auth vs transport).

    Only the numeric code is quoted. Remote messages and bodies can contain
    credentials or request-signature material, even on authentication failures.
    """
    if isinstance(resp, dict) and resp.get("success") is True:
        return
    code = _cloud_code(resp)
    msg = f"{what} failed: code={code}" if code is not None else f"{what} failed: invalid response"
    if code in _CLOUD_SUBSCRIPTION_CODES:
        raise TuyaSubscriptionError(msg)
    if code in _CLOUD_PERMISSION_CODES:
        raise TuyaPermissionError(msg)
    if code in _CLOUD_AUTH_CODES:
        raise TuyaAuthError(msg)
    raise TuyaError(msg)


def _bounded_cloud_transport(method):
    """Scope HTTP timeouts to our pinned TinyTuya client, without global patches.

    TinyTuya 1.20 has no transport/timeout injection and calls its module's
    requests object directly. Rebind only this method's globals; retain the
    vendor's signing, query encoding, defaults and closure unchanged.
    """
    requests_module = method.__globals__["requests"]

    class BoundedRequests:
        def __getattr__(self, name):
            return getattr(requests_module, name)

        def get(self, *args, **kwargs):
            kwargs.setdefault("timeout", (5, 15))
            return requests_module.get(*args, **kwargs)

        def request(self, *args, **kwargs):
            kwargs.setdefault("timeout", (5, 15))
            return requests_module.request(*args, **kwargs)

    scoped = FunctionType(
        method.__code__, {**method.__globals__, "requests": BoundedRequests()},
        method.__name__, method.__defaults__, method.__closure__,
    )
    scoped.__kwdefaults__ = method.__kwdefaults__
    return scoped


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
        if not all(isinstance(value, str) and value.strip() for value in (region, access_id, access_secret)):
            # TinyTuya otherwise falls back to a local tinytuya.json account.
            raise TuyaAuthError("cloud credentials missing")
        vendor_transport = getattr(tinytuya.Cloud, "_tuyaplatform", None)
        bounded_transport = _bounded_cloud_transport(vendor_transport) if vendor_transport else None

        class CheckedCloud(tinytuya.Cloud):
            """Preserve errors before TinyTuya reduces token and device replies."""

            def _tuyaplatform(self, *args, **kwargs):
                response = bounded_transport(self, *args, **kwargs)
                uri = str(args[0] if args else kwargs.get("uri", ""))
                is_token_request = uri.lstrip("/").startswith("token")
                if _cloud_code(response) in _CLOUD_TOKEN_CODES and not is_token_request:
                    # TinyTuya only recognizes some English token messages.
                    # Retry one rejected request using the API code instead.
                    self._gettoken()
                    response = bounded_transport(self, *args, **kwargs)
                _check_cloud(response, "cloud request")
                if is_token_request:
                    result = response.get("result")
                    token = result.get("access_token") if isinstance(result, dict) else None
                    if not isinstance(token, str) or not token:
                        raise TuyaError("cloud token unavailable")
                return response

        # NOTE: constructing tinytuya.Cloud performs a blocking token fetch —
        # build this inside an executor job, never on the event loop.
        self._cloud = CheckedCloud(
            apiRegion=region, apiKey=access_id, apiSecret=access_secret
        )
        # Raw token failures are classified above. An absent token alone is
        # not evidence of invalid credentials, and .error may contain secrets.
        if not isinstance(getattr(self._cloud, "token", None), str) or not self._cloud.token:
            raise TuyaError("cloud token unavailable")
        # Sensor and schedule coordinators share this client but run their
        # blocking work in separate executor threads. tinytuya.Cloud mutates
        # request/signature state, so overlapping calls can return ``None``.
        self._request_lock = Lock()

    def _request(self, path: str, post: dict[str, Any] | None = None) -> Any:
        """Serialize access to the shared, stateful tinytuya cloud client."""
        with self._request_lock:
            self._ensure_token()
            return self._cloud.cloudrequest(path, post=post)

    def _ensure_token(self) -> None:
        """Retry a failed token renewal on the next poll, under the request lock."""
        if not isinstance(getattr(self._cloud, "token", None), str) or not self._cloud.token:
            self._cloud._gettoken()
            if not isinstance(getattr(self._cloud, "token", None), str) or not self._cloud.token:
                raise TuyaError("cloud token unavailable")

    def list_devices(self) -> list[dict[str, Any]]:
        """List the project's devices with their local keys (for auto-discovery).

        Returns ``[{id, name, key, category, product_id}, ...]`` — the local
        ``key`` lets setup skip manual key extraction entirely.
        """
        # The non-verbose TinyTuya list drops success/code/msg, making an
        # expired IoT Core plan indistinguishable from an empty project (#13).
        with self._request_lock:
            self._ensure_token()
            response = self._cloud.getdevices(verbose=True)
        _check_cloud(response, "cloud getdevices")
        devs = response.get("result")
        if not isinstance(devs, list):
            raise TuyaError("cloud getdevices failed: expected a device list")
        return [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "key": d.get("key") or d.get("local_key"),
                "category": d.get("category"),
                "product_id": d.get("product_id"),
            }
            for d in devs
            if isinstance(d, dict) and d.get("id")
        ]

    def properties(self, device_id: str) -> dict[str, Any]:
        """Return {code: value} for the device's thing-model shadow properties.

        Each property's report time (epoch ms) is preserved under the reserved
        ``_times`` key (``{code: epoch_ms}``) — it feeds the "Last measurement"
        sensor and staleness detection. ``_times`` cannot collide with a real
        property code (Tuya codes never start with an underscore).
        """
        path = f"/v2.0/cloud/thing/{device_id}/shadow/properties"
        resp = self._request(path)
        _check_cloud(resp, "cloud properties")
        result = resp.get("result")
        props = result.get("properties") if isinstance(result, dict) else None
        if not isinstance(props, list) or any(not isinstance(p, dict) for p in props):
            raise TuyaError("cloud properties failed: expected a properties list")
        out: dict[str, Any] = {p["code"]: p.get("value") for p in props if p.get("code")}
        out["_times"] = {
            p["code"]: p.get("time") for p in props if p.get("code") and p.get("time")
        }
        return out

    def issue(self, device_id: str, code: str, value: Any) -> None:
        """Write a single property via the property-issue API."""
        path = f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue"
        body = {"properties": json.dumps({code: value})}
        resp = self._request(path, post=body)
        _check_cloud(resp, f"cloud issue {code}")
