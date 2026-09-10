"""Cloud account failures must lead users to the correct recovery action."""
import pytest

from custom_components.intex_pool import config_flow, tuya


@pytest.mark.parametrize("step", ["user", "reconfigure_user", "sensor"])
async def test_expired_subscription_has_actionable_form_error(hass, monkeypatch, step):
    async def expired(*args):
        raise tuya.TuyaSubscriptionError("cloud plan expired")

    monkeypatch.setattr(config_flow, "discover", expired)
    monkeypatch.setattr(config_flow, "validate_sensor", expired)
    flow = config_flow.IntexPoolConfigFlow()
    flow.hass = hass
    result = await getattr(flow, f"async_step_{step}")({
        "region": "eu-w", "access_id": "test-id", "access_secret": "test-secret",
        "device_id": "test-analyzer",
    })
    assert result["step_id"] == step
    assert result["errors"] == {"base": "cloud_subscription"}
