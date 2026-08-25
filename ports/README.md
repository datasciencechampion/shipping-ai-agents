# Ports — one slice, not a second MedGuard

Canonical MedGuard is `src/medguard/` (tags `v0`–`v5.2`). These ports share **one**
runnable slice: the same tools, the same structured decide, the **same golden
set**, and the independent dose-ceiling veto **after** the reasoner.

They are not 15 extra git tags and not four full rewrites.

## What each folder is

| Path | Role | Offline command |
| --- | --- | --- |
| `ports/slice.py` | Shared v4.1 path: `run_medguard_core` then `apply_independent_veto` | `PYTHONPATH=src:. python -m ports.run_eval` |
| `ports/openai/` | OpenAI Python SDK **adapter only** (`complete`) | `PYTHONPATH=src:. python -m ports.openai` |
| `ports/anthropic/` | Anthropic Python SDK **adapter only** | `PYTHONPATH=src:. python -m ports.anthropic` |
| `ports/langgraph/` | Graph node calls MedGuard core; veto after `invoke` | `PYTHONPATH=src:. python -m ports.langgraph` |
| `ports/adk/` | Google ADK: MedGuard as a tool; veto in Python | `PYTHONPATH=src:. python -m ports.adk` |
| `ports/agno/` | Agno: MedGuard as a tool; veto in Python | `PYTHONPATH=src:. python -m ports.agno` |

Every `__main__` above runs the golden-set safety gate on `review_v41` (no API
key). Expect **100% / 0 unsafe**, same as `medguard-eval --agent v41 --fake`.

## Adapters vs wrappers

- **OpenAI / Anthropic:** `OpenAIAdapter.complete` / `AnthropicAdapter.complete`
  match Appendix B. They are not used by the eval slice. Plug them into *your*
  `decide` if you want a live model; still call `apply_independent_veto` after.
- **LangGraph / ADK / Agno:** the framework may orchestrate. The veto is ordinary
  MedGuard code **outside** the model. Do not prompt the model to enforce the
  dose ceiling.

## Optional installs (live SDKs / frameworks)

```bash
pip install -e ".[openai]"       # OpenAIAdapter
pip install -e ".[anthropic]"    # AnthropicAdapter
pip install -e ".[langgraph]"    # build_graph / review_via_langgraph
pip install google-adk           # ports.adk.build_agent
pip install agno                 # ports.agno.build_agent
```

Framework `build_*` helpers track moving APIs. If a constructor fails after an
upstream release, `review()` / `review_v41` is still the slice the book means.
