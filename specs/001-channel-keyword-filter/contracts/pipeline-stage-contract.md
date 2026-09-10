# Contract: Message Processing Pipeline Stage

This is the extensibility seam required by FR-016/SC-008: "a new
content-handling rule can be added ... without modifying or re-testing the
behavior of existing rules." Any code that adds a new rule must conform to
this contract instead of editing the pipeline's control flow.

## Stage signature

A stage is a pure function:

```text
Stage: (post: ChannelPost) -> Outcome
```

- **Input**: only the `ChannelPost` being evaluated (see data-model.md). A
  stage MUST NOT perform its own database or network I/O — it receives
  everything it needs as an argument so it stays unit-testable with plain
  values.
- **Output**: exactly one `Outcome` variant (`Skip`, `BroadcastAll`,
  `MatchedUsers`, or `Continue` — see data-model.md).
- A stage MUST be a total function over any input string: it must not raise
  for any post content; unrecognized/irrelevant content returns `Continue`.
- A stage MUST NOT itself decide *who* is eligible to receive a
  notification — eligibility (`active AND NOT blocked`, data-model.md) is
  handled entirely outside the stage: the keyword-match stage's automaton
  is built only from eligible subscribers' keywords (research.md §6a), so
  its `MatchedUsers` result is correct by construction, and `BroadcastAll`
  is resolved against a fresh eligible-subscriber query only when the
  outcome is turned into deliveries. This keeps a stage's job limited to
  "does this rule apply to this post", never "who currently qualifies".

## Pipeline evaluation contract

The pipeline is an **ordered list** of stages, evaluated by a single runner:

1. Evaluate stages in list order.
2. The first stage to return anything other than `Continue` decides the
   outcome for the whole post; no later stage is evaluated (short-circuit,
   FR-016).
3. If every stage returns `Continue`, the pipeline's own default applies:
   for this feature, that default is the keyword-match stage itself, which
   never returns `Continue` (it always resolves to `MatchedUsers` — possibly
   empty — as the final stage in the list). A future stage may be inserted
   before it without changing this rule.

## Ordering for this feature (v1)

```text
[jar_link_stage, pure_number_stage, keyword_match_stage]
```

- `jar_link_stage`: `BroadcastAll` if the post contains the designated
  jar-link pattern, else `Continue`.
- `pure_number_stage`: `Skip` if the stripped post text is only digits and
  numeric punctuation (with at least one digit), else `Continue`.
- `keyword_match_stage`: always resolves — `MatchedUsers` with the automaton
  lookup result (already eligible-only by construction).

**Note**: the operator's `/broadcast` (FR-019, see contracts/admin-commands.md)
is deliberately outside this pipeline — it has no `ChannelPost` to evaluate
rules against. It resolves recipients the same way `BroadcastAll` does
(a fresh eligible-subscriber query) without going through any stage.

## Adding a new rule later

To add a rule (per FR-016/SC-008):

1. Write a new function matching the `Stage` signature above.
2. Insert it into the ordered list at the position that gives it the
   correct precedence relative to existing stages.
3. Do not modify any existing stage function's body.
4. Add unit tests for only the new stage; existing stage tests MUST continue
   to pass unmodified — that's the acceptance bar for "without modifying or
   re-testing the behavior of existing rules" (SC-008).
