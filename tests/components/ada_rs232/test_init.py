"""Tests for ADA RS-232 setup and teardown."""

from unittest.mock import MagicMock, patch

from ada_rs232 import AdaConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ada_rs232.const import CONF_ADDRESS, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ENTITY_ID, MOCK_PORT


async def test_setup_retry(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retry failed setup without leaking a proxy key or retaining the client."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_DEVICE: "esphome://proxy.local/?port_name=ADA&noise_psk=SECRET",
        },
    )
    mock_client.async_get_state.side_effect = AdaConnectionError("No response")
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "SECRET" not in caplog.text
    assert not hass.states.async_all(Platform.SWITCH)
    mock_client.async_close.assert_awaited_once()
    mock_client.subscribe.return_value.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_unload(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Unload the integration and release its subscriptions and connection."""
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_client.async_close.assert_awaited_once()
    mock_client.subscribe.return_value.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_failed_unload_keeps_connection(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Keep the connection if the platform cannot unload."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    mock_client.async_close.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_home_assistant_stop(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Close the serial connection when Home Assistant stops."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_client.async_close.assert_awaited_once()


async def test_shared_connection_and_addressed_feedback(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Entries and read-only probes share one bus until its last owner unloads."""
    with patch(
        "homeassistant.components.ada_rs232.connection.AdaBus", return_value=mock_bus
    ) as factory:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        mock_bus.async_get_states.return_value = {1: (False,) * 8, 9: (False,) * 8}
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: MOCK_PORT}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_ADDRESS] == 9
        factory.assert_called_once_with(MOCK_PORT)
        mock_bus.async_close.assert_not_awaited()
        mock_bus.async_get_state.assert_any_await(1)
        mock_bus.async_get_state.assert_any_await(9)
        first_listener = mock_bus.subscribe.call_args_list[0].args[0]
        second_listener = mock_bus.subscribe.call_args_list[1].args[0]
        for listener in (first_listener, second_listener):
            listener(1, (True,) * 8)
        assert hass.states.get(ENTITY_ID).state == STATE_ON
        assert hass.states.get("switch.ada_ptm_1645_9_zone_1").state == STATE_OFF
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        mock_bus.async_close.assert_not_awaited()
        assert await hass.config_entries.async_unload(result["result"].entry_id)
        mock_bus.async_close.assert_awaited_once()
