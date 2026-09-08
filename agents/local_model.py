"""
Local model support for GLOSS.

Routes every LLM call to an Ollama model on the Khoury GPU cluster instead of
OpenAI/Azure. Two adapters live here, because GLOSS talks to models through two
different libraries:

- ``OllamaChatModel``     -- a LangChain chat model, used by every agent that
                             builds an LCEL chain (``prompt | llmchat | parser``).
- ``LangChainModelClient`` -- an AutoGen ``ChatCompletionClient``, used by
                             ``agents/coding_agent.py``.

Both go through :func:`chat` below, which speaks Ollama's ``/api/chat`` endpoint.

Requests are streamed and reassembled rather than sent with ``stream: false``.
The gateway's HTTPS front door returns 504 if a non-streaming request produces
no bytes before its timeout, which is easy to hit on long prompts.
"""

import json
import os
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import requests
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agents.config import (
    LOCAL_MODEL_API_KEY_ENV,
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_NAME,
    LOCAL_MODEL_NUM_PREDICT,
    LOCAL_MODEL_TEMPERATURE,
    LOCAL_MODEL_THINK,
    LOCAL_MODEL_TIMEOUT,
)

# AutoGen moved these out of `.components` after 0.4.0.dev2, which is the
# version GLOSS pins. Try the pinned layout first, then the newer one.
try:
    from autogen_core.components import FunctionCall  # noqa: F401
    from autogen_core.components.models import CreateResult, RequestUsage
except ImportError:  # pragma: no cover - newer autogen
    from autogen_core import FunctionCall  # noqa: F401
    from autogen_core.models import CreateResult, RequestUsage

# Retried: the gateway returns these when a worker is slow, unreachable, or all
# workers are momentarily offline. 429 and 500 matter once several people query
# the same model at once, which is the tutorial's normal state.
# 401/403 are deliberately absent -- a bad key or a non-allowlisted network will
# not fix itself, so those fail fast with the gateway's own explanation.
_RETRY_STATUS = (429, 500, 502, 503, 504)
_MAX_ATTEMPTS = 4


def get_api_key() -> Optional[str]:
    """Return the gateway bearer token, or None if it is not set."""
    return os.getenv(LOCAL_MODEL_API_KEY_ENV)


def get_headers() -> Dict[str, str]:
    """Build request headers, omitting auth when no key is configured.

    A direct worker URL needs no Authorization header; the gateway rejects
    requests without one (401).
    """
    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _message_text(content: Any) -> str:
    """Flatten message content to a string.

    Multimodal content arrives as a list of parts; keep the text ones.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
        return "\n".join(parts)
    return "" if content is None else str(content)


def chat(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    num_predict: Optional[int] = None,
    think: Optional[bool] = None,
    stop: Optional[Sequence[str]] = None,
    timeout: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Send a chat request to the Ollama gateway and return (text, metadata).

    ``messages`` uses Ollama's own format: ``{"role": ..., "content": ...}``
    with roles ``system``, ``user`` or ``assistant``.

    Returns the assistant's ``content``, plus metadata carrying token counts,
    the reasoning trace when thinking is enabled, and the worker that served
    the request.

    Raises:
        RuntimeError: on a non-200 response, or an error inside the stream.
                      The gateway's body is included, since it explains the
                      failure (e.g. which models the allowlist permits).
    """
    options: Dict[str, Any] = {
        "temperature": LOCAL_MODEL_TEMPERATURE if temperature is None else temperature,
    }
    predict = LOCAL_MODEL_NUM_PREDICT if num_predict is None else num_predict
    if predict is not None and predict > 0:
        options["num_predict"] = predict
    if stop:
        options["stop"] = list(stop)

    payload: Dict[str, Any] = {
        "model": model or LOCAL_MODEL_NAME,
        "messages": messages,
        "stream": True,
        "options": options,
        "think": LOCAL_MODEL_THINK if think is None else think,
    }

    url = f"{LOCAL_MODEL_BASE_URL.rstrip('/')}/api/chat"
    request_timeout = LOCAL_MODEL_TIMEOUT if timeout is None else timeout
    last_error = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return _stream_once(url, payload, request_timeout)
        except RuntimeError as exc:
            status = getattr(exc, "status_code", None)
            if status not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS:
                raise
            last_error = exc
        except requests.exceptions.RequestException as exc:
            if attempt == _MAX_ATTEMPTS:
                raise RuntimeError(f"Could not reach {url}: {exc}") from exc
            last_error = exc
        time.sleep(2 * attempt)

    raise RuntimeError(f"Request to {url} failed: {last_error}")


