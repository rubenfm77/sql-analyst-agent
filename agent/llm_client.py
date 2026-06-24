"""
LLMClient interface + Groq implementation (OpenAI-compatible endpoint).
Swap the backend by implementing LLMClient and passing a different instance.
"""

from __future__ import annotations
import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface: one round-trip, returns the assistant text."""
    def complete(self, system: str, user: str) -> str: ...


class GroqClient:
    """
    Calls Groq via the OpenAI-compatible REST API.
    Reads GROQ_API_KEY from env or Streamlit secrets.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    BASE_URL      = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or self._resolve_key()
        self._model   = model or self.DEFAULT_MODEL

    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_key() -> str:
        # 1. plain env var
        key = os.environ.get("GROQ_API_KEY", "")
        if key:
            return key
        # 2. Streamlit secrets (only available inside a Streamlit process)
        try:
            import streamlit as st          # noqa: PLC0415
            key = st.secrets.get("GROQ_API_KEY", "")
            if key:
                return key
        except Exception:
            pass
        raise EnvironmentError(
            "GROQ_API_KEY not found. "
            "Set it as an environment variable or add it to .streamlit/secrets.toml."
        )

    # ------------------------------------------------------------------
    def complete(self, system: str, user: str) -> str:
        from openai import OpenAI           # noqa: PLC0415  (optional dep)

        client = OpenAI(api_key=self._api_key, base_url=self.BASE_URL)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""


def default_client() -> LLMClient:
    """Factory used by the app. Returns a GroqClient."""
    return GroqClient()
