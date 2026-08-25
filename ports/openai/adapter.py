"""Thin OpenAI chat adapter (Appendix B). The core never imports this module."""

from __future__ import annotations

import os


class OpenAIAdapter:
    def __init__(self, *, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def complete(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                'Install the OpenAI extra: pip install -e ".[openai]"'
            ) from exc
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = OpenAI(api_key=self.api_key)
        completion = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content or ""
