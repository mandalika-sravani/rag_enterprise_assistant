"""Claude through LangChain (langchain-anthropic), returning validated Pydantic objects.

`with_structured_output(Schema, include_raw=True)` makes Claude answer by calling a tool whose
input schema is the Pydantic model, parses the reply into that model, and keeps the raw message
so token usage can be logged. An invalid reply is retried once; provider errors (raised by the
underlying anthropic SDK) become a few safe error types that the API turns into HTTP errors.
"""

import time
from typing import TypeVar

import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    status, code = 502, "llm_error"
    message = "The language model failed to answer. Please try again."


class LLMTimeout(LLMError):
    status, code, message = 504, "llm_timeout", "The language model took too long to respond. Please try again."


class LLMRateLimited(LLMError):
    status, code, message = 429, "llm_rate_limited", "Too many requests right now. Please retry shortly."


class LLMUnavailable(LLMError):
    status, code, message = 503, "llm_unavailable", "The language model service is unavailable. Please try again later."


class LLMBadOutput(LLMError):
    status, code, message = 502, "llm_bad_output", "The language model returned an invalid response, so no answer was given."


class Claude:
    def __init__(self, api_key: str, model: str, timeout: float = 30, base_url: str | None = None):
        options = {"base_url": base_url} if base_url else {}
        self.chat = ChatAnthropic(model=model, api_key=api_key, max_tokens=1024,
                                  default_request_timeout=timeout, max_retries=2, **options)

    def ask_json(self, system: str, prompt: str, schema: type[T], trace: dict | None = None) -> T:
        structured = self.chat.with_structured_output(schema, include_raw=True)
        for attempt in range(2):
            t0 = time.perf_counter()
            try:
                out = structured.invoke([SystemMessage(system), HumanMessage(prompt)])
            except anthropic.APITimeoutError as exc:
                raise LLMTimeout() from exc
            except anthropic.RateLimitError as exc:
                raise LLMRateLimited() from exc
            except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
                raise LLMUnavailable() from exc
            except anthropic.APIStatusError as exc:
                raise LLMError() from exc

            usage = getattr(out["raw"], "usage_metadata", None) or {}
            if trace is not None:  # tokens and latency for logging and cost
                trace["llm_calls"].append({"schema": schema.__name__, "input_tokens": usage.get("input_tokens", 0),
                                           "output_tokens": usage.get("output_tokens", 0),
                                           "ms": round((time.perf_counter() - t0) * 1000)})
            if out["parsed"] is not None and out["parsing_error"] is None:
                return out["parsed"]
            prompt += f"\n\nYour previous reply was invalid ({out['parsing_error']}). Reply using the tool correctly."
        raise LLMBadOutput()
