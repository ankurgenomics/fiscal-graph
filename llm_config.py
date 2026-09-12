"""Central LLM factory. Uses OpenRouter (OpenAI-compatible endpoint) for all models.

DEV_MODEL: free-tier, zero-cost, used while iterating on prompts/code.
HAIKU_MODEL / SONNET_MODEL: real Claude, used for final verified runs (costs a few cents).
"""
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

DEV_MODEL = os.environ.get("DEV_MODEL", "liquid/lfm-2.5-2.6b:free")  # via OpenRouter, free
# Gemma was the original default; swapped after its shared free-tier pool started
# returning 429s. Reasoning-style free models (nvidia/nemotron-3-super-120b-a12b:free,
# nex-agi/nex-n2.5-pro:free) were tried and rejected: both spend their entire token
# budget on a hidden "thinking" phase before ever emitting the structured JSON answer,
# which is a bad fit for a fast dev-iteration loop regardless of eventual accuracy.
HAIKU_MODEL = "claude-haiku-4-5-20251001"  # direct Anthropic model id
SONNET_MODEL = "claude-sonnet-5"  # direct Anthropic model id
GEMINI_MODEL = "gemini-3.6-flash"  # direct Google Gemini model id


DEFAULT_TIMEOUT_SECONDS = 60


def primary_model(part_default: str) -> str:
    """Returns the MODEL_OVERRIDE environment variable if set, otherwise the given
    default. Every documented entry point resolves its model through this function,
    so a single environment variable swaps the whole pipeline onto a different
    model without touching any code:

        MODEL_OVERRIDE=gemini-3.6-flash python run_all.py

    See MODEL_EVALUATION.md for what running the pipeline this way actually
    produces, verified live, not just wired up and left untested.
    """
    return os.environ.get("MODEL_OVERRIDE") or part_default


def get_llm(
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float | None = 0,
    timeout: float | None = DEFAULT_TIMEOUT_SECONDS,
):
    """Routes to direct Anthropic for real Claude models (HAIKU_MODEL/SONNET_MODEL),
    direct Google for GEMINI_MODEL, OpenRouter for everything else (free/dev models).
    Model-agnostic: any OpenRouter model id works for the dev path with zero code changes.

    temperature=None omits the parameter entirely -- some newer Anthropic models
    (confirmed: claude-sonnet-5) reject `temperature` as deprecated/unsupported and
    error with a 400 if it's passed at all, even 0. Haiku 4.5 accepts it fine.

    timeout bounds every network call so a hung provider can't hang the pipeline
    indefinitely. Each provider names this field differently, confirmed by inspecting
    each class's own pydantic model_fields rather than guessing: ChatAnthropic wants
    `default_request_timeout`, ChatOpenAI wants `request_timeout`, ChatGoogleGenerativeAI
    wants `timeout`. Pass timeout=None to disable the bound entirely.
    """
    model = model or DEV_MODEL
    if model in (HAIKU_MODEL, SONNET_MODEL):
        if not _ANTHROPIC_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        kwargs = {"api_key": _ANTHROPIC_KEY, "model": model, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if timeout is not None:
            kwargs["default_request_timeout"] = timeout
        return ChatAnthropic(**kwargs)
    if model == GEMINI_MODEL:
        if not _GEMINI_KEY:
            raise RuntimeError("GEMINI_API_KEY not set in .env")
        kwargs = {"google_api_key": _GEMINI_KEY, "model": model, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if timeout is not None:
            kwargs["timeout"] = timeout
        return ChatGoogleGenerativeAI(**kwargs)
    if not _OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    kwargs = {
        "base_url": OPENROUTER_BASE_URL,
        "api_key": _OPENROUTER_KEY,
        "model": model,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if timeout is not None:
        kwargs["request_timeout"] = timeout
    return ChatOpenAI(**kwargs)