def _stream_once(url: str, payload: Dict[str, Any], timeout: int) -> Tuple[str, Dict[str, Any]]:
    """Run one streaming request and reassemble it."""
    content_parts: List[str] = []
    thinking_parts: List[str] = []
    meta: Dict[str, Any] = {}

    with requests.post(
        url, headers=get_headers(), json=payload, stream=True, timeout=timeout
    ) as response:
        if response.status_code != 200:
            error = RuntimeError(
                f"{url} returned {response.status_code}: {response.text.strip()}"
            )
            error.status_code = response.status_code
            raise error

        meta["worker"] = response.headers.get("X-Proxied-To")

        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                # The gateway occasionally injects a non-JSON keep-alive line.
                continue

            if "error" in chunk:
                raise RuntimeError(f"{url} streamed an error: {chunk['error']}")

            message = chunk.get("message") or {}
            content_parts.append(message.get("content") or "")
            thinking_parts.append(message.get("thinking") or "")

            if chunk.get("done"):
                meta.update(
                    {
                        "model": chunk.get("model"),
                        "done_reason": chunk.get("done_reason"),
                        "prompt_eval_count": chunk.get("prompt_eval_count", 0),
                        "eval_count": chunk.get("eval_count", 0),
                        "total_duration": chunk.get("total_duration"),
                    }
                )

    text = "".join(content_parts)
    meta["thinking"] = "".join(thinking_parts)

    # A thinking model that runs out of budget mid-reasoning returns an empty
    # answer. Say so explicitly, rather than handing a parser an empty string.
    if not text and meta.get("done_reason") == "length" and meta["thinking"]:
        raise RuntimeError(
            "Model produced only reasoning and no answer before hitting the token "
            "limit. Raise LOCAL_MODEL_NUM_PREDICT (or set it to -1), or set "
            "LOCAL_MODEL_THINK=False."
        )

    return text, meta


class OllamaChatModel(BaseChatModel):
    """LangChain chat model backed by an Ollama model on the GPU cluster.

    Drop-in replacement for ``ChatOpenAI`` in GLOSS's LCEL chains: it returns
    plain text, which the chains hand to ``JsonOutputParser`` or
    ``StrOutputParser`` exactly as before.
    """

    model: str = LOCAL_MODEL_NAME
    temperature: float = LOCAL_MODEL_TEMPERATURE
    num_predict: int = LOCAL_MODEL_NUM_PREDICT
    think: bool = LOCAL_MODEL_THINK
    request_timeout: int = LOCAL_MODEL_TIMEOUT

    @property
    def _llm_type(self) -> str:
        return "ollama-gateway-chat"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {
            "model": self.model,
            "base_url": LOCAL_MODEL_BASE_URL,
            "temperature": self.temperature,
            "think": self.think,
        }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        text, meta = chat(
            self._to_ollama_messages(messages),
            model=self.model,
            temperature=self.temperature,
            num_predict=self.num_predict,
            think=self.think,
            stop=stop,
            timeout=self.request_timeout,
        )

        message = AIMessage(
            content=text,
            usage_metadata={
                "input_tokens": meta.get("prompt_eval_count", 0) or 0,
                "output_tokens": meta.get("eval_count", 0) or 0,
                "total_tokens": (meta.get("prompt_eval_count", 0) or 0)
                + (meta.get("eval_count", 0) or 0),
            },
        )
        return ChatResult(
            generations=[ChatGeneration(message=message, generation_info=meta)],
            llm_output=meta,
        )

    @staticmethod
    def _to_ollama_messages(messages: Sequence[BaseMessage]) -> List[Dict[str, str]]:
        """Map LangChain message types onto Ollama roles.

        The system role is preserved rather than folded into the user turn,
        so prompts that rely on system instructions keep working.
        """
        role_map = {"system": "system", "human": "user", "ai": "assistant"}
        return [
            {
                "role": role_map.get(getattr(message, "type", "human"), "user"),
                "content": _message_text(message.content),
            }
            for message in messages
        ]


