"""
Append-only event log for one sensemaking run.

The pipeline already produces far more detail than it reports: the coding
agent's whole conversation, per-call model latency and token counts, and which
stage was active when something failed. This module collects that as a
structured list of events so a UI (or a curious participant) can see what
actually happened, without changing how the pipeline behaves.

Design constraints:

- **Opt-in and side-effect free.** When no trace is active, every hook here is a
  no-op returning immediately, so the CLI path is unchanged.
- **Thread-safe.** ``SenseMaker.make_sense`` runs on a worker thread while the
  Streamlit script thread reads the trace to render it.
- **Never raises into the pipeline.** A bug in instrumentation must not break a
  run, so recording is wrapped defensively.

Usage from the pipeline::

    trace = RunTrace()
    run_trace.set_current(trace)          # done by SenseMaker
    ...
    run_trace.current().llm_call(...)     # done by local_model

Usage from a consumer::

    for event in trace.events():
        ...
    trace.summary()      # counts, tokens, elapsed
    trace.to_json()
"""

import contextvars
import json
import threading
import time

# Event kinds. Kept as plain strings so the JSON is readable without this module.
STAGE = "stage"                  # the pipeline moved to a new stage
LLM_CALL = "llm_call"            # one request to the language model
CODE_PROPOSED = "code_proposed"  # the coding assistant wrote code
CODE_OUTPUT = "code_output"      # the executor ran it and produced output
DB_QUERY = "db_query"            # a data function was called
ERROR = "error"                  # a step failed
ANSWER = "answer"                # the final answer was produced

_MAX_EVENTS = 5000  # a runaway loop must not exhaust memory

# Prompts grow as memory accumulates, and a long run can hold tens of them, so
# the recorded text is clipped. Head and tail are kept rather than just the
# head: the head carries the agent's instructions and the tail carries the
# actual question and the memory it was given, and both are what a reader is
# trying to see.
_MAX_TEXT = 12000


def _clip(text, limit=_MAX_TEXT):
    """Shorten `text` for storage, keeping both ends and saying what was cut."""
    if text is None:
        return None
    text = str(text)
    if len(text) <= limit:
        return text
    head, tail = limit * 2 // 3, limit // 3
    removed = len(text) - head - tail
    return (f"{text[:head]}\n\n"
            f"[... {removed:,} characters omitted from the middle ...]\n\n"
            f"{text[-tail:]}")


