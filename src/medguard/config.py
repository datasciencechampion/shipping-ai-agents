"""Configuration for MedGuard, read from the environment.

Kept intentionally tiny at v0. A ``.env`` file, if present next to the code, is
loaded with a minimal parser so there's no third-party dependency yet.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from a nearby .env into os.environ (no overwrite).

    Deliberately minimal — no quoting rules, no interpolation. Real projects use
    python-dotenv; we avoid the dependency at v0.
    """
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Config:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    fake: bool = True  # default to offline/deterministic until a key is present

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()
        api_key = os.environ.get("OPENAI_API_KEY") or None
        forced_fake = os.environ.get("MEDGUARD_FAKE", "").strip() in {"1", "true", "yes"}
        # Fake mode when explicitly forced, or when no credentials are available.
        fake = forced_fake or api_key is None
        return cls(
            provider=os.environ.get("MEDGUARD_PROVIDER", "openai").strip(),
            model=os.environ.get("MEDGUARD_MODEL", "gpt-4o-mini").strip(),
            api_key=api_key,
            fake=fake,
        )
