"""Tests for ADA RS-232 setup and teardown."""

from unittest.mock import MagicMock, patch

from ada_rs232 import AdaConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant


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
