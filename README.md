# MedGuard — companion reference agent

MedGuard is the running example for _Shipping AI Agents to Production_: a
medication-safety agent that, given a patient's current medications and a
proposed new prescription, flags interactions, contraindications, and dosage
problems — and escalates uncertain cases to a human pharmacist.

The book takes MedGuard from a naive demo (`v0`) to a production-grade system
(`v5`). Each stage is a **git tag**, so you can check out exactly the code a
chapter describes.

> **Disclaimer:** MedGuard is a teaching artifact. It is not a medical device
> and must never be used for real clinical decisions.

## Version → chapter map

| Tag    | Stage                                   | Chapter |
| ------ | --------------------------------------- | ------- |
| `v0`   | Naive single-call demo                  | Ch 1    |
| `v1`   | Eval harness + golden dataset           | Ch 3    |
| `v1.1` | Deterministic tests + trace replay      | Ch 4    |
| `v2`   | Full tracing + incident replay          | Ch 5    |
| `v2.1` | Kill switch + versioned rollback        | Ch 6    |
| `v3`   | Bounded state machine                   | Ch 7    |
| `v3.1` | Grounded, cited recommendations         | Ch 8    |
| `v3.2` | Hardened interaction-checker tool       | Ch 9    |
| `v3.3` | Bounded, auditable memory               | Ch 10   |
| `v4`   | Uncertainty-triggered escalation        | Ch 11   |
| `v4.1` | Independent dosage-bounds veto          | Ch 12   |
| `v4.2` | Cost/latency budget + model cascade     | Ch 13   |
| `v4.3` | Auditable, isolated data flows          | Ch 14   |
| `v5`   | Shadow deploy + canary rollout          | Ch 15   |
| `v5.1` | Continuous evaluation flywheel          | Ch 16   |
| `v5.2` | Concurrency, rate limits, backpressure  | Ch 17   |

## Design intent

- **Framework-agnostic core.** The agent's control loop, tools, grounding,
  guardrails, and eval hooks are plain code behind small interfaces. Framework
  ports (LangGraph, vendor SDKs) live in the book's appendices.
- **Every subsystem is inspectable.** Tracing, evals, and guardrails are
  first-class, not bolted on.

## Layout (v0)

```
code/
  README.md                     # this file
  SPEC.md                       # one-page product & system spec
  pyproject.toml                # package metadata; openai is an optional extra
  .env.example                  # copy to .env for a real provider
  src/medguard/
    config.py                   # env-driven config (+ tiny .env loader)
    model.py                    # the single model boundary (call_model)
    agent.py                    # v0 naive single-call review
    cli.py                      # `medguard` command-line entry point
  src/medguard/eval/
    verdict.py                  # prose -> APPROVE/FLAG/ESCALATE (stopgap extractor)
    scoring.py                  # stratified scorer; tracks unsafe approvals
    run.py                      # `medguard-eval` command-line entry point
  examples/
    renal_overdose.json         # the Chapter 1 post-mortem case
    simple_interaction.json     # an easy case a demo handles well
  src/medguard/testing.py       # snapshot / trace-replay helpers
  src/medguard/trace.py         # v2: structured spans, trace_id, PHI redaction
  src/medguard/ops.py           # v2.1: behavior bundle registry, rollback, kill switch
  src/medguard/types.py         # v3: structured Review / Finding
  src/medguard/tools.py         # v3: interaction/contraindication tools; v3.2: reliability wrapper
  src/medguard/pipeline.py      # v3: bounded state machine -> structured verdict
  src/medguard/grounding.py     # v3.1: source store + citation verification
  src/medguard/memory.py        # v3.3: bounded, isolated, auditable session store
  src/medguard/escalation.py    # v4: confidence routing, review queue, feedback loop
  src/medguard/guardrails.py    # v4.1: independent dose-ceiling veto + injection scan
  src/medguard/budget.py        # v4.2: cost/latency budget tracker + model cascade
  src/medguard/audit.py         # v4.3: data-flow boundary + PHI-safe audit trail
  src/medguard/rollout.py       # v5: shadow mode + canary routing + promote gate
  src/medguard/continuous.py    # v5.1: online sampling + drift monitor + feedback merge
  src/medguard/runtime.py       # v5.2: rate limit + backpressure + safe degradation + concurrency
  src/medguard/capstone.py      # Ch 19: review_end_to_end composing every subsystem
  evals/
    golden_set.json             # 15 labeled cases (12 safe, 3 dangerous)
  tests/                        # deterministic + snapshot/replay tests (106 total)
    fixtures/v0_golden_outputs.json
```

> The code evolves cumulatively in this single tree (v0, v1, v1.1, v2, v3, v4.1
> coexist). Git tags `v0` … `v5.2` mark the chapter each stage was introduced;
> use `--agent` (for example `--agent v0` or `--agent v41`) to run that stage.

## Walk every remaining stage

The printed book (Appendix H) walks **v0 → v1 → v4.1** in detail. That is the
thesis: a dangerous demo, a number that exposes the tail, then a veto that makes
the approval impossible.

This section is the rest of the map. Stay in the venv from setup. The tree is
cumulative, so you do not need a new checkout for each command. `pytest -q`
prints one `.` per passing test; `N passed` means that chapter's property still
holds.