class RunTrace:
    """Thread-safe, append-only log of what happened during a run."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events = []
        self._seq = 0
        self.started_at = time.time()
        self._stage = None

    # --- recording ---------------------------------------------------------

    def add(self, kind, **payload):
        """Record one event. Never raises."""
        try:
            with self._lock:
                if len(self._events) >= _MAX_EVENTS:
                    return
                self._seq += 1
                self._events.append({
                    "seq": self._seq,
                    "ts": time.time(),
                    "elapsed": round(time.time() - self.started_at, 3),
                    "stage": self._stage,
                    "kind": kind,
                    **payload,
                })
        except Exception:  # pragma: no cover - instrumentation must not break a run
            pass

    def enter_stage(self, name):
        """Note that the pipeline moved to a new stage.

        Called from SenseMaker.current_step's setter, so every existing
        assignment records a transition without restructuring the pipeline.
        """
        if name == self._stage:
            return
        previous, self._stage = self._stage, name
        self.add(STAGE, name=name, previous=previous)

    def llm_call(self, *, model, seconds, prompt_tokens=None, completion_tokens=None,
                 worker=None, attempt=1, chars=None, messages=None, response=None,
                 thinking=None):
        """Record one model request.

        ``messages`` is the prompt in Ollama's own format; it is stored as the
        list of turns so a reader can tell the system instructions apart from
        the question. ``response`` is what came back, and ``thinking`` the
        reasoning trace when the model emits one.
        """
        # Flattened defensively rather than inline in the add() call: add()
        # swallows its own failures, but an argument expression is evaluated
        # before add() is entered, so a prompt in an unexpected shape would
        # raise straight into the pipeline. Instrumentation must not do that.
        try:
            turns = [
                {"role": str(m.get("role") or "user"),
                 "content": _clip(m.get("content") or "")}
                for m in (messages or [])
            ]
        except Exception:  # pragma: no cover - shape we do not produce ourselves
            turns = []

        self.add(LLM_CALL, model=model, seconds=round(seconds, 3),
                 prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                 worker=worker, attempt=attempt, chars=chars,
                 messages=turns,
                 response=_clip(response),
                 thinking=_clip(thinking) or None)

    def code_proposed(self, *, source, code, round_index=None):
        self.add(CODE_PROPOSED, source=source, code=code, round_index=round_index)

    def code_output(self, *, source, output, round_index=None):
        self.add(CODE_OUTPUT, source=source, output=output, round_index=round_index)

    def db_query(self, *, databases, request):
        self.add(DB_QUERY, databases=databases, request=request)

    def error(self, *, where, message):
        self.add(ERROR, where=where, message=str(message)[:2000])

    def answer(self, *, text):
        self.add(ANSWER, text=text)

    # --- reading -----------------------------------------------------------

    def events(self, kind=None, since_seq=0):
        """Snapshot of recorded events, optionally filtered.

        Returns copies, so a consumer iterating while the run continues cannot
        see a half-written event or trip over concurrent mutation.
        """
        with self._lock:
            events = list(self._events)
        if kind is not None:
            kinds = {kind} if isinstance(kind, str) else set(kind)
            events = [e for e in events if e["kind"] in kinds]
        if since_seq:
            events = [e for e in events if e["seq"] > since_seq]
        return events

    @property
    def stage(self):
        return self._stage

    def summary(self):
        """Aggregates worth putting on a dashboard."""
        events = self.events()
        calls = [e for e in events if e["kind"] == LLM_CALL]
        return {
            "elapsed": round(time.time() - self.started_at, 1),
            "stages": sum(1 for e in events if e["kind"] == STAGE),
            "llm_calls": len(calls),
            "llm_seconds": round(sum(e.get("seconds") or 0 for e in calls), 1),
            "prompt_tokens": sum(e.get("prompt_tokens") or 0 for e in calls),
            "completion_tokens": sum(e.get("completion_tokens") or 0 for e in calls),
            "code_rounds": sum(1 for e in events if e["kind"] == CODE_PROPOSED),
            "db_queries": sum(1 for e in events if e["kind"] == DB_QUERY),
            "errors": sum(1 for e in events if e["kind"] == ERROR),
        }

    def to_json(self, indent=2):
        return json.dumps(
            {"started_at": self.started_at,
             "summary": self.summary(),
             "events": self.events()},
            indent=indent, default=str,
        )


class NullTrace:
    """Does nothing, with the same surface as RunTrace.

    Returned by current() when nothing is recording, so callers never need to
    check for None.
    """

    def add(self, *a, **k): pass
    def enter_stage(self, *a, **k): pass
    def llm_call(self, *a, **k): pass
    def code_proposed(self, *a, **k): pass
    def code_output(self, *a, **k): pass
    def db_query(self, *a, **k): pass
    def error(self, *a, **k): pass
    def answer(self, *a, **k): pass
    def events(self, *a, **k): return []
    def summary(self): return {}
    def to_json(self, indent=2): return "{}"

    @property
    def stage(self): return None


_NULL = NullTrace()

# A ContextVar rather than a plain global: the coding agent runs its own
# asyncio loop inside the worker thread, and context vars propagate into
# asyncio tasks, so the active trace is still visible down there.
_active = contextvars.ContextVar("gloss_run_trace", default=_NULL)


def set_current(trace):
    """Make `trace` the one that pipeline hooks record into."""
    _active.set(trace if trace is not None else _NULL)


def current():
    """The active trace, or a no-op if nothing is recording."""
    try:
        return _active.get()
    except Exception:  # pragma: no cover
        return _NULL


def clear():
    _active.set(_NULL)
