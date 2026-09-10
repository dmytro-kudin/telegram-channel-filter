<!--
Sync Impact Report
Version change: (none) → 1.0.0
Modified principles: n/a (initial ratification)
Added sections:
  - Core Principles: I. No Assumptions, No Inferred Intent
  - Core Principles: II. Explicit, Typed Error Handling
  - Core Principles: III. Typed Domain Values Over Raw Primitives
  - Core Principles: IV. Cross-Cutting Concerns Stay Out of Business Logic
  - Coding Standards
  - Development Workflow: Test-Driven Development (Superpowers TDD Protocol)
  - Governance
Removed sections: none
Deferred items: none
Templates requiring follow-up: none checked in this run — dependent templates
  read this file at runtime and were not modified per scope guard.
-->

# telegram-channel-filter Constitution

## Core Principles

### I. No Assumptions, No Inferred Intent
Agents MUST NOT act on assumptions, guesses, or inferred user intent. When a
requirement, instruction, or specification is ambiguous or incomplete, the
agent MUST ask a clarifying question or stop and request explicit direction
before proceeding with implementation.
Rationale: unstated assumptions compound into defects and rework that are far
more expensive to detect after code is written; requiring explicit
confirmation keeps every behavior traceable to an actual decision instead of
a guess.

### II. Explicit, Typed Error Handling
Expected, recoverable failures (validation errors, not-found, external API
rejections, rate limits) MUST be represented as explicit return values —
either a `Result`/`Either`-style type or a narrow, well-defined exception
type documented at the function boundary — and MUST NOT be silently
swallowed with a bare `except:`/`except Exception:` that discards the cause.
Exceptions MUST be reserved for truly exceptional, unrecoverable conditions
(programmer errors, corrupted invariants), not for normal control flow.
Callers MUST handle or explicitly propagate every documented failure case;
handling it MUST NOT be optional by omission.
Rationale: expected failures are part of normal control flow and must be
represented as values or documented types so every caller is forced to
confront them, instead of failures being discovered only in production logs.

### III. Typed Domain Values Over Raw Primitives
Domain concepts (e.g., a channel ID, a filter rule, a message score) MUST be
modeled as `dataclass`/`NamedTuple`/`NewType` value objects rather than
passed around as bare `str`, `int`, or `dict` once they cross a module
boundary where their domain meaning matters. Value objects MUST validate
their invariants at construction time.
Rationale: typed domain primitives make illegal states unrepresentable and
centralize validation at the type level instead of scattering ad-hoc checks
across call sites.

### IV. Cross-Cutting Concerns Stay Out of Business Logic
Logging, input validation, retries, and similar cross-cutting concerns MUST
be implemented as reusable decorators, context managers, or middleware —
never embedded ad hoc inside individual business-logic functions. Business
logic functions MUST remain free of these concerns except for calling
already-validated inputs.
Rationale: separating cross-cutting concerns from business logic keeps core
logic testable in isolation and prevents the same concern from being
implemented inconsistently across the codebase.

## Coding Standards

- Module and package layout MUST match the logical structure of the code
  (a module's location reflects what it contains); do not scatter related
  logic across unrelated directories.
- Every public function and method MUST have complete type hints (parameters
  and return type); `Any` MUST be justified with a comment when used.
- Entities and value objects MUST be implemented as `dataclass` (frozen where
  the value is immutable) or `NamedTuple`, not as loose dicts or tuples.
- Async code (`async def`) MUST NOT perform blocking I/O or CPU-bound work
  directly; blocking calls MUST be dispatched via `asyncio.to_thread` or an
  async-native equivalent so the event loop is never stalled.
- Repetitive per-type logic (formatting, parsing, validation repeated across
  call sites for the same type) MUST be implemented as a shared function or
  decorator rather than duplicated inline at each call site.
- Shared constants, message templates, and configuration values MUST be
  defined once and imported, never duplicated or re-typed at each usage site.

## Development Workflow

### Test-Driven Development (Superpowers TDD Protocol)

1. **Strict RED-GREEN-REFACTOR Cycle:**
   - **RED (Failing Test First):** Before writing production logic for any task in
     `tasks.md`, write a minimal failing test that asserts the desired behavior.
     Run the test suite and confirm it fails for the expected reason.
   - **GREEN (Minimal Fix):** Write the smallest amount of production code
     required to flip the test from RED to GREEN. Do not add extra
     abstractions or unrequested scope.
   - **REFACTOR (Clean Up):** Refactor the implementation for clarity and
     performance while keeping all tests passing.

2. **Non-Negotiable TDD Guardrails:**
   - **No Pre-Written Code:** Logic written prior to a failing test is
     non-compliant and MUST be discarded or rewritten test-first.
   - **Assert Behavior, Not Mocks:** Tests MUST assert against real outputs
     and domain behavior rather than internal implementation details.
   - **Test First Verification:** Never skip running the failing test phase;
     a test passing on its first run without new logic proves the test is
     invalid or redundant.

3. **Task Completion Gating:**
   - A checkbox in `tasks.md` may ONLY be updated from `- [ ]` to `- [x]`
     after the RED-GREEN-REFACTOR cycle completes successfully and `pytest`
     (the project test command) passes cleanly.

Rationale: gating task completion on an enforced RED-GREEN-REFACTOR cycle
keeps every implementation task backed by a test that failed for the right
reason before it passed, preventing untested or speculative code from being
marked done.

## Governance

This constitution supersedes all other project practices, style guides, and
prior undocumented conventions. Amendments require: (1) a documented
rationale, (2) an update to this file via `/speckit-constitution`, (3) a
version bump per the versioning policy below, and (4) a recorded Sync Impact
Report in the amendment commit.

Versioning policy (semantic versioning applied to this document):
- MAJOR: backward-incompatible principle removal or redefinition.
- MINOR: a new principle added or existing guidance materially expanded.
- PATCH: clarifications, wording, or typo fixes with no semantic change.

Compliance: all pull requests and code reviews MUST verify adherence to these
principles. Any deviation MUST be explicitly justified in the PR description;
unjustified deviations MUST be rejected in review.

**Version**: 1.0.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-09-10
