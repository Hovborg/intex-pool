"""Pytest config: make the repo importable and enable custom integrations."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the intex_pool custom integration in all tests."""
    yield


@pytest.fixture
def mock_tinytuya(monkeypatch):
    """Patch tinytuya with offline fakes so flow + entry setup need no network."""
    import types

    from custom_components.intex_pool import tuya

    class FakeDevice:
        def __init__(self, *a, **k):
            pass

        def set_socketPersistent(self, v):
            pass

        def set_socketTimeout(self, t):
            pass

        def status(self):
            return {"dps": {
                "103": False, "104": True, "105": 10, "108": 4, "109": 1490,
                "110": 5, "111": 19, "114": 0, "119": True, "124": False,
                "125": "working", "126": False, "127": "normal", "1": True,
            }}

        def set_value(self, dp, v):
            pass

    class FakeCloud:
        def __init__(self, *a, **k):
            self.token = "fake-token"  # CloudClient afviser token=None (bad creds)

        def cloudrequest(self, path, post=None):
            if path.endswith("/shadow/properties"):
                props = [
                    {"code": "PH_Number", "value": 740},
                    {"code": "ORP_Number", "value": 680},
                    {"code": "fc_number", "value": 120},
                    {"code": "water_tempture_c", "value": 19},
                    {"code": "battery_capacity", "value": 97},
                    {"code": "ph_set", "value": 750},
                    {"code": "orp_set", "value": 700},
                    {"code": "ph_indcator", "value": "green"},
                    {"code": "maintenance_indicator", "value": "off"},
                ]
                return {"success": True, "result": {"properties": props}}
            return {"success": True, "result": {}}

    monkeypatch.setattr(tuya, "tinytuya", types.SimpleNamespace(Device=FakeDevice, Cloud=FakeCloud))
    return tuya
