"""The model interface — MedGuard's single boundary to an LLM.

At v0 this is the *only* real machinery in the agent, which is precisely the
problem the book sets out to fix. Note what's absent: no retries, no timeout, no
cost/latency accounting, no tracing. Later chapters add all of it behind this
same boundary.
"""

from __future__ import annotations

from .config import Config

# A canned, deliberately DANGEROUS response used in deterministic fake mode.
# It reproduces the Chapter 1 post-mortem: a confident approval of a standard
# adult dose with no regard for the patient's renal function. It exists so
# readers (and tests) can see the failure without a live model or an API key.
_FAKE_DANGEROUS_REVIEW = """\
This prescription looks appropriate. {drug} is commonly co-prescribed with the \
patient's current medications and I do not see a significant interaction.

The proposed dose of {dose} is a standard adult dose and should be well \
tolerated. You can start the patient at this dose right away.

Overall assessment: safe to prescribe as written."""


def call_model(prompt: str, config: Config, *, context: dict | None = None) -> str:
    """Return the model's text completion for ``prompt``.

    In fake mode, returns a deterministic canned review (see above). Otherwise
    calls the configured provider. ``context`` is only used to personalize the
    fake output; a real provider gets everything it needs from ``prompt``.
    """
    if config.fake:
        return _fake_completion(context or {})
    if config.provider == "openai":
        return _openai_completion(prompt, config)
    raise ValueError(f"Unknown provider: {config.provider!r}")


def _fake_completion(context: dict) -> str:
    proposed = context.get("proposed", {}) if isinstance(context, dict) else {}
    drug = proposed.get("drug", "the proposed medication")
    dose = proposed.get("dose", "the proposed dose")
    return _FAKE_DANGEROUS_REVIEW.format(drug=drug, dose=dose)


def _openai_completion(prompt: str, config: Config) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "The 'openai' package is not installed. Install it with "
            '`pip install -e ".[openai]"`, or run in fake mode (MEDGUARD_FAKE=1).'
        ) from exc

    client = OpenAI(api_key=config.api_key)
    # v0 naivety on display: a single call, default settings, no error handling.
    completion = client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content or ""
