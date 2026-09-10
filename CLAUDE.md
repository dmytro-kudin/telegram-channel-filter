## Specification-Driven Development (Spec Kit) Governance

This project follows a strict Spec-Driven Development workflow managed via Spec Kit artifacts located in `.specify/` and `specs/`.

### Core Rules for Claude
1. **Source of Truth:** The files `.specify/memory/constitution.md` and, per feature, `specs/<feature>/spec.md`, `plan.md`, and `tasks.md` (when present) are the absolute authorities on how features must behave. Do not guess or invent product behavior; consult these files first.
2. **Specification Consistency:** Implementation must match the active specification exactly. If a task or requirement is ambiguous, or a spec/plan/tasks file is missing or out of date, stop and use the Spec Kit workflow (`speckit-clarify`, `speckit-specify`, `speckit-plan`, `speckit-tasks`) to update it rather than assuming functionality.
3. **Root Cause & Tests:** If a test fails during implementation, find the root cause. Fix the application code if it diverges from the spec. Never alter a test case just to make a broken implementation pass unless the test itself violates the specification.
4. **Task-Bound Execution:** When executing implementation tasks, reference the specific steps in the active feature's `tasks.md`. Do not skip ahead or implement unassigned scope.
5. **Active Feature:** `.specify/feature.json` names the feature currently in progress (`feature_directory`). Confirm you are reading/updating the correct `specs/<feature>/` directory before making changes.
6. **No Coding Rules Here:** This file must never hold or duplicate coding rules, conventions, architecture decisions, tech stack choices, or style guides. All such rules live in `.specify/memory/constitution.md`. If asked to add a coding rule, add it to the constitution via `speckit-constitution` instead of writing it here.
7. **Spec Artifacts Are Generated, Not Hand-Edited:** Don't directly hand-edit `spec.md`, `plan.md`, `tasks.md`, or `constitution.md` to change requirements, design, or task scope. Use the corresponding Spec Kit skill (`speckit-specify`, `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-constitution`) so the artifacts stay internally consistent and traceable. Minor fixes (typos, formatting) are fine to edit directly.
8. **Consistency Checks:** After generating or editing tasks, or before implementing, run `speckit-analyze` to catch drift between `spec.md`, `plan.md`, and `tasks.md` before writing code.
9. **Constitution Changes Cascade:** If a change to `constitution.md` affects an in-progress feature's spec, plan, or tasks, re-run the relevant Spec Kit skill(s) to reconcile them — don't let the constitution and feature artifacts diverge silently.
10. **New Work Starts With a Spec:** For any new feature or non-trivial change, ensure a `specs/<feature>/spec.md` exists (create it via `speckit-specify`) before writing implementation code.
