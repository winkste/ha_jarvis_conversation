"""Client for the Hermes API server (OpenAI Responses API)."""

from collections.abc import AsyncIterable, AsyncIterator
import json
from typing import Any

import aiohttp

from .const import LOGGER


class JarvisError(Exception):
    """Base error of the JARVIS client."""


class JarvisConnectionError(JarvisError):
    """JARVIS is not reachable."""


class JarvisAuthError(JarvisError):
    """The API key was rejected."""


class JarvisClient:
    """Minimal client for the Hermes API server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        timeout: int,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def async_get_model(self) -> str:
        """Validate the connection and return the advertised model name."""
        try:
            async with self._session.get(
                f"{self._base_url}/v1/models",
                headers=self._headers,
                timeout=self._timeout,
            ) as response:
                if response.status in (401, 403):
                    raise JarvisAuthError("API key rejected")
                response.raise_for_status()
                body = await response.json()
        except aiohttp.ClientResponseError as err:
            raise JarvisError(f"Unexpected response: {err.status}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise JarvisConnectionError(str(err)) from err

        models = body.get("data") or []
        if not models:
            raise JarvisError("Server advertises no model")
        return models[0]["id"]

    async def async_stream_response(
        self,
        model: str,
        text: str,
        conversation: str,
        instructions: str | None,
    ) -> AsyncIterator[str]:
        """Send one user turn and yield the answer text as it streams in."""
        payload: dict[str, Any] = {
            "model": model,
            "input": text,
            "conversation": conversation,
            "stream": True,
            "store": True,
        }
        if instructions:
            payload["instructions"] = instructions

        try:
            async with self._session.post(
                f"{self._base_url}/v1/responses",
                headers=self._headers,
                json=payload,
                timeout=self._timeout,
            ) as response:
                if response.status in (401, 403):
                    raise JarvisAuthError("API key rejected")
                response.raise_for_status()
                async for delta in parse_response_stream(response.content):
                    yield delta
        except aiohttp.ClientResponseError as err:
            raise JarvisError(f"Unexpected response: {err.status}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise JarvisConnectionError(str(err)) from err


async def parse_response_stream(
    lines: AsyncIterable[bytes],
) -> AsyncIterator[str]:
    """Yield the answer text deltas from a Responses API SSE stream.

    Only `response.output_text.delta` events carry answer text. Commentary,
    reasoning and tool events are skipped, keepalive comments are ignored.
    """
    async for raw_line in lines:
        line = raw_line.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            return

        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            LOGGER.debug("Skipping malformed event: %s", data)
            continue

        event_type = event.get("type")
        if event_type == "response.output_text.delta":
            yield event.get("delta", "")
        elif event_type in ("response.failed", "error"):
            raise JarvisError(f"JARVIS reported an error: {event}")
        elif event_type == "response.completed":
            return
