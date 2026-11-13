import logging
import json
from dataclasses import dataclass
from collections.abc import Iterator

import httpx

from backend.infra.postgres.tables import UserSettings
from backend.services.common.ai_errors import LLMProviderError
from backend.services.common import decrypt_secret_value

logger = logging.getLogger(__name__)


def _resolve_secret(value: str | None) -> str | None:
    secret = decrypt_secret_value(value)
    if secret is None:
        return None
    clean = secret.strip()
    return clean or None


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


class _BaseBackend:
    provider: str
    model: str

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        raise NotImplementedError

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        # Fallback for providers without dedicated streaming support.
        result = self.generate(user_prompt=user_prompt, system_prompt=system_prompt)
        if result.text:
            yield result.text


class GeminiBackend(_BaseBackend):
    provider = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        with httpx.Client(timeout=60) as client:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content", {}).get("parts", []) if candidates else [])
        text = "\n".join(part.get("text", "") for part in parts).strip()
        if not text:
            logger.warning("Gemini returned an empty response")
            raise LLMProviderError("Gemini returned an empty response")
        return LLMResult(text=text, provider=self.provider, model=self.model)

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                url,
                params={"key": self.api_key, "alt": "sse"},
                json=payload,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines():
                    line = (raw_line or "").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if not chunk:
                        continue
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue

                    candidates = data.get("candidates") or []
                    parts = (candidates[0].get("content", {}).get("parts", []) if candidates else [])
                    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                    if text:
                        yield text


class OpenAIBackend(_BaseBackend):
    provider = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=60) as client:
            response = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        text = (message.get("content") or "").strip()
        if not text:
            logger.warning("OpenAI returned an empty response")
            raise LLMProviderError("OpenAI returned an empty response")
        return LLMResult(text=text, provider=self.provider, model=self.model)

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines():
                    line = (raw_line or "").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if not chunk or chunk == "[DONE]":
                        continue
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    delta = choices[0].get("delta", {}) if choices else {}
                    text = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(text, str) and text:
                        yield text


class AnthropicBackend(_BaseBackend):
    provider = "anthropic"
    _API_VERSION = "2023-06-01"
    _MAX_TOKENS = 800

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest"):
        self.api_key = api_key
        self.model = model

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        payload = {
            "model": self.model,
            "max_tokens": self._MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self._API_VERSION,
            "content-type": "application/json",
        }

        with httpx.Client(timeout=60) as client:
            response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        blocks = data.get("content") or []
        text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
        if not text:
            logger.warning("Anthropic returned an empty response")
            raise LLMProviderError("Anthropic returned an empty response")
        return LLMResult(text=text, provider=self.provider, model=self.model)

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "max_tokens": self._MAX_TOKENS,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "stream": True,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self._API_VERSION,
            "content-type": "application/json",
        }

        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines():
                    line = (raw_line or "").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if not chunk:
                        continue
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue

                    if data.get("type") != "content_block_delta":
                        continue
                    delta = data.get("delta") or {}
                    text = delta.get("text") if isinstance(delta, dict) else None
                    if isinstance(text, str) and text:
                        yield text


class OllamaBackend(_BaseBackend):
    provider = "ollama"
    _TEMPERATURE = 0.2
    _TOP_P = 0.9

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        provider_name: str = "ollama",
        api_key: str | None = None,
        localhost_retry: bool = True,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider_name
        self.api_key = (api_key or "").strip() or None
        self.localhost_retry = localhost_retry

    def _build_headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self._TEMPERATURE,
                "top_p": self._TOP_P,
            },
        }

        candidate_urls = [self.base_url]
        if self.localhost_retry and "://localhost" in self.base_url:
            candidate_urls.append(self.base_url.replace("://localhost", "://127.0.0.1", 1))

        data: dict | None = None
        last_connect_error: httpx.ConnectError | None = None
        headers = self._build_headers()
        with httpx.Client(timeout=120) as client:
            for candidate_url in candidate_urls:
                try:
                    response = client.post(f"{candidate_url}/api/chat", json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    break
                except httpx.ConnectError as exc:
                    last_connect_error = exc
                    logger.warning(
                        "Ollama chat endpoint unreachable at %s; trying next candidate if available",
                        candidate_url,
                    )

        if data is None:
            if last_connect_error is not None:
                raise LLMProviderError(f"Ollama connection failed: {last_connect_error}") from last_connect_error
            raise LLMProviderError("Ollama request failed before receiving a response")

        text = (data.get("message", {}).get("content") or "").strip()
        if not text:
            logger.warning("Ollama returned an empty response")
            raise LLMProviderError("Ollama returned an empty response")
        return LLMResult(text=text, provider=self.provider, model=self.model)

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "options": {
                "temperature": self._TEMPERATURE,
                "top_p": self._TOP_P,
            },
        }

        candidate_urls = [self.base_url]
        if self.localhost_retry and "://localhost" in self.base_url:
            candidate_urls.append(self.base_url.replace("://localhost", "://127.0.0.1", 1))

        last_connect_error: httpx.ConnectError | None = None
        headers = self._build_headers()
        with httpx.Client(timeout=120) as client:
            for candidate_url in candidate_urls:
                try:
                    with client.stream("POST", f"{candidate_url}/api/chat", json=payload, headers=headers) as response:
                        response.raise_for_status()
                        for raw_line in response.iter_lines():
                            line = (raw_line or "").strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            text = (data.get("message") or {}).get("content")
                            if isinstance(text, str) and text:
                                yield text
                    return
                except httpx.ConnectError as exc:
                    last_connect_error = exc
                    logger.warning(
                        "Ollama chat stream endpoint unreachable at %s; trying next candidate if available",
                        candidate_url,
                    )

        if last_connect_error is not None:
            raise LLMProviderError(f"Ollama connection failed: {last_connect_error}") from last_connect_error
        raise LLMProviderError("Ollama stream request failed before receiving a response")


