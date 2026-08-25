"""Thin Anthropic Messages adapter (Appendix B). The core never imports this module."""

from __future__ import annotations

import os


class AnthropicAdapter:
    def __init__(self, *, api_key: str | None = None, model: str = "claude-sonnet-4-5"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model

    def complete(self, prompt: str) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                'Install the Anthropic extra: pip install -e ".[anthropic]"'
            ) from exc
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        client = Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        block = message.content[0]
        return getattr(block, "text", "") or ""
