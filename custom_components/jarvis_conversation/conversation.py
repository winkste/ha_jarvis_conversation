"""Conversation agent that forwards Assist requests to JARVIS."""

from collections.abc import AsyncIterator
from typing import Literal, override

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JarvisConfigEntry
from .api import JarvisError
from .const import (
    CONF_MODEL,
    CONVERSATION_PREFIX,
    DOMAIN,
    LOGGER,
    UNAVAILABLE_SPEECH,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JarvisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JARVIS conversation entity."""
    async_add_entities([JarvisConversationEntity(entry)])


class JarvisConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Forward Assist requests to JARVIS and return its answer."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supports_streaming = True

    def __init__(self, entry: JarvisConfigEntry) -> None:
        """Initialize the agent."""
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Hermes Agent",
            model=entry.data[CONF_MODEL],
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register the agent when the entity is added."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister the agent when the entity is removed."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return the supported languages; JARVIS handles any language."""
        return MATCH_ALL

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Forward the request to JARVIS and stream the answer into the chat log."""
        try:
            async for _content in chat_log.async_add_delta_content_stream(
                self.entity_id, self._async_answer_deltas(user_input, chat_log)
            ):
                pass
        except JarvisError as err:
            LOGGER.warning("JARVIS request failed: %s", err)
            return self._unavailable_result(user_input, chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_answer_deltas(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> AsyncIterator[conversation.AssistantContentDeltaDict]:
        """Translate the JARVIS text stream into chat log deltas."""
        yield {"role": "assistant"}
        async for text in self.entry.runtime_data.async_stream_response(
            self.entry.data[CONF_MODEL],
            user_input.text,
            f"{CONVERSATION_PREFIX}{chat_log.conversation_id}",
            self._request_context(user_input),
        ):
            yield {"content": text}

    def _request_context(self, user_input: conversation.ConversationInput) -> str:
        """Describe where the request came from, so JARVIS can answer in place."""
        lines = [
            "Request received through Home Assistant Assist "
            "(voice satellite or Assist dialog).",
            f"Language: {user_input.language}",
        ]

        device = None
        if user_input.device_id:
            device = dr.async_get(self.hass).async_get(user_input.device_id)
        if device is not None:
            lines.append(f"Device: {device.name_by_user or device.name}")

        if user_input.satellite_id:
            lines.append(f"Satellite entity: {user_input.satellite_id}")

        if area_name := self._request_area(user_input, device):
            lines.append(f"Area: {area_name}")

        if user_input.extra_system_prompt:
            lines.append(user_input.extra_system_prompt)

        return "\n".join(lines)

    def _request_area(
        self,
        user_input: conversation.ConversationInput,
        device: dr.DeviceEntry | None,
    ) -> str | None:
        """Return the area of the satellite or device that received the request."""
        area_id = None
        if user_input.satellite_id:
            satellite = er.async_get(self.hass).async_get(user_input.satellite_id)
            if satellite is not None:
                area_id = satellite.area_id
        if area_id is None and device is not None:
            area_id = device.area_id
        if area_id is None:
            return None

        area = ar.async_get(self.hass).async_get_area(area_id)
        return area.name if area is not None else None

    def _unavailable_result(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Return a spoken error when JARVIS cannot be reached."""
        language = user_input.language.split("-")[0]
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(
            intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
            UNAVAILABLE_SPEECH.get(language, UNAVAILABLE_SPEECH["en"]),
        )
        return conversation.ConversationResult(
            response=response, conversation_id=chat_log.conversation_id
        )
