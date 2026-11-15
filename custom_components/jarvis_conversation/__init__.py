"""The JARVIS Conversation integration.

Makes JARVIS (the Hermes agent) available as a conversation agent in Assist.
The integration only forwards text and returns the answer; it has no tools and
no access to the Home Assistant LLM API. JARVIS controls Home Assistant on its
own through the Home Assistant MCP server.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JarvisClient
from .const import CONF_TIMEOUT, DEFAULT_TIMEOUT

PLATFORMS = [Platform.CONVERSATION]

type JarvisConfigEntry = ConfigEntry[JarvisClient]


async def async_setup_entry(hass: HomeAssistant, entry: JarvisConfigEntry) -> bool:
    """Set up JARVIS Conversation from a config entry."""
    entry.runtime_data = JarvisClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JarvisConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
