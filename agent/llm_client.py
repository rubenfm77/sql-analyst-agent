"""
LLMClient interface + Groq implementation (OpenAI-compatible endpoint).
"""

from __future__ import annotations
import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class GroqClient:
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    BASE_URL      = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or self._resolve_key()
        self._model   = model or self.DEFAULT_MODEL

    @staticmethod
    def _resolve_key() -> str:
        key = os.environ.get("GROQ_API_KEY", "")
        if key:
            return key
        try:
            import streamlit as st
            key = st.secrets.get("GROQ_API_KEY", "")
            if key:
                return key
        except Exception:
            pass
        raise EnvironmentError(
            "GROQ_API_KEY not set. Add it in the sidebar or create a .env file."
        )

    def complete(self, system: str, user: str) -> str:
        from openai import OpenAI
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


def make_client(api_key: str | None = None) -> LLMClient:
    """Create a client with an optional runtime key override."""
    return GroqClient(api_key=api_key)
