# ha_jarvis_conversation

Home Assistant integration that makes **JARVIS** – an agent running on
[Hermes Agent](https://github.com/NousResearch/hermes-agent) – available as a
conversation agent in Assist.

The integration is only a **mouthpiece**: it forwards what was said or typed in
Assist to the Hermes API server and returns the answer. It has no tools and no
access to the Home Assistant LLM API. JARVIS is the brain and controls Home
Assistant on its own, for example through the Home Assistant MCP server.

```
Assist satellite ──text──► JARVIS Conversation ──► Hermes API server (JARVIS)
                 ◄─answer──                                  │
                                                             └──► Home Assistant (MCP)
```

## Features

- Conversation agent for Assist pipelines (voice and text)
- Streams the answer, so text-to-speech can start before the answer is complete
- Keeps follow-up questions in context: each Assist conversation maps to a
  named Hermes conversation
- Tells JARVIS where the request came from: device, satellite, area and language
- Answers with a short spoken message when JARVIS is not reachable

## Requirements

- Home Assistant 2026.11 or newer
- Hermes Agent with the API server enabled and reachable from Home Assistant:

  ```sh
  # ~/.hermes/.env
  API_SERVER_ENABLED=true
  API_SERVER_KEY=<long random key>
  API_SERVER_HOST=0.0.0.0   # default 127.0.0.1 is not reachable from Home Assistant
  ```

  Only expose the API server in your local network and keep the key private.

## Installation

### HACS

1. HACS → ⋮ → Custom repositories → add this repository as type *Integration*
2. Install **JARVIS Conversation** and restart Home Assistant

### Manual

Copy `custom_components/jarvis_conversation` into `/config/custom_components/`
and restart Home Assistant.

## Configuration

1. Settings → Devices & services → Add integration → **JARVIS Conversation**
2. Enter the URL of the Hermes API server (e.g. `http://192.168.1.20:8642`),
   the API key and a timeout
3. Settings → Voice assistants → choose your assistant → Conversation agent:
   **JARVIS**

## How it works

Each request goes to `POST /v1/responses` of the Hermes API server with
streaming enabled. The Home Assistant conversation id is used as the Hermes
conversation name (`ha-<conversation id>`), so follow-up questions share the
same history. Device, satellite, area and language are sent as `instructions`.

## License

MIT
