# Contract: Guided and Comma-Separated Keyword Add

Extends `/add` from `specs/001-channel-keyword-filter/contracts/bot-commands.md`.
The per-word validation rules there (min length 3, 20-keyword cap, dedup) are
unchanged and are not repeated in full here — this contract only covers what's
new: multi-word input and the guided entry point.

## Shared parsing rule (both entry points)

Given raw input text:
1. Split on `,`.
2. Strip leading/trailing whitespace from each piece.
3. Drop empty pieces (e.g. from `"foo,,bar"` or a trailing comma).
4. If zero non-empty pieces remain, treat it exactly as today's "no argument"
   case for `/add` (`ADD_TOO_SHORT` reply) — not a new error state.
5. Run each surviving piece through the existing `db.add_keyword` once,
   independently — one piece's outcome MUST NOT affect another piece's
   evaluation in the same batch (FR-005), including the 20-keyword cap: once
   the cap is reached mid-batch, every subsequent new word in that same batch
   is reported as limit-reached, exactly as if added one at a time in order.
6. Reply with one line per submitted piece, stating its outcome: added /
   already exists / too short / limit reached — reusing the existing
   per-outcome message text from `messages.py`, not new wording per outcome.

## `/add <word>[, <word>, ...]` (typed)

**Input**: one or more comma-separated words as the command argument.

**Behavior**: Applies the shared parsing rule above to `command.args`.

**Reply**: The per-word summary described above. A single-word input
produces a single-line reply, unchanged from today's `/add <word>` behavior
(FR-006).

## Guided add (➕ Додати слово button)

**Trigger**: Subscriber taps ➕ Додати слово from the persistent menu
(`button-menu.md`).

**Behavior**:
1. Bot replies asking for one or more words, comma-separated, and marks this
   chat as awaiting add-keyword input (transient, in-memory — data-model.md
   "Guided-add FSM state").
2. The subscriber's next message, whatever its content, is treated as the
   input and passed through the shared parsing rule above. This applies
   even if the message looks like it could be something else (e.g. numeric
   text) — while awaiting input, it is always attempted as keyword(s).
3. After processing (success, partial success, or complete rejection), the
   awaiting-input flag is cleared unconditionally — a second message
   afterward is treated as ordinary input again, not as another batch.

**Cancellation**: If the subscriber instead taps a different menu button (or
sends any other recognized command) while awaiting input, that action
proceeds normally on its own terms and the awaiting-input flag is cleared —
the abandoned prompt's input is never merged into whatever the subscriber
did instead (Edge Cases, spec.md).

**Reply**: Same per-word summary format as the typed path (step 6 above).

## Cross-cutting rules

- A blocked subscriber tapping ➕ or typing `/add` gets the same `BLOCKED`
  reply as any other action — the guided flow is never entered for a
  blocked subscriber (mirrors `refuse_if_blocked` on the typed command).
- All new prompts and summary lines are in Ukrainian (FR-025, unchanged
  project-wide rule).
