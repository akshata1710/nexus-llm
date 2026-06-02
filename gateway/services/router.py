import httpx
from dataclasses import dataclass
from core.config import settings


@dataclass
class LLMRequest:
    model: str
    messages: list[dict]
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False


@dataclass
class LLMResponse:
    provider: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ProviderRouter:

    def resolve_provider(self, model: str) -> str:
        if "claude" in model.lower():
            return "anthropic"
        if "gpt" in model.lower():
            return "openai"
        if "gemini" in model.lower():
            return "gemini"
        raise ValueError(f"Unknown model: {model}. Must contain 'claude', 'gpt', or 'gemini'.")

    async def route(self, request: LLMRequest) -> LLMResponse:
        provider = self.resolve_provider(request.model)

        providers_to_try = [provider]
        if provider == "openai" and settings.anthropic_api_key:
            providers_to_try.append("anthropic")
        elif provider == "anthropic" and settings.openai_api_key:
            providers_to_try.append("openai")

        last_error = None
        for p in providers_to_try:
            try:
                return await self._call_provider(p, request)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503):
                    last_error = e
                    continue
                raise
            except httpx.TimeoutException as e:
                last_error = e
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")

    async def _call_provider(self, provider: str, request: LLMRequest) -> LLMResponse:
        if provider == "anthropic":
            return await self._call_anthropic(request)
        elif provider == "openai":
            return await self._call_openai(request)
        elif provider == "gemini":
            return await self._call_gemini(request)
        raise ValueError(f"Unknown provider: {provider}")

    async def _call_anthropic(self, request: LLMRequest) -> LLMResponse:
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured")

        system = ""
        messages = []
        for msg in request.messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                messages.append(msg)

        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            provider="anthropic",
            model=data["model"],
            content=data["content"][0]["text"],
            prompt_tokens=data["usage"]["input_tokens"],
            completion_tokens=data["usage"]["output_tokens"],
            total_tokens=data["usage"]["input_tokens"] + data["usage"]["output_tokens"],
        )

    async def _call_openai(self, request: LLMRequest) -> LLMResponse:
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": request.model,
                    "messages": request.messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            provider="openai",
            model=data["model"],
            content=data["choices"][0]["message"]["content"],
            prompt_tokens=data["usage"]["prompt_tokens"],
            completion_tokens=data["usage"]["completion_tokens"],
            total_tokens=data["usage"]["total_tokens"],
        )

    async def _call_gemini(self, request: LLMRequest) -> LLMResponse:
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key not configured")

        contents = [
            {
                "role": m["role"] if m["role"] != "assistant" else "model",
                "parts": [{"text": m["content"]}]
            }
            for m in request.messages if m["role"] != "system"
        ]

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent",
                params={"key": settings.gemini_api_key},
                json={"contents": contents},
            )
            resp.raise_for_status()
            data = resp.json()

        candidate = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})

        return LLMResponse(
            provider="gemini",
            model=request.model,
            content=candidate,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
        )


provider_router = ProviderRouter()