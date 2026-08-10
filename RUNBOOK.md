# MedGuard Operating Runbook

> The living-system half of the product (Chapter 18). Code without an owner rots;
> this file names the owners, the on-call signals, the maintenance cadence, and the
> two emergency levers. Keep it versioned alongside the code and review it every
> quarter.
>
> **Disclaimer:** MedGuard is a teaching artifact, not a medical device.

## Ownership

Every subsystem has one accountable owner. "Everyone owns it" means no one does.

| Subsystem                         | Owner (role)          | Approves changes to        |
| --------------------------------- | --------------------- | -------------------------- |
| Golden set + eval harness         | Eval lead             | `evals/`, `eval/scoring.py`|
| Prompts + behavior bundles        | Agent lead            | `ops.py`, prompt versions  |
| Guardrails + safety rules         | Clinical safety owner | `guardrails.py`, dose ceilings |
| Grounding sources + citations     | Data/retrieval owner  | `grounding.py`, source index |
| Incident response / on-call       | On-call rotation      | kill switch, rollback      |
| Cost/latency budgets              | Platform owner        | `budget.py` ceilings       |

A change to `guardrails.py` or the dose ceilings requires review by the **clinical
safety owner** — no exceptions, however small the edit looks (Chapter 15).

## On-call signals (what pages you)

Alert on quality, not just system health — agent incidents are usually quiet
(Chapter 6). Page when any of these breach threshold:

- **Unsafe-approval rate** rises above baseline (the headline safety metric).
- **Eval drift**: online rolling score falls `>= 0.05` below baseline (`continuous.DriftMonitor`).
- **Escalation rate** spikes or collapses (either can signal a regression).
- **Cost/latency** p95 exceeds budget (`budget.BudgetTracker`).
- Ordinary error/timeout spikes from tools or the model provider.

## Emergency levers

1. **Kill switch** — degrade to human review without a deploy:
   ```python
   from medguard.ops import KillSwitch
   ks = KillSwitch(); ks.engage("provider incident 2026-07-15")
   # pass ks into review_end_to_end / review_case; every case now ESCALATES
   ```
2. **Rollback** — revert the whole behavior bundle to last-known-good:
   ```python
   registry.rollback()   # model + prompt + tools + guardrails, in one call
   ```
   Confirm the fix by **replaying** the offending request from its `trace_id`.

## Maintenance cadence

Maintenance is rhythmic, not reactive (Chapter 18):

- **On every provider model update:** revalidate against the golden set, then canary
  (Chapter 15) before full rollout. Never float on a model alias.
- **Weekly:** review incidents + post-mortems; turn each into a new golden case
  (`escalation.feedback_to_golden_case` → `continuous.merge_feedback`).
- **Monthly:** refresh the golden set from current production traffic so the
  benchmark tracks the real world (Chapter 16).
- **As libraries change:** update the framework appendices only — never the durable
  principles in the chapters.

## Release checklist (gated on evidence, not hope)

- [ ] Offline eval passes with **zero unsafe approvals** (`medguard-eval`).
- [ ] Full test suite green (`pytest`).
- [ ] New behavior bundle version assigned and recorded (`ops.BehaviorBundle`).
- [ ] Shadowed on real traffic with **no safety regressions** (`rollout.ShadowRunner.safe_to_promote()`).
- [ ] Canary slice healthy on safety metrics before widening.
- [ ] Rollback path verified; on-call briefed.