class LangChainModelClient:
    """AutoGen ``ChatCompletionClient`` backed by the same local model.

    Used by ``agents/coding_agent.py``, whose ``CodingAssistantAgent`` only
    calls ``create()``. Tool calling is not advertised: the coding agent gets
    code out of the model as text in a markdown block, which is what
    ``CodeExecutorAgent`` extracts and runs.
    """

    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None):
        self.model = model or LOCAL_MODEL_NAME
        self.temperature = LOCAL_MODEL_TEMPERATURE if temperature is None else temperature
        self._actual_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
        self._total_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)

    @property
    def capabilities(self) -> Dict[str, bool]:
        """Model capabilities, as autogen 0.4.0.dev2 expects them."""
        return {"vision": False, "function_calling": False, "json_output": False}

    @property
    def model_info(self) -> Dict[str, Any]:
        """Newer autogen releases read `model_info` instead of `capabilities`."""
        return {**self.capabilities, "family": "ollama"}

    async def create(
        self,
        messages: Sequence[Any],
        tools: Sequence[Any] = (),
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[Any] = None,
        **kwargs: Any,
    ) -> CreateResult:
        import asyncio

        ollama_messages = self._to_ollama_messages(messages)
        text, meta = await asyncio.to_thread(
            chat,
            ollama_messages,
            model=self.model,
            temperature=self.temperature,
        )

        usage = RequestUsage(
            prompt_tokens=meta.get("prompt_eval_count", 0) or 0,
            completion_tokens=meta.get("eval_count", 0) or 0,
        )
        self._actual_usage = usage
        self._total_usage = RequestUsage(
            prompt_tokens=self._total_usage.prompt_tokens + usage.prompt_tokens,
            completion_tokens=self._total_usage.completion_tokens + usage.completion_tokens,
        )

        return CreateResult(
            finish_reason=self._finish_reason(meta.get("done_reason")),
            content=text,
            usage=usage,
            cached=False,
            logprobs=None,
        )

    async def create_stream(
        self,
        messages: Sequence[Any],
        tools: Sequence[Any] = (),
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[Any] = None,
        **kwargs: Any,
    ):
        """Yield the finished result.

        The underlying call already streams from the gateway; this returns one
        chunk because nothing in GLOSS consumes token-by-token output.
        """
        result = await self.create(
            messages,
            tools=tools,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )
        yield result

    def actual_usage(self) -> RequestUsage:
        return self._actual_usage

    def total_usage(self) -> RequestUsage:
        return self._total_usage

    def count_tokens(self, messages: Sequence[Any], tools: Sequence[Any] = ()) -> int:
        """Rough token estimate (~4 characters per token).

        Ollama reports real counts only after generating, and AutoGen uses this
        only for budget bookkeeping.
        """
        characters = sum(len(m["content"]) for m in self._to_ollama_messages(messages))
        return characters // 4

    def remaining_tokens(self, messages: Sequence[Any], tools: Sequence[Any] = ()) -> int:
        # gpt-oss:20b and gemma4:31b both carry large context windows; 128k is a
        # safe floor for reporting purposes.
        return max(0, 128_000 - self.count_tokens(messages, tools))

    @staticmethod
    def _finish_reason(done_reason: Optional[str]) -> str:
        return {"stop": "stop", "length": "length", None: "unknown"}.get(
            done_reason, "unknown"
        )

    @staticmethod
    def _to_ollama_messages(messages: Sequence[Any]) -> List[Dict[str, str]]:
        """Map AutoGen's message dataclasses onto Ollama roles.

        AutoGen sends ``SystemMessage``/``UserMessage``/``AssistantMessage``,
        which are dataclasses rather than LangChain messages, so the mapping
        keys off the class name.
        """
        by_class = {
            "SystemMessage": "system",
            "UserMessage": "user",
            "AssistantMessage": "assistant",
        }
        converted = []
        for message in messages:
            role = by_class.get(type(message).__name__)
            if role is None:
                # LangChain messages expose `.type`; anything else is a user turn.
                role = {"system": "system", "human": "user", "ai": "assistant"}.get(
                    getattr(message, "type", ""), "user"
                )
            converted.append(
                {"role": role, "content": _message_text(getattr(message, "content", message))}
            )
        return converted


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, SystemMessage

    print(f"model:    {LOCAL_MODEL_NAME}")
    print(f"endpoint: {LOCAL_MODEL_BASE_URL}/api/chat")
    print(f"auth:     {LOCAL_MODEL_API_KEY_ENV} is {'set' if get_api_key() else 'NOT set'}\n")

    llm = OllamaChatModel()
    reply = llm.invoke(
        [
            SystemMessage(content="You are a concise assistant."),
            HumanMessage(content="Reply with exactly: local model works"),
        ]
    )
    print(f"reply: {reply.content!r}")
