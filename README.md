# EB-1 Package Auto-Evolving Agent System

This repository contains a Python reference implementation of a policy-driven, self-evolving EB-1 package generator. The system does **not** train LLMs; instead, it evolves deterministic policies based on attorney edits.

## Modules

### Package Generation Agent
- **PlannerAgent** builds a generation plan using applicant signatures and active policies.
- **DraftingAgent** creates draft documents that follow the plan.
- **RAGAgent** mocks retrieval of similar cases and exhibits.
- **VerifierAgent** enforces hard policy constraints and rejects violating drafts.
- `profile_from_resume(resume_text, case_id)` deterministically derives profile hints from a resume.
- `generate_package(applicant_profile, policies)` produces a constrained `DraftPackage`.
- `generate_package_from_resume(resume_text, policies, case_id)` is the resume-to-package entry point.

### Structured Diff Engine
- Parses draft and attorney-final packages.
- Loads packages from text or PDF files via `PackageLoader`.
- Aligns segments and extracts edit distance signals.
- Attributes edits to deterministic reason codes.
- Emits `ReviewEvent` records suitable for downstream aggregation and persists them with `DiffDatabase`.

### Policy Evolution Engine
- **SignalStore** captures incoming review events.
- **PatternAggregator** converts events to `FailurePattern` summaries.
- **PolicyCompiler** deterministically converts patterns into `Policy` records.
- **PolicyStore** tracks versioned policies that can be applied to future generations.
- `evolve_and_activate_policies` runs aggregation -> compilation -> activation in one call.

## Data Models

Core schemas are implemented as dataclasses in `policy_doc_agent.models`:
- `DraftPackage` with nested `DraftDocument` and `DraftSegment`
- `ReviewEvent`, `FailurePattern`, and `Policy`
- `PlannerPlan` for the planner output

## Notes

- Policy evolution is deterministic and auditable.
- Generation is constrained by policies; no model training occurs in the loop.