| Tag | Chapter | Command | What to notice |
| --- | --- | --- | --- |
| `v1.1` | Testing | `pytest -q tests/test_replay.py tests/test_verdict.py tests/test_scoring.py tests/test_agent.py` | `test_replayed_scoring_reproduces_the_dangerous_tail` pins the 80% / 3-unsafe result |
| `v2` | Observability | `pytest -q tests/test_trace.py` | PHI is `***REDACTED***` on spans (`redact` in `src/medguard/trace.py`) |
| `v2.1` | Incidents | `pytest -q tests/test_ops.py` | Kill switch returns `ESCALATE`, not an exception |
| `v3` | Control flow | `medguard-eval --agent v3` then `pytest -q tests/test_pipeline.py` | About 93%, **1 unsafe** (renal overdose). Structured flow, no dose veto yet |
| `v3.1` | Grounding | `pytest -q tests/test_grounding.py` | Invented citations force `ESCALATE` |
| `v3.2` | Tools | `pytest -q tests/test_tools_reliability.py` | Missing `drug` is a `ToolError` |
| `v3.3` | Memory | `pytest -q tests/test_memory.py` | Sessions cannot see each other's keys |
| `v4` | Human-in-the-loop | `pytest -q tests/test_escalation.py` | Low confidence routes to a human |
| `v4.1` | Guardrails | `medguard-eval --agent v41` | 100%, **0 unsafe** (already in Appendix H) |
| `v4.2` | Cost / latency | `pytest -q tests/test_budget.py` | Budget overrun is a tracked failure |
| `v4.3` | Security | `pytest -q tests/test_audit.py` | Name / MRN stripped from the provider payload |
| `v5` | Rollout | `pytest -q tests/test_rollout.py` | Candidate that *approves* where current *escalates* is a safety regression |
| `v5.1` | Continuous eval | `pytest -q tests/test_continuous.py` | Unsafe-approval rate on a live sample |
| `v5.2` | Scaling | `pytest -q tests/test_runtime.py` | Token bucket limits; overload degrades to a safe verdict |
| Capstone | Ch 19 | `pytest -q tests/test_capstone.py` then `pytest -q` | Chapter 1 overdose cannot be approved; full suite stays green |

## Running the tests (v1.1)

The suite is deterministic, offline (no API key), and sub-second:

```bash
cd shipping-ai-agents
python3 -m venv .venv && .venv/bin/pip install pytest   # once
.venv/bin/python -m pytest -q                            # 106 tests
```

It unit-tests the prompt builder, verdict extractor, and scorer, documents the
extractor's known negation weakness as a tripwire, and uses snapshot/replay tests
to reproduce Chapter 3's safety result without calling a model.

## Running the eval harness (v1)

The harness scores MedGuard against the golden set, **stratifies by severity**,
and exits non-zero on any unsafe approval (so it can gate CI):

```bash
cd shipping-ai-agents
PYTHONPATH=src python3 -m medguard.eval.run --golden evals/golden_set.json --fake
# v0 scores 80% overall while approving all 3 dangerous cases -> FAIL (exit 1)
```

After `pip install -e ".[openai]"`, the same run is just `medguard-eval`.

Compare the safety progression across agent versions with `--agent`:

```bash
PYTHONPATH=src python3 -m medguard.eval.run --agent v0  --fake   # 80%, 3 unsafe -> FAIL
PYTHONPATH=src python3 -m medguard.eval.run --agent v3  --fake   # 93%, 1 unsafe -> FAIL
PYTHONPATH=src python3 -m medguard.eval.run --agent v41 --fake   # 100%, 0 unsafe -> PASS
```

## Setup & running

MedGuard v0 runs with **zero dependencies** in deterministic *fake* mode — no
network, no API key — which is perfect for reading the code and reproducing the
Chapter 1 post-mortem:

```bash
cd shipping-ai-agents
PYTHONPATH=src python -m medguard.cli --case examples/renal_overdose.json --fake
```

To run the finished **v5 end-to-end pipeline** (Chapter 19) — structured verdict,
grounding, the independent dose-ceiling veto, confidence routing, and a redacted
audit record — add `--end-to-end`:

```bash
PYTHONPATH=src python -m medguard.cli --case examples/renal_overdose.json --end-to-end
# v0 approved this dangerous case; the finished system ESCALATES it (veto) and
# emits a PHI-redacted audit record.
```

To run against a real model provider:

```bash
cp .env.example .env          # then set OPENAI_API_KEY
pip install -e ".[openai]"    # installs the optional provider SDK + console script
medguard --case examples/renal_overdose.json
```

If no API key is present, MedGuard automatically falls back to fake mode.

## Get the code

```bash
git clone https://github.com/datasciencechampion/shipping-ai-agents.git
cd shipping-ai-agents
```

This repository is the standalone companion code for the book; the repository
root is the MedGuard package. Run all commands above from that root.

## License

Code in this repository is licensed under the **Apache License 2.0** (see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE)).

> **Medical disclaimer.** MedGuard is a teaching artifact, not a medical device.
> It is not clinically validated and must never be used for real clinical,
> prescribing, or patient-care decisions. All patient data and drug rules here
> are simplified and illustrative. The software is provided "AS IS", without
> warranty of any kind.

## Contributing

Issues and pull requests are welcome. Because the safety gate is the point of
the project, changes should keep `pytest` green and keep the eval harness at
**zero unsafe approvals** for the finished agent (CI enforces both).
