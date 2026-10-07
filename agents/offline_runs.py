"""
Recorded runs, replayed without touching the language model.

A tutorial's example queries should not depend on a gateway being up and
responsive in front of a room. These are real runs, captured once with
``deploy/record_offline_runs.py`` and played back from disk: same stages, same
generated code, same answer, same shape on the dashboard.

Replay is deliberately not instant. A run takes real time and prints nothing
during code generation, and an example that resolves in a blink teaches the
wrong thing about what the system is doing. The recorded timings are scaled to
``TARGET_SECONDS`` so the shape survives while the wait does not.

The replay object stands in for ``SenseMaker``: the dashboard only reads
``trace``, ``current_step``, ``answer``, ``understanding``, ``memory``,
``action_plan``, ``user_query`` and ``cancel``, and calls ``make_sense``. Every
tab, the timeline and the agent graph therefore work on a replay unchanged.

Matching a question to a recording
----------------------------------
Keyed on the question, the presentation instructions, and a fingerprint of what
was registered at the time. The fingerprint matters because the tutorial's demo
queries have two right answers: before the sensing behaviour database is
registered, asking about sleep fails; afterwards it returns three hours. Both
are recorded, and the one matching the instance's current state is played.

An exact fingerprint match wins. Failing that, any recording of the same
question is used -- most questions do not depend on what is registered, and
those should keep working after the tutorial's demos change the state.
"""

import hashlib
import json
import os
import threading
import time

from agents import run_trace

# Where recordings live, resolved from this file so the working directory does
# not matter.
RECORDINGS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "offline_runs")
)

# How long a replayed run should take, in seconds. Long enough to read the
# stages as they arrive and narrate over them; short enough to show several.
TARGET_SECONDS = 25.0

# No two events closer together than this, so a burst of quick events still
# reads as separate things happening rather than one flash. Best effort: with
# enough events the floor would overrun TARGET_SECONDS, and the target wins.
MIN_GAP_SECONDS = 0.35


# --------------------------------------------------------------------------
# What was registered when the run was recorded
# --------------------------------------------------------------------------

def state_fingerprint():
    """Short hash of the registered databases and their function names.

    Changes when a database or a helper function is registered, which is
    exactly what the tutorial's two demos do.
    """
    try:
        from agents.database_registry import get_all_databases
        parts = []
        for name, info in sorted(get_all_databases().items()):
            functions = sorted(
                (f.get("name", "") for f in (info.functions or {}).values())
            )
            parts.append(name + "|" + ",".join(functions))
        blob = ";".join(parts)
    except Exception:  # noqa: BLE001 - never block a run over a fingerprint
        blob = "unknown"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def recording_id(query, instructions, fingerprint):
    """Stable filename for one recording."""
    blob = f"{query.strip()}\x00{(instructions or '').strip()}\x00{fingerprint}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Reading and writing recordings
# --------------------------------------------------------------------------

def load_recordings():
    """Every recording on disk, newest first. Never raises."""
    recordings = []
    if not os.path.isdir(RECORDINGS_DIR):
        return recordings
    for filename in sorted(os.listdir(RECORDINGS_DIR)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(RECORDINGS_DIR, filename)
        try:
            with open(path) as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            print(f"Skipping unreadable recording {filename}: {exc}")
            continue
        if data.get("query"):
            data["_path"] = path
            recordings.append(data)
    recordings.sort(key=lambda r: r.get("recorded_at") or 0, reverse=True)
    return recordings


def available_runs():
    """Every recording, in the picker's order.

    The demo questions appear twice, labelled "(commented)" and
    "(uncommented)", rather than one row chosen from what is registered right
    now. Choosing automatically was invisible and therefore hard to trust: it
    also had no answer for a half-registered instance, which is what you get
    between performing the first demo and the second. Showing both and letting
    the presenter pick needs no explanation and cannot be in the wrong state.
    """
    runs = load_recordings()
    runs.sort(key=lambda r: (r.get("order", 999), r.get("state_label", "")))
    return runs


def picker_label(recording):
    """How one recording reads in the dropdown."""
    label = recording.get("label") or recording["query"]
    state = recording.get("state_label") or ""
    return f"{label}  {state}".strip()


def save_recording(*, query, instructions, fingerprint, maker, label="", note="",
                   order=999, state_label=""):
    """Write one completed run to disk, returning its path.

    ``order`` fixes where this question sits in the dashboard's picker, so the
    list reads in the order the tutorial uses rather than by recording time.
    """
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    payload = {
        "query": query,
        "instructions": instructions or "",
        "label": label or query,
        "note": note,
        "order": order,
        # "(commented)" / "(uncommented)" for the demo questions, so the picker
        # says which side of the demo a recording is from. Blank for everything
        # else, which has only one recording and no state to be in.
        "state_label": state_label,
        "fingerprint": fingerprint,
        "recorded_at": time.time(),
        "final": {
            "answer": getattr(maker, "answer", "") or "",
            "understanding": getattr(maker, "understanding", "") or "",
            "memory": getattr(maker, "memory", "") or "",
            "action_plan": getattr(maker, "action_plan", "") or "",
        },
        "summary": maker.trace.summary(),
        "events": maker.trace.events(),
    }
    path = os.path.join(
        RECORDINGS_DIR, recording_id(query, instructions, fingerprint) + ".json"
    )
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2, default=str)
    return path


# --------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------

