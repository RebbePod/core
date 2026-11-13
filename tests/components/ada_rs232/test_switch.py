"""Tests for ADA zone power switches."""

from datetime import timedelta
from unittest.mock import MagicMock

from ada_rs232 import AdaConnectionError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import ENTITY_ID

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Verify all eight switches and their device registration."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "enabled", "expected"),
    [(SERVICE_TURN_ON, True, STATE_ON), (SERVICE_TURN_OFF, False, STATE_OFF)],
)
async def test_power_actions(
    hass: HomeAssistant,
    mock_client: MagicMock,
    service: str,
    enabled: bool,
    expected: str,
) -> None:
    """Publish only the state reported by command readback."""
    mock_client.async_set_zone.return_value = (enabled,) + (False,) * 7
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_client.async_set_zone.assert_awaited_once_with(1, enabled)
    assert hass.states.get(ENTITY_ID).state == expected


async def test_hardware_override(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """An off command must not override feedback from an active hardware trigger."""
    mock_client.async_set_zone.return_value = (True,) + (False,) * 7
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_feedback_and_recovery(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Push feedback updates entities; a later poll recovers a lost connection."""
    listener = mock_client.subscribe.call_args.args[0]
    listener((True,) * 8)
    assert all(
        state.state == STATE_ON for state in hass.states.async_all(Platform.SWITCH)
    )
    listener(None)
    assert all(
        state.state == STATE_UNAVAILABLE
        for state in hass.states.async_all(Platform.SWITCH)
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()
    assert mock_client.async_get_state.await_count == 2
    assert all(
        state.state == STATE_OFF for state in hass.states.async_all(Platform.SWITCH)
    )


async def test_command_failure(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Failed readback is reported and makes all outputs unavailable."""
    mock_client.async_set_zone.side_effect = AdaConnectionError("No reply")
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert all(
        state.state == STATE_UNAVAILABLE
        for state in hass.states.async_all(Platform.SWITCH)
    )
