"""Central LLM factory. Uses OpenRouter (OpenAI-compatible endpoint) for all models.

DEV_MODEL: free-tier, zero-cost, used while iterating on prompts/code.
HAIKU_MODEL / SONNET_MODEL: real Claude, used for final verified runs (costs a few cents).
"""
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

DEV_MODEL = os.environ.get("DEV_MODEL", "google/gemma-4-31b-it:free")  # via OpenRouter, free
HAIKU_MODEL = "claude-haiku-4-5-20251001"  # direct Anthropic model id
SONNET_MODEL = "claude-sonnet-5"  # direct Anthropic model id


def get_llm(model: str | None = None, max_tokens: int = 1024, temperature: float = 0):
    """Routes to direct Anthropic for real Claude models (HAIKU_MODEL/SONNET_MODEL),
    OpenRouter for everything else (free/dev models). Model-agnostic: any OpenRouter
    model id works for the dev path with zero code changes.
    """
    model = model or DEV_MODEL
    if model in (HAIKU_MODEL, SONNET_MODEL):
        if not _ANTHROPIC_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
        return ChatAnthropic(api_key=_ANTHROPIC_KEY, model=model, max_tokens=max_tokens, temperature=temperature)
    if not _OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    return ChatOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=_OPENROUTER_KEY,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