class LLMProvider:
    """Abstraction over multiple LLM backends. Used only for chat."""

    def __init__(
        self,
        settings: UserSettings,
        preferred_provider: str | None = None,
        preferred_model: str | None = None,
    ):
        provider_name = (preferred_provider or "").strip().lower() or None
        model_name = (preferred_model or "").strip() or None
        gemini_key = _resolve_secret(settings.gemini_api_key)
        openai_key = _resolve_secret(settings.openai_api_key)
        anthropic_key = _resolve_secret(settings.anthropic_api_key)
        ollama_cloud_key = _resolve_secret(settings.ollama_cloud_api_key)

        if provider_name:
            self.backend = self._build_backend_for_provider(
                settings,
                provider_name,
                model_name,
                gemini_key=gemini_key,
                openai_key=openai_key,
                anthropic_key=anthropic_key,
                ollama_cloud_key=ollama_cloud_key,
            )
            return

        if gemini_key:
            self.backend = GeminiBackend(gemini_key, model=model_name or "gemini-2.5-flash")
        elif openai_key:
            self.backend = OpenAIBackend(openai_key, model=model_name or "gpt-4o-mini")
        elif anthropic_key:
            self.backend = AnthropicBackend(anthropic_key, model=model_name or "claude-3-5-sonnet-latest")
        elif ollama_cloud_key:
            self.backend = OllamaBackend(
                model_name or settings.ollama_model,
                base_url="https://api.ollama.com",
                provider_name="ollama_cloud",
                api_key=ollama_cloud_key,
                localhost_retry=False,
            )
        else:
            self.backend = OllamaBackend(model_name or settings.ollama_model, settings.ollama_base_url)

    def _build_backend_for_provider(
        self,
        settings: UserSettings,
        provider_name: str,
        model_name: str | None,
        *,
        gemini_key: str | None,
        openai_key: str | None,
        anthropic_key: str | None,
        ollama_cloud_key: str | None,
    ) -> _BaseBackend:
        if provider_name == "gemini":
            if not gemini_key:
                raise LLMProviderError("Gemini API key is not configured")
            return GeminiBackend(gemini_key, model=model_name or "gemini-2.5-flash")

        if provider_name == "openai":
            if not openai_key:
                raise LLMProviderError("OpenAI API key is not configured")
            return OpenAIBackend(openai_key, model=model_name or "gpt-4o-mini")

        if provider_name == "anthropic":
            if not anthropic_key:
                raise LLMProviderError("Anthropic API key is not configured")
            return AnthropicBackend(anthropic_key, model=model_name or "claude-3-5-sonnet-latest")

        if provider_name == "ollama":
            return OllamaBackend(model_name or settings.ollama_model, settings.ollama_base_url)

        if provider_name == "ollama_cloud":
            if not ollama_cloud_key:
                raise LLMProviderError("Ollama Cloud API key is not configured")
            return OllamaBackend(
                model_name or settings.ollama_model,
                base_url="https://api.ollama.com",
                provider_name="ollama_cloud",
                api_key=ollama_cloud_key,
                localhost_retry=False,
            )

        raise LLMProviderError(f"Unsupported provider '{provider_name}'")

    def generate(self, user_prompt: str, system_prompt: str) -> LLMResult:
        return self.backend.generate(user_prompt=user_prompt, system_prompt=system_prompt)

    def stream(self, user_prompt: str, system_prompt: str) -> Iterator[str]:
        return self.backend.stream(user_prompt=user_prompt, system_prompt=system_prompt)

    @property
    def provider_name(self) -> str:
        return self.backend.provider

    @property
    def model_name(self) -> str:
        return self.backend.model
