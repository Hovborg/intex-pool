"""Tests for the thin tinytuya wrappers (fake tinytuya, no network)."""
import types

import pytest

from custom_components.intex_pool import tuya


class FakeDevice:
    last: "FakeDevice | None" = None

    def __init__(self, dev_id, host, key, version=None):
        FakeDevice.last = self
        self.dev_id, self.host, self.key, self.version = dev_id, host, key, version
        self.persistent = None
        self.timeout = None
        self.set_calls = []
        self._status = {"dps": {"104": True, "109": 1490, "111": 19}}

    def set_socketPersistent(self, v):
        self.persistent = v

    def set_socketTimeout(self, t):
        self.timeout = t

    def status(self):
        return self._status

    def set_value(self, dp, val):
        self.set_calls.append((dp, val))


class FakeCloud:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.requests = []

    def cloudrequest(self, path, post=None):
        self.requests.append((path, post))
        if path.endswith("/shadow/properties"):
            return {"success": True, "result": {"properties": [
                {"code": "PH_Number", "value": 740},
                {"code": "battery_capacity", "value": 97},
                {"code": None, "value": "ignored"},
            ]}}
        return {"success": True, "result": {}}

    def getdevices(self, verbose=False):
        return [
            {"id": "d1", "name": "AGP Salt", "key": "k1", "category": "rs", "product_id": "p1"},
            {"id": "d2", "name": "Other", "local_key": "k2", "category": "dj"},
            {"name": "no-id-skip"},
        ]


def _fake_scan(forcescan, timeout):
    return {"1.2.3.4": {"gwId": "d1", "version": "3.5"}, "5.6.7.8": {"id": "d3"}}


@pytest.fixture
def fake_tinytuya(monkeypatch):
    fake = types.SimpleNamespace(Device=FakeDevice, Cloud=FakeCloud, deviceScan=_fake_scan)
    monkeypatch.setattr(tuya, "tinytuya", fake)
    return fake


def test_list_devices_returns_keys(fake_tinytuya):
    devs = tuya.CloudClient("eu", "id", "secret").list_devices()
    by_id = {d["id"]: d for d in devs}
    assert set(by_id) == {"d1", "d2"}  # entry without id dropped
    assert by_id["d1"]["key"] == "k1"
    assert by_id["d2"]["key"] == "k2"  # local_key fallback


def test_scan_lan_maps_id_to_ip_version(fake_tinytuya):
    m = tuya.scan_lan(1)
    assert m["d1"] == ("1.2.3.4", 3.5)
    assert m["d3"] == ("5.6.7.8", None)  # missing version -> None


def test_local_status_uses_fresh_nonpersistent_socket(fake_tinytuya):
    client = tuya.LocalClient("dev", "key", "1.2.3.4", version=3.5)
    dps = client.status()
    assert dps == {"104": True, "109": 1490, "111": 19}
    assert FakeDevice.last.persistent is False
    assert FakeDevice.last.timeout == 5
    assert FakeDevice.last.version == 3.5


def test_local_status_bad_response_raises(fake_tinytuya, monkeypatch):
    client = tuya.LocalClient("dev", "key", "1.2.3.4")
    monkeypatch.setattr(FakeDevice, "status", lambda self: "Error 905")
    with pytest.raises(tuya.TuyaError):
        client.status()


def test_local_set_value_casts_dp_to_int(fake_tinytuya):
    client = tuya.LocalClient("dev", "key", "1.2.3.4", version=3.5)
    client.set_value("104", True)
    assert FakeDevice.last.set_calls == [(104, True)]


def test_set_version(fake_tinytuya):
    client = tuya.LocalClient("dev", "key", "1.2.3.4", version=3.3)
    client.set_version(3.5)
    assert client.version == 3.5


def test_cloud_properties_parses_codes(fake_tinytuya):
    client = tuya.CloudClient("eu", "id", "secret")
    props = client.properties("devid")
    assert props == {"PH_Number": 740, "battery_capacity": 97}  # None-code dropped


def test_cloud_issue_builds_json_body(fake_tinytuya):
    client = tuya.CloudClient("eu", "id", "secret")
    client.issue("devid", "ph_set", 750)
    path, post = client._cloud.requests[-1]
    assert path == "/v2.0/cloud/thing/devid/shadow/properties/issue"
    assert post == {"properties": '{"ph_set": 750}'}


def test_cloud_failure_raises(fake_tinytuya, monkeypatch):
    client = tuya.CloudClient("eu", "id", "secret")
    monkeypatch.setattr(FakeCloud, "cloudrequest", lambda self, p, post=None: {"success": False})
    with pytest.raises(tuya.TuyaError):
        client.properties("devid")


def test_local_status_bad_key_raises_auth(fake_tinytuya, monkeypatch):
    # tinytuya Err 914 = "Check device key or version" -> auth error -> reauth
    client = tuya.LocalClient("dev", "key", "1.2.3.4")
    monkeypatch.setattr(FakeDevice, "status", lambda self: {"Error": "...", "Err": "914"})
    with pytest.raises(tuya.TuyaAuthError):
        client.status()


def test_local_status_transport_error_is_not_auth(fake_tinytuya, monkeypatch):
    client = tuya.LocalClient("dev", "key", "1.2.3.4")
    monkeypatch.setattr(FakeDevice, "status", lambda self: {"Error": "offline", "Err": "905"})
    with pytest.raises(tuya.TuyaError) as exc:
        client.status()
    assert not isinstance(exc.value, tuya.TuyaAuthError)


def test_cloud_auth_code_raises_auth(fake_tinytuya, monkeypatch):
    client = tuya.CloudClient("eu", "id", "secret")
    # code 1004 = sign invalid (bad access secret) -> auth error
    monkeypatch.setattr(
        FakeCloud, "cloudrequest", lambda self, p, post=None: {"success": False, "code": 1004}
    )
    with pytest.raises(tuya.TuyaAuthError):
        client.properties("devid")
