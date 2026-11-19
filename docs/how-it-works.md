# How it works

This document explains the code of the JARVIS Conversation integration for
people who want to read or change it. For installation and setup, see the
[README](../README.md).

The integration is a mouthpiece: it forwards Assist requests to the Hermes API
server and returns the answer. It has no tools and no logic of its own.

## Files

```
custom_components/jarvis_conversation/
├── manifest.json     integration metadata
├── __init__.py       sets up a config entry and creates the client
├── config_flow.py    setup dialog (URL, API key, timeout)
├── const.py          constants
├── api.py            client for the Hermes API server, stream parser
├── conversation.py   the conversation agent
└── translations/     UI texts
```

## The path of a request

```
speech ─► speech-to-text ─► JarvisConversationEntity ─► JarvisClient ─► POST /v1/responses
                                     ▲                                        │ SSE stream
text-to-speech ◄── chat log ◄── deltas ┴──────────── parse_response_stream ◄──┘
```

## 1. Loading

`manifest.json` declares the domain `jarvis_conversation`, enables UI setup
(`config_flow: true`) and depends on `conversation`, so Home Assistant loads its
conversation system first. There are no extra Python requirements; `aiohttp`
and `voluptuous` ship with Home Assistant.

## 2. Setup dialog (`config_flow.py`)

`JarvisConfigFlow.async_step_user` shows a form for URL, API key and timeout.
On submit it validates the input before anything is stored:

```python
client = JarvisClient(async_get_clientsession(self.hass), url, api_key, timeout)
try:
    model = await client.async_get_model()
except JarvisAuthError:
    errors["base"] = "invalid_auth"
except JarvisConnectionError:
    errors["base"] = "cannot_connect"
```

`async_get_model()` calls `GET /v1/models`. This proves that URL and key work
and returns the model name the server advertises. The name is stored in the
config entry, because every request has to send it. The same URL cannot be
configured twice.

## 3. Starting the integration (`__init__.py`)

`async_setup_entry` creates a `JarvisClient` and keeps it in
`entry.runtime_data`, then forwards the setup to the conversation platform.
It does not contact the Hermes API server. If Hermes is offline, the
integration still loads and only individual requests fail (see step 10).

## 4. Registering the agent (`conversation.py`)

`JarvisConversationEntity` inherits from Home Assistant's
`ConversationEntity` and `AbstractConversationAgent`:

- `_attr_supports_streaming = True` lets the Assist pipeline start
  text-to-speech before the answer is complete.
- `supported_languages` returns `MATCH_ALL`; the agent accepts any language.
- `async_added_to_hass` calls `conversation.async_set_agent`, which makes the
  agent selectable in voice assistants.
- A service device carries the advertised model name.

## 5. Receiving a request

Home Assistant's base class `ConversationEntity.async_process` opens a chat
session and a chat log for the request, adds the user text to the log and then
calls the integration's `_async_handle_message(user_input, chat_log)`.

`user_input` provides the text, the language, the conversation id and, if
known, the device id and the satellite entity id.

## 6. Request context

`_request_context` builds a short text that tells the agent where the request
came from: language, device name, satellite entity and area. The area is taken
from the satellite entity first, then from the device. An
`extra_system_prompt` from Home Assistant is appended. Example:

```
Request received through Home Assistant Assist (voice satellite or Assist dialog).
Language: de
Device: Kitchen satellite
Area: Kitchen
```

The context lets the agent resolve references such as "turn on the light
here". The integration itself controls nothing.

## 7. Sending the request (`api.py`)

`JarvisClient.async_stream_response` posts to `/v1/responses`:

```python
payload = {
    "model": model,
    "input": text,
    "conversation": conversation,
    "stream": True,
    "store": True,
    "instructions": instructions,  # the request context, only if present
}
```

The API key is sent as `Authorization: Bearer <key>`. With `stream: True` the
server answers with server-sent events (SSE). The method is an async generator
and yields each piece of answer text as soon as it arrives.

## 8. Parsing the stream

The stream contains more than answer text: reasoning, tool calls, commentary
and keepalive comments. `parse_response_stream` keeps only the answer:

| Event | Handling |
|---|---|
| `response.output_text.delta` | yield `delta` |
| `response.completed`, `[DONE]` | stop |
| `response.failed`, `error` | raise `JarvisError` |
| everything else, lines without `data:` | ignore |

## 9. Streaming the answer into Home Assistant

`_async_answer_deltas` turns the text pieces into chat log deltas: first
`{"role": "assistant"}`, then one `{"content": ...}` per piece.
`_async_handle_message` feeds them into
`chat_log.async_add_delta_content_stream`. Because the entity supports
streaming, the Assist pipeline can pass finished sentences to text-to-speech
while the agent is still writing.

Finally `conversation.async_get_result_from_chat_log` takes the last assistant
message as the result, which Assist shows and speaks.

## 10. Follow-up questions

The Hermes conversation name is derived from the Home Assistant conversation
id:

```python
f"{CONVERSATION_PREFIX}{chat_log.conversation_id}"   # "ha-<conversation id>"
```

Home Assistant keeps the conversation id for follow-up questions, so Hermes
continues the stored history of the same conversation. A new conversation in
Home Assistant starts a fresh conversation in Hermes.

## 11. Errors

`api.py` translates network errors into its own exception types:

| Exception | Cause |
|---|---|
| `JarvisAuthError` | HTTP 401 or 403 |
| `JarvisConnectionError` | server unreachable, timeout |
| `JarvisError` | any other HTTP error, error event in the stream (base class of both above) |

`_async_handle_message` catches `JarvisError`, logs a warning and returns a
spoken message ("JARVIS is not reachable right now", German for German
assistants) instead of failing silently.

## What the integration does not do

- **No tools:** it never provides the Home Assistant LLM API to the agent. The
  agent controls Home Assistant through its own connection, for example the
  Home Assistant MCP server.
- **No logic:** no routing, filtering or memory. That is the agent's job.
- **No further entities:** no status sensors and no actions for automations.
