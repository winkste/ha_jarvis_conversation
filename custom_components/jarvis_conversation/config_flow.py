"""Config flow for the JARVIS Conversation integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import JarvisAuthError, JarvisClient, JarvisConnectionError, JarvisError
from .const import CONF_MODEL, CONF_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, LOGGER

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(
                min=10,
                max=600,
                step=10,
                unit_of_measurement="s",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
)


class JarvisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JARVIS Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Hermes API server and validate the connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            timeout = int(user_input[CONF_TIMEOUT])
            self._async_abort_entries_match({CONF_URL: url})

            client = JarvisClient(
                async_get_clientsession(self.hass),
                url,
                user_input[CONF_API_KEY],
                timeout,
            )
            try:
                model = await client.async_get_model()
            except JarvisAuthError:
                errors["base"] = "invalid_auth"
            except JarvisConnectionError:
                errors["base"] = "cannot_connect"
            except JarvisError:
                LOGGER.exception("Unexpected response from JARVIS")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="JARVIS",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_TIMEOUT: timeout,
                        CONF_MODEL: model,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )
