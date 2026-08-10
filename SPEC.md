# MedGuard — Product & System Spec (one page)

> Teaching artifact for _Shipping AI Agents to Production_. **Not a medical
> device.** Never use for real clinical decisions.

## One-liner

Given a patient's current medications plus a **proposed new prescription**,
MedGuard flags drug–drug interactions, contraindications, and dosage problems,
**grounds** each finding in an authoritative source, and **escalates** anything
uncertain or high-severity to a human pharmacist.

## Who uses it, and why reliability is life-or-death

- **Primary user:** a prescribing clinician (or a pharmacist reviewing an order)
  who wants a fast second check before a prescription is finalized.
- **Stakes:** a missed interaction or a wrong dose can cause real patient harm.
  A confident-but-wrong answer is worse than no answer, because it *displaces*
  the human's own caution. This is exactly why the book uses MedGuard: every
  reliability technique has an obvious, human cost when it's absent.

## Inputs / outputs

**Input** (one "case"):
- `patient`: age, weight, sex, relevant conditions, renal/hepatic function
  markers (e.g. eGFR).
- `current_medications`: list of `{drug, dose, route, frequency}`.
- `proposed`: a single `{drug, dose, route, frequency}` to be checked.

**Output** (a "review"):
- `verdict`: one of `APPROVE`, `FLAG`, `ESCALATE`.
- `findings`: list of `{type, severity, explanation, citation}` where `type ∈
  {interaction, contraindication, dosing}` and `severity ∈ {low, moderate,
  high}`.
- `confidence`: calibrated 0–1.
- `trace_id`: correlates to the full execution trace.

## Core behaviors

1. **Interaction check** — proposed drug vs. each current medication.
2. **Contraindication check** — proposed drug vs. patient conditions.
3. **Dose check** — proposed dose vs. safe range, adjusted for renal/hepatic
   function and weight/age.
4. **Ground & cite** — every finding points to a trusted source.
5. **Decide & escalate** — abstain and route to a human when uncertain or when
   any high-severity finding is present.

## The v0 → v5 arc (what each stage adds)

| Stage | What changes | Book chapter |
| ----- | ------------ | ------------ |
| `v0`  | Naive single LLM call → prose. No checks, no citations. **Deliberately unsafe.** | Ch 1 |
| `v1`  | Golden dataset + eval harness | Ch 3 |
| `v2`  | Structured tracing + replay | Ch 5 |
| `v3`  | Bounded state machine; grounding; hardened tools; bounded memory | Ch 7–10 |
| `v4`  | Escalation; independent dosage-bounds veto; cost/latency budget; auditable data flow | Ch 11–14 |
| `v5`  | Shadow/canary rollout; continuous eval; scaling | Ch 15–17 |

## Reference architecture (target state)

See `../images/ch02-reference-architecture.svg`. Components, each behind a small
interface so the core stays framework-agnostic:

- **Orchestrator / control loop** — drives the review; bounded steps.
- **Model interface** — provider-agnostic `call_model()`.
- **Retrieval & grounding** — authoritative drug/interaction sources + citations.
- **Tools / actions** — interaction checker, dose calculator (validated I/O).
- **Memory / state** — per-case, access-controlled, retention-bounded.
- **Policy & guardrails** — input/output validation; independent dose-bounds veto.
- **Human-in-the-loop** — escalation queue + feedback capture.
- **Evaluation hooks** — offline + online scoring against the golden set.
- **Telemetry / tracing** — structured, replayable, PHI-redacted.

## Non-goals (for the book's scope)

- Not a real clinical knowledge base — data is illustrative/fixture-based.
- Not a UI product — we focus on the agent/system, not the front end.
- Not legal/compliance guidance — Ch 14 teaches principles only.

## Design invariants (must always hold)

- Never emit a recommendation above a hard dose ceiling (independent check, ≥ v4).
- Never present an unverified citation as verified (≥ v3.1).
- A tool error is never silently treated as "no problem found" (≥ v3.2).
- Every decision is reconstructable from its trace (≥ v2).
