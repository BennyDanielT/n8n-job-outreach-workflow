"""LLM access behind one small interface, so the pipeline never imports a vendor SDK.

`AzureLLM` talks to Azure OpenAI (Microsoft Foundry) using structured outputs: every call
returns a validated Pydantic object or raises. `FakeLLM` replays canned responses for tests.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLM(Protocol):
    def structured(self, *, system: str, user: str, schema: type[T], step: str, judge: bool = False) -> T: ...


class LLMError(RuntimeError):
    pass


class AzureLLM:
    """Azure OpenAI via the OpenAI SDK's Azure client, with structured outputs."""

    def __init__(self, settings: Settings):
        from openai import AzureOpenAI

        if not settings.azure_openai_endpoint:
            raise LLMError("AZURE_OPENAI_ENDPOINT is not set")

        kwargs: dict = {
            "azure_endpoint": settings.azure_openai_endpoint,
            "api_version": "2024-10-21",
            "timeout": settings.llm_timeout_s,
            "max_retries": 3,
        }
        if settings.azure_openai_api_key:
            kwargs["api_key"] = settings.azure_openai_api_key
        else:
            # Keyless: managed identity in Azure, `az login` locally.
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
            )
        self._client = AzureOpenAI(**kwargs)
        self._deployment = settings.azure_openai_deployment
        self._judge_deployment = settings.azure_openai_judge_deployment or settings.azure_openai_deployment
        self._temperature = settings.llm_temperature

    def structured(self, *, system: str, user: str, schema: type[T], step: str, judge: bool = False) -> T:
        model = self._judge_deployment if judge else self._deployment
        started = time.perf_counter()
        completion = self._client.chat.completions.parse(
            model=model,
            temperature=0 if judge else self._temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=schema,
        )
        msg = completion.choices[0].message
        usage = completion.usage
        log.info(
            "llm_call step=%s model=%s ms=%d prompt_tokens=%s completion_tokens=%s",
            step,
            model,
            (time.perf_counter() - started) * 1000,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )
        if getattr(msg, "refusal", None):
            raise LLMError(f"Model refused at step '{step}': {msg.refusal}")
        if msg.parsed is None:
            raise LLMError(f"No structured output at step '{step}'")
        return msg.parsed


class FakeLLM:
    """Returns responses from a dict of step name -> object or callable(user_prompt) -> object."""

    def __init__(self, responses: dict[str, BaseModel | list[BaseModel] | Callable[[str], BaseModel]]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def structured(self, *, system: str, user: str, schema: type[T], step: str, judge: bool = False) -> T:
        self.calls.append((step, user))
        r = self.responses[step]
        if isinstance(r, list):  # successive calls get successive answers
            r = r.pop(0) if len(r) > 1 else r[0]
        if callable(r) and not isinstance(r, BaseModel):
            r = r(user)
        assert isinstance(r, schema), f"FakeLLM step '{step}' returned {type(r).__name__}, expected {schema.__name__}"
        return r


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "azure":
        return AzureLLM(settings)
    if settings.llm_provider == "fake":
        from app.demo import demo_llm

        return demo_llm()
    raise LLMError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'")
