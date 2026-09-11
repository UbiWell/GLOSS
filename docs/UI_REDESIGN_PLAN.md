# Plan: rebuild the GLOSS dashboard

## Context

Tutorial feedback was that the UI is poor, and that people want to see what the
agents are actually doing — the interactions between them, the code being
generated, and how memory builds up. Today the dashboard shows five narrow
columns of text and hides the most interesting part of the system.

This plan has two halves: make the pipeline *observable* (the data mostly isn't
captured today), then rebuild the UI on native Streamlit components.

## What is wrong now, concretely

Read from `sensemaking_ui.py` as it stands:

| Problem | Where | Why it matters |
|---|---|---|
| Five equal columns for prose, JSON and code | `:176` `st.columns(5)` | Each panel is ~1/5 of the width. This is the main "looks bad" complaint. |
| Hand-rolled HTML with hardcoded pastel backgrounds and `color: black` | `:110-168` | Ignores the Streamlit theme, unreadable in dark mode, and looks unfinished. |
| Content interpolated into HTML **unescaped** | `:358-393`, e.g. `'<div>{}</div>'.format(memory)` | `memory` contains generated Python and JSON. Any `<`, `>` or `&` corrupts the layout. This is a rendering bug, not a style preference. |
| Blocking poll loop | `:398-401` `while ...: time.sleep(1)` | Holds the script thread for the whole run, so widgets are dead and there is no way to cancel. |
| "Open in New Tab" writes a file on the server and calls `webbrowser.open` | `:219-311`, `:315-346` | Does nothing for a remote participant, and writes `page.html` into their checkout. |
| `reset_state()` clears only `sense_maker` | `:29-32` | `status` / `sensemaker_running` survive, so a second run is fragile and `:399` can raise. |
| No error surface | — | If a stage fails the dashboard spins silently. With a shared model this is the common case, not the rare one. |
| Duplicate/unused imports | `:1`, `:209-217` | `os` three times, `webbrowser` twice, `streamlit` re-imported, `base64` unused. |

## What data exists, and what has to be captured

**Already on `SenseMaker`** and shown (badly): `current_step`, `step_history`,
`action_plan`, `information_request`, `memory`, `understanding`,
`function_calls`, `answer`.

**Already produced but thrown away — the important find.**
`agents/coding_agent.py` returns autogen's `TaskResult`, whose `.messages` hold
the whole round-robin: the code the assistant proposed, the executor's stdout,
and any retry after a failure. `data_streams/generic_coding_functions.py:99`
keeps only `messages[-2] + messages[-1]` as one concatenated string, which is
then appended to `memory`. So "show the generated code" needs no new
capability, just retaining what is already in hand — and it explains why memory
currently reads as a mangled blob.

**Not captured anywhere yet:** per-call latency and token counts (though
`agents/local_model.py`'s `chat()` already returns `prompt_eval_count`,
`eval_count` and the serving worker in its metadata), per-stage timings, and
exceptions.

## Phase 1 — an observability layer (no UI work)

New `agents/run_trace.py` holding an append-only event log.

```python
RunTrace.event = {"seq", "ts", "stage", "kind", "payload"}
# kinds: stage_start, stage_end, llm_call, code_proposed, code_output,
#        db_query, error, answer
```

- `SenseMaker` gains `self.trace = RunTrace()`. Each stage runs inside a
  context manager that records start, end, duration and any exception.
- `generic_coding_functions` hands the `TaskResult` messages to the trace as
  `code_proposed` / `code_output` events instead of discarding them. Its return
  value stays byte-identical so the pipeline's behaviour does not change.
- `agents/local_model.py` records an `llm_call` event per request: stage, model,
  latency, prompt and completion tokens, serving worker, and whether it was a
  retry.
- Thread-safe (`deque` + `Lock`): the worker thread writes while the UI thread
  reads.
- **Opt-in and side-effect free.** With no trace attached, every code path
  behaves exactly as today, so the CLI is unaffected.

Deliverable: `python sensemaking_process.py` optionally dumps a trace JSON, and
the UI consumes the same structure. Being able to diff two runs' traces is
useful for the tutorial independently of the UI.

## Phase 2 — rebuild the UI on native components

One file, `sensemaking_ui.py`. Sidebar for input and controls; main area as
`st.tabs`:

- **Overview** — `st.status` per stage, flipping spinner → tick as it
  completes, the final answer in a prominent container, elapsed time, and a
  `st.metric` row: LLM calls, tokens, code executions, iterations used.
- **Agent activity** — the "see the interactions" ask. A chronological feed of
  `llm_call` events rendered with `st.chat_message`: which agent spoke, how long
  it took, tokens, and the decision it returned.
- **Generated code** — per code round, `st.code(..., language="python")` beside
  the executor's output, with pass/fail and the retry chain visible. This is the
  part of GLOSS people most want to see and currently cannot.
- **Memory / Understanding** — the same text, escaped properly, with
  `st.download_button` replacing the broken new-tab feature.
- **Data** — `function_calls` as an `st.dataframe` (function, database, params,
  rows returned) instead of `<li>` items.
- **Trace** — the raw event table plus a JSON download.

Mechanics:

- Live updates via `@st.fragment(run_every="1s")` on the live panels, replacing
  the blocking loop. Verified available in the pinned Streamlit 1.39.
- A **Stop** button, backed by a `threading.Event` checked between stages.
- No inline colours. Define a theme in `.streamlit/config.toml` and let light
  and dark mode work. Avoid `st.badge` (1.44+; this deployment is 1.39).
- Fix `reset_state()` to clear all run keys so a second run is clean.

## Phase 3 — tutorial affordances

- Three or four example-query buttons, so a participant gets a real result in
  one click instead of composing a query first.
- A one-paragraph "what am I looking at?" expander per tab.
- An explicit error panel carrying the real message — in particular the
  gateway's own text, which names the permitted models on a 403.

## Risks and constraints

- **Don't break the CLI.** Tracing is additive and optional; `make_sense()`
  keeps working with no trace.
- **The worker thread has no Streamlit context**, so it must never call `st.*`.
  The trace is the only channel. This is already true of today's code.
- **Version ceiling.** Streamlit is pinned at 1.39 by `environment_linux.yml`.
  Changing it forces a full image rebuild on the server, so stay within 1.39's
  API.
- **Keep it readable.** Participants read this file; prefer obvious native
  widgets over clever layout.
- The answer must not change. The pipeline is verified against known values and
  this work should not touch decision logic.

## Verification

1. The verified query still returns the same answer: 20 sent / 17 received /
   23.996 h at home.
2. A code-generation query shows the generated Python *and* the executor output
   in the Generated code tab.
3. With a deliberately bad `GATEWAY_API_KEY`, the UI shows a clear error rather
   than spinning.
4. Legible in dark mode and in a narrow window.
5. Two participants (p01 and p02) run simultaneously with no shared state.
6. Stop actually stops, and a second run starts clean.

## Rough effort

Phase 1 is the load-bearing half and is mostly mechanical: perhaps a day,
most of it in wiring the trace through without changing behaviour. Phase 2 is
a day. Phase 3 is small. Phase 1 is worth doing even if the UI work slips,
because the trace JSON is independently useful for teaching.
