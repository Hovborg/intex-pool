"""Exercise pinned TinyTuya with synthetic HTTP replies, never live credentials."""
import json
from unittest.mock import patch

import pytest
import requests
import tinytuya

from custom_components.intex_pool import tuya

TOKEN = {"success": True, "result": {"access_token": "synthetic-token"}}
PROPERTIES = {"success": True, "result": {"properties": [{"code": "PH_Number", "value": 740}]}}


def response(body):
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps(body).encode()
    return result


@pytest.fixture(autouse=True)
def no_unexpected_transport(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network request")
    monkeypatch.setattr(requests, "request", blocked)


@pytest.mark.parametrize("code,error", [
    (500, tuya.TuyaError), (1004, tuya.TuyaAuthError),
    (28841102, tuya.TuyaSubscriptionError), (1106, tuya.TuyaPermissionError),
])
def test_token_failure_preserves_cause_without_remote_secrets(code, error):
    payload = {"success": False, "code": code, "msg": "private-signature-do-not-log"}
    with patch("requests.get", return_value=response(payload)), pytest.raises(error) as exc:
        tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
    assert type(exc.value) is error
    assert "private-signature" not in str(exc.value)
    assert str(code) in str(exc.value)


def test_failed_token_refresh_recovers_on_next_poll():
    sequence = [TOKEN, {"success": False, "code": 1011, "msg": "token invalid"},
                {"success": False, "code": 500, "msg": "temporarily unavailable"},
                TOKEN, PROPERTIES]
    with patch("requests.get", side_effect=[response(item) for item in sequence]) as get:
        client = tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
        with pytest.raises(tuya.TuyaError):
            client.properties("synthetic-device")
        assert client.properties("synthetic-device")["PH_Number"] == 740
        assert get.call_count == 5


def test_token_refresh_uses_code_instead_of_message():
    sequence = [TOKEN, {"success": False, "code": 1010, "msg": "token is expired"}, TOKEN, PROPERTIES]
    with patch("requests.get", side_effect=[response(item) for item in sequence]) as get:
        client = tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
        assert client.properties("synthetic-device")["PH_Number"] == 740
        assert get.call_count == 4


def test_uid_lookup_failure_cannot_return_partial_device_list():
    sequence = [TOKEN, {"success": True, "result": {"devices": [
        {"id": "synthetic-device", "uid": "synthetic-user", "name": "Pump", "local_key": ""},
    ]}}, {"success": False, "code": 28841105, "msg": "not authorized"}]
    with patch("requests.get", side_effect=[response(item) for item in sequence]):
        client = tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
        with pytest.raises(tuya.TuyaPermissionError):
            client.list_devices()


@pytest.mark.parametrize("payload", [
    {"success": True}, {"success": True, "result": None},
    {"success": True, "result": {}}, {"success": True, "result": {"properties": None}},
])
def test_malformed_properties_are_not_success(payload):
    with patch("requests.get", side_effect=[response(TOKEN), response(payload)]):
        client = tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
        with pytest.raises(tuya.TuyaError):
            client.properties("synthetic-device")


def test_cloud_http_timeouts_do_not_change_global_requests():
    original = tinytuya.Cloud._tuyaplatform.__globals__["requests"]
    with (
        patch("requests.get", side_effect=[response(TOKEN), response(PROPERTIES)]) as get,
        patch("requests.request", return_value=response({"success": True, "result": {}})) as post,
    ):
        client = tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")
        client.properties("synthetic-device")
        client.issue("synthetic-device", "refresh_switch", True)
    assert len(get.call_args_list) == 2
    assert all(call.kwargs["timeout"] == (5, 15) for call in get.call_args_list)
    assert post.call_args.kwargs["timeout"] == (5, 15)
    assert tinytuya.Cloud._tuyaplatform.__globals__["requests"] is original is requests


@pytest.mark.parametrize("result", [None, {}, {"access_token": ""}, {"access_token": 1}])
def test_invalid_token_payload_is_not_accepted(result):
    with (
        patch("requests.get", return_value=response({"success": True, "result": result})),
        pytest.raises(tuya.TuyaError),
    ):
        tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")


def test_string_false_success_does_not_accept_rejected_credentials():
    with (
        patch("requests.get", return_value=response({"success": "false", "code": 1004})),
        pytest.raises(tuya.TuyaAuthError),
    ):
        tuya.CloudClient("eu", "synthetic-id", "synthetic-secret")


@pytest.mark.parametrize("access_id,secret", [("", ""), ("id", " "), (None, "secret")])
def test_missing_credentials_never_read_tinytuya_json(access_id, secret):
    with (
        patch("builtins.open", side_effect=AssertionError("Unexpected credential file read")) as opened,
        pytest.raises(tuya.TuyaAuthError),
    ):
        tuya.CloudClient("eu", access_id, secret)
    opened.assert_not_called()
