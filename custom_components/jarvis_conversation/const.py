"""Constants for the JARVIS Conversation integration."""

import logging

DOMAIN = "jarvis_conversation"
LOGGER = logging.getLogger(__package__)

CONF_TIMEOUT = "timeout"
CONF_MODEL = "model"

DEFAULT_TIMEOUT = 120

# Prefix for the Hermes conversation name derived from the HA conversation id.
CONVERSATION_PREFIX = "ha-"

UNAVAILABLE_SPEECH = {
    "de": "JARVIS ist gerade nicht erreichbar.",
    "en": "JARVIS is not reachable right now.",
}