def _schedule(events, target_seconds=TARGET_SECONDS):
    """When to emit each event, in seconds from the start of the replay.

    The recorded gaps are kept in proportion rather than flattened, so a run
    that paused for two minutes in code generation still pauses longest there.
    A floor keeps near-simultaneous events from arriving as one blur.
    """
    if not events:
        return []
    elapsed = [float(e.get("elapsed") or 0) for e in events]
    span = max(elapsed) or 1.0
    scale = target_seconds / span

    times, previous = [], 0.0
    for value in elapsed:
        moment = max(value * scale, previous + MIN_GAP_SECONDS)
        times.append(moment)
        previous = moment

    # Enough events and the floor alone exceeds the target -- a 12-event run
    # held to 0.35s apart cannot finish in 3s. Squeeze back to the target
    # rather than overrunning it, since how long a replay takes is the part
    # that was actually chosen.
    total = times[-1]
    if total > target_seconds:
        squeeze = target_seconds / total
        times = [t * squeeze for t in times]
    return times


class ReplayRun:
    """A recorded run, played back with the surface of a live one."""

    def __init__(self, recording, target_seconds=TARGET_SECONDS):
        self.recording = recording
        self.target_seconds = target_seconds

        self.user_query = recording.get("query", "")
        self.presentation_instructions = recording.get("instructions", "")
        self.trace = run_trace.RunTrace()
        self.cancel = threading.Event()

        self.current_step = ""
        self.answer = ""
        self.understanding = ""
        self.memory = ""
        self.action_plan = ""
        self.offline = True
        self._seen_planning = False

    def make_sense(self, verbose=False):
        """Emit the recorded events on the original rhythm, compressed."""
        events = self.recording.get("events") or []
        schedule = _schedule(events, self.target_seconds)
        started = time.monotonic()

        for event, moment in zip(events, schedule):
            # Wait in slices so Stop is responsive rather than taking effect
            # only once the next event is due.
            while True:
                remaining = moment - (time.monotonic() - started)
                if remaining <= 0 or self.cancel.is_set():
                    break
                time.sleep(min(remaining, 0.1))
            if self.cancel.is_set():
                self.trace.error(where="run", message="stopped by the user")
                break
            self._emit(event)

        if not self.cancel.is_set():
            # The recorded fields are the authority: a clipped memory event
            # would otherwise leave the panels holding a truncated version.
            final = self.recording.get("final") or {}
            self.action_plan = final.get("action_plan", self.action_plan)
            self.memory = final.get("memory", self.memory)
            self.understanding = final.get("understanding", self.understanding)
            self.answer = final.get("answer", self.answer)
            self.current_step = "FINISH"

            # Same reason: the finished run should report how long it took,
            # not how long the playback took. Set before finish(), which only
            # fills finished_at when it is still unset.
            original = (self.recording.get("summary") or {}).get("elapsed")
            if original:
                self.trace.finished_at = self.trace.started_at + float(original)

        self.trace.finish()

    def _keep_recorded_elapsed(self, event):
        """Restore the original run's timing on the event just added.

        A replay has two clocks, and mixing them produced nonsense: stage
        durations and the total came from the compressed replay, while the
        per-call model latencies were the original run's. The overview read
        "48s of the 25s was spent waiting on the language model (192%)".

        The recorded timings are the real information -- how long the run
        actually took, and where it went -- so they win. Compression decides
        only when each event appears on screen.
        """
        recorded = event.get("elapsed")
        if recorded is None:
            return
        with self.trace._lock:  # noqa: SLF001 - replaying into a trace
            if self.trace._events:
                self.trace._events[-1]["elapsed"] = recorded
            # Wind the start back so the running total reads in recorded time
            # too. summary() computes elapsed as now - started_at, which while
            # a replay is in flight was the playback clock -- four seconds in,
            # against model latencies from a run that took seventy, giving
            # "11s of the 4s (245%)". Fixing only the final value left that
            # visible for the whole replay, and frozen there if it was stopped.
            self.trace.started_at = time.time() - recorded

    def _emit(self, event):
        """Put one recorded event on the live trace and update the fields."""
        payload = {k: v for k, v in event.items()
                   if k not in ("seq", "ts", "elapsed", "stage", "kind")}
        kind = event.get("kind")

        if kind == run_trace.STAGE:
            name = event.get("name") or ""

            # The pipeline never records the action plan on the trace -- the
            # dashboard reads it off the run object -- so replay has only the
            # recorded final value and no event telling it when to show it.
            # It is written once, during the planning stage, and never
            # changed, so revealing it as that stage ends is faithful. Without
            # this it stayed blank until the whole replay finished, with the
            # timeline claiming planning was long done.
            if self._seen_planning and not self.action_plan:
                self.action_plan = (self.recording.get("final") or {}).get(
                    "action_plan", ""
                )
            if "ACTION PLAN" in name.upper():
                self._seen_planning = True

            self.current_step = name
            self.trace.enter_stage(name)
            self._keep_recorded_elapsed(event)
            return

        # Keep the stage recorded against each event, so the timeline groups
        # them the way the original run did.
        self.trace._stage = event.get("stage")  # noqa: SLF001 - replaying a record
        self.trace.add(kind, **payload)
        self._keep_recorded_elapsed(event)

        if kind == run_trace.MEMORY:
            field, added = event.get("field"), event.get("added") or ""
            if field == "memory":
                self.memory = (self.memory + added) if not event.get("rewritten") else added
            elif field == "understanding":
                self.understanding = added
        elif kind == run_trace.ANSWER:
            self.answer = event.get("text") or ""
