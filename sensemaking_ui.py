"""
GLOSS dashboard.

Shows a sensemaking run as it happens: which agent is working, what it decided,
the code it generated, what running that code produced, and how memory and
understanding build up.

Everything on screen comes from two sources:

- ``SenseMaker`` attributes for the current text (action plan, memory,
  understanding, answer);
- ``SenseMaker.trace`` for the event history -- stage transitions, model calls
  with their latency and token counts, the coding agent's conversation, and
  errors. See agents/run_trace.py.

The run happens on a worker thread, which must never call ``st.*``; the trace is
the only channel between it and this script.

Targets the Streamlit pinned in environment_linux.yml (1.39), so no widgets
newer than that are used.
"""

import json
import threading
import time

import altair as alt
import pandas as pd
import streamlit as st

import sensemaking_process
from agents.config import LOCAL_MODEL_NAME, USE_LOCAL_MODEL
from agents.database_registry import get_all_databases

st.set_page_config(page_title="GLOSS", page_icon="🔍", layout="wide")

EXAMPLE_QUERIES = [
    "on nov 2 2020, for user1 what was the most used app by duration?",
    "on nov 2 2020, for user1 how many text messages were sent and received?",
    "on nov 2 2020, for user1 how many hours were spent at home?",
    "on nov 2 2020, for user1 how many calls were missed?",
]

DEFAULT_INSTRUCTIONS = "clear and concise"

for key, value in {
    "sense_maker": None,
    "worker": None,
    "query": EXAMPLE_QUERIES[0],
    "instructions": DEFAULT_INSTRUCTIONS,
    "run_active": False,
    "graph_step": 0,
}.items():
    st.session_state.setdefault(key, value)


# --------------------------------------------------------------------------
# Run control
# --------------------------------------------------------------------------

def is_running():
    worker = st.session_state.worker
    return worker is not None and worker.is_alive()


def has_finished():
    maker = st.session_state.sense_maker
    return maker is not None and not is_running()


def start_run(query, instructions):
    maker = sensemaking_process.SenseMaker(query, instructions or DEFAULT_INSTRUCTIONS)
    st.session_state.sense_maker = maker

    def work():
        # A crash here would otherwise leave the dashboard waiting forever, so
        # record it on the trace and mark the run finished.
        try:
            maker.make_sense(verbose=True)
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            maker.trace.error(where="run", message=exc)
            maker.answer = f"The run failed: {exc}"
            maker.current_step = "FINISH"
        finally:
            # In a finally so the clock stops on a crash and on a cancellation,
            # not just on a clean finish.
            maker.trace.finish()

    # Watched by live_area so it can hand the controls back the moment the
    # thread exits, without the participant having to press Stop first.
    st.session_state.run_active = True
    worker = threading.Thread(target=work, daemon=True)
    st.session_state.worker = worker
    worker.start()


def stop_run():
    maker = st.session_state.sense_maker
    if maker is not None:
        maker.cancel.set()


# --------------------------------------------------------------------------
# Tutorial affordances: short explanations, and errors turned into advice
# --------------------------------------------------------------------------

TAB_NOTES = {
    "overview": (
        "GLOSS answers a question by passing it between several agents. This tab "
        "summarises the whole run: how long each stage took, the plan it chose, "
        "the understanding it built up, and the final answer. The metrics are "
        "worth a look -- most of the elapsed time is usually spent waiting on the "
        "language model, not computing over your data."
    ),
    "activity": (
        "One entry per model call, in order, naming the agent that made it -- the "
        "next-step agent, the information-seeking agent, the coding agent, and "
        "so on -- with the exact prompt that was sent and the exact reply that "
        "came back. Open 'Exact prompt sent' to read what an agent was actually "
        "asked. Memory and understanding appear here too, at the moment they "
        "change, so you can see what each step actually added. Each entry also "
        "shows how long the model took, how many tokens "
        "went in and out, and which GPU worker served it. Prompts grow as "
        "memory accumulates, so later calls in a run are usually slower than "
        "earlier ones. Very long prompts are clipped in the middle; both ends "
        "are kept."
    ),
    "graph": (
        "The same information as Agent activity, arranged as the pipeline "
        "itself: every agent in GLOSS and how control passes between them. "
        "Boxes are coloured by whether this run used them -- the next-step "
        "agent decides which are needed, so a short run leaves several grey. "
        "Click any box, including Query and Answer, to read exactly what that "
        "agent was sent and what it replied."
    ),
    "code": (
        "GLOSS does not query your data directly. It writes Python, runs it in a "
        "container, reads what the code printed, and uses that as evidence. This "
        "tab shows that loop: the request, the code, and the output. If the code "
        "fails, the agent sees the error and tries again -- you will see several "
        "rounds when that happens."
    ),
}


def explain(key):
    """A short, collapsed note about what the tab is showing."""
    note = TAB_NOTES.get(key)
    if note:
        with st.expander("What am I looking at?"):
            st.markdown(note)


def diagnose(message):
    """Turn a model-gateway failure into something a participant can act on.

    The raw errors are accurate but unhelpful to someone seeing them for the
    first time, and the difference between them matters: one needs the
    organiser, one needs patience, one needs a different model.
    """
    text = str(message)
    lowered = text.lower()

    if "401" in text or "unauthorized" in lowered:
        return ("The model rejected our credentials.",
                "The access key is missing or wrong. This one is for the "
                "organiser to fix -- it is not something you did.")
    if "not permitted on this gateway" in lowered or "allowed_models" in lowered:
        return ("That model is not available on this cluster.",
                "The gateway only serves certain models. The error above lists "
                "the permitted ones; tell the organiser which you need.")
    if "403" in text:
        return ("The cluster refused the connection.",
                "It only accepts requests from recognised networks, which "
                "usually means the server's access has lapsed. Tell the "
                "organiser; retrying will not help.")
    if any(code in text for code in ("429", "500", "502", "503", "504")) or "timed out" in lowered:
        return ("The shared model is busy or slow.",
                "Several people are likely querying it at once. Wait a moment "
                "and run again -- GLOSS already retries a few times on its own.")
    if "could not reach" in lowered or "connection" in lowered:
        return ("Could not reach the model.",
                "The network path to the cluster is down. Tell the organiser.")
    if "stopped by the user" in lowered:
        return ("You stopped this run.", "Press Run to start another.")
    return (None, None)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.subheader("Ask a question")

    st.session_state.query = st.text_area(
        "Question",
        value=st.session_state.query,
        height=110,
        disabled=is_running(),
        help="The user id in the sample data is always user1.",
    )
    st.session_state.instructions = st.text_input(
        "How should the answer be presented?",
        value=st.session_state.instructions,
        disabled=is_running(),
    )

    if is_running():
        st.button("Running…", disabled=True, use_container_width=True)
        st.button("Stop", on_click=stop_run, use_container_width=True)
    else:
        st.button(
            "Run",
            type="primary",
            use_container_width=True,
            disabled=not st.session_state.query.strip(),
            on_click=lambda: start_run(st.session_state.query, st.session_state.instructions),
        )

    st.divider()
    st.caption("Examples — click to load one")
    for index, example in enumerate(EXAMPLE_QUERIES):
        st.button(
            example,
            key=f"example_{index}",
            disabled=is_running(),
            use_container_width=True,
            on_click=lambda e=example: st.session_state.update(query=e),
        )

    st.divider()

    # A quick check, so a gateway problem is found before a minute-long run
    # fails on it. Runs in the script thread deliberately: it is short, and the
    # result is wanted immediately.
    #
    # The short timeout is the point. chat() otherwise inherits
    # LOCAL_MODEL_TIMEOUT (600s) and retries four times, so a gateway that
    # accepts the connection and then hangs -- which is how an overloaded
    # worker actually fails -- would freeze this page for far longer than the
    # run it was meant to save.
    if st.button("Check model connection", use_container_width=True,
                 disabled=is_running()):
        from agents import local_model
        with st.spinner("Contacting the model…"):
            try:
                started = time.monotonic()
                reply, meta = local_model.chat(
                    [{"role": "user", "content": "Reply with the single word: ok"}],
                    num_predict=16,
                    timeout=20,
                )
                st.success(
                    f"Reachable in {time.monotonic() - started:.1f}s "
                    f"(worker {meta.get('worker') or 'unknown'})"
                )
            except Exception as exc:  # noqa: BLE001 - reported below
                headline, advice = diagnose(exc)
                st.error(headline or "Could not reach the model.")
                if advice:
                    st.caption(advice)
                with st.expander("Technical detail"):
                    st.caption(str(exc))

    databases = get_all_databases()
    st.caption(
        f"Model: {LOCAL_MODEL_NAME if USE_LOCAL_MODEL else 'OpenAI'}  ·  "
        f"{len(databases)} databases"
    )
    with st.expander("Available data"):
        for name, info in sorted((n, d.info) for n, d in databases.items()):
            st.markdown(f"**{name}**")
            st.caption(info)


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def stage_timeline(trace, current_step):
    """The stages the run has moved through, with how long each took."""
    stages = [e for e in trace.events(kind="stage") if e.get("name")]
    if not stages:
        st.caption("Waiting for the first stage…")
        return

    for index, event in enumerate(stages):
        name = event["name"]
        if index + 1 < len(stages):
            duration = stages[index + 1]["elapsed"] - event["elapsed"]
            label = f"{name} — {duration:.1f}s"
            icon = "✅"
        elif name in ("FINISH", "END"):
            label, icon = name, "✅"
        else:
            label, icon = f"{name} — running", "⏳"
        st.markdown(f"{icon}  {label}")


def render_overview(maker, trace):
    summary = trace.summary()
    columns = st.columns(4)
    columns[0].metric("Elapsed", f"{summary.get('elapsed', 0):.0f}s")
    columns[1].metric("Model calls", summary.get("llm_calls", 0))
    columns[2].metric(
        "Tokens",
        f"{summary.get('prompt_tokens', 0) + summary.get('completion_tokens', 0):,}",
    )
    columns[3].metric("Code runs", summary.get("code_rounds", 0))

    elapsed = summary.get("elapsed") or 0
    waiting = summary.get("llm_seconds") or 0
    if elapsed and waiting:
        st.caption(
            f"{waiting:.0f}s of the {elapsed:.0f}s was spent waiting on the language "
            f"model ({waiting / elapsed * 100:.0f}%). The model is shared, so a run "
            "takes longer when others are querying it at the same time."
        )

    errors = trace.events(kind="error")
    if errors:
        latest = errors[-1].get("message", "")
        headline, advice = diagnose(latest)
        with st.container(border=True):
            st.error(headline or f"{len(errors)} problem(s) during this run")
            if advice:
                st.markdown(advice)
            with st.expander(f"Technical detail ({len(errors)} event(s))"):
                for event in errors:
                    st.caption(f"**{event.get('where')}** — {event.get('message')}")

    if maker.answer:
        st.subheader("Answer")
        with st.container(border=True):
            st.markdown(maker.answer)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Progress")
        stage_timeline(trace, maker.current_step)
    with right:
        st.subheader("Action plan")
        st.markdown(maker.action_plan or "_not generated yet_")

    if maker.understanding:
        st.subheader("Understanding so far")
        st.markdown(maker.understanding)

    # The tabs that used to hold these are gone; the text itself now appears in
    # the timeline as it is written, but a whole-run copy is still worth having.
    st.divider()
    downloads = st.columns(3)
    downloads[0].download_button(
        "Memory (txt)", maker.memory or "", file_name="gloss_memory.txt",
        disabled=not maker.memory, use_container_width=True)
    downloads[1].download_button(
        "Understanding (txt)", maker.understanding or "",
        file_name="gloss_understanding.txt",
        disabled=not maker.understanding, use_container_width=True)
    downloads[2].download_button(
        "Full trace (JSON)", trace.to_json(), file_name="gloss_trace.json",
        mime="application/json", use_container_width=True)


def stage_label(stage):
    """'INFORMATION SEEKING' -> 'information seeking', for secondary text."""
    return (stage or "").replace("_", " ").lower() or "unknown stage"


def render_exchange(event):
    """The exact prompt sent and the exact reply received, for one model call.

    Everything is shown with st.code rather than st.markdown: prompts and
    replies contain JSON, braces and generated Python, which markdown would
    reflow or swallow. The ask here is fidelity, so the text is reproduced
    verbatim -- and st.code gives a copy button, which is what someone
    comparing a prompt against a reply actually wants.

    wrap_lines is on because these are mostly prose: a model writes a paragraph
    as one long line, and without wrapping reading it means scrolling sideways
    through every paragraph. Wrapping is a display choice only -- the text, and
    what the copy button yields, are unchanged.
    """
    messages = event.get("messages") or []
    reply = event.get("response")
    thinking = event.get("thinking")

    if not messages and reply is None:
        # Traces recorded before prompt capture existed, or a non-local model,
        # which does not route through local_model.chat().
        st.caption("_Prompt and reply were not recorded for this call._")
        return

    if messages:
        turns = ", ".join(
            f"{m.get('role')} {len(m.get('content') or ''):,} chars" for m in messages
        )
        with st.expander(f"Exact prompt sent — {len(messages)} turn(s): {turns}"):
            for message in messages:
                st.caption(f"**{(message.get('role') or 'user').upper()}**")
                st.code(message.get("content") or "", language=None, wrap_lines=True)

    if reply is not None:
        # A preview inline, because the point of this tab is to see what each
        # agent said without a click per call; the full text is one click away.
        preview = reply if len(reply) <= 400 else reply[:400] + " …"
        st.code(preview, language=None, wrap_lines=True)
        if len(reply) > 400:
            with st.expander(f"Exact reply in full — {len(reply):,} chars"):
                st.code(reply, language=None, wrap_lines=True)

    if thinking:
        with st.expander(f"The model's reasoning — {len(thinking):,} chars"):
            st.code(thinking, language=None, wrap_lines=True)


def render_activity(trace):
    """Chronological feed of what the agents did."""
    events = [
        e for e in trace.events()
        if e["kind"] in ("llm_call", "db_query", "error", "answer", "memory")
    ]
    if not events:
        st.caption("No agent activity yet.")
        return

    for event in events:
        kind = event["kind"]
        stage = event.get("stage") or "—"

        if kind == "llm_call":
            with st.chat_message("assistant"):
                tokens = f"{event.get('prompt_tokens') or 0} in / {event.get('completion_tokens') or 0} out"
                # The agent's name, not the stage: several agents run inside
                # one stage, and a stage name does not tell a participant who
                # is speaking. The stage stays as secondary context below.
                st.markdown(f"**{event.get('agent') or 'A model call'}**")
                st.caption(
                    f"during {stage_label(stage)} · {event['seconds']:.1f}s · "
                    f"{tokens} tokens · worker {event.get('worker') or 'unknown'}"
                    + (f" · attempt {event['attempt']}" if event.get("attempt", 1) > 1 else "")
                )
                render_exchange(event)
        elif kind == "db_query":
            with st.chat_message("user"):
                st.markdown(
                    f"**Database manager** queried "
                    f"{', '.join(event.get('databases') or []) or 'the data'}"
                )
                st.caption(
                    (event.get("request") or "")
                    + f"  ·  during {stage_label(stage)}"
                )
        elif kind == "memory":
            # Where the run's understanding actually changes, in line with the
            # calls that caused it -- the point of a timeline.
            field = event.get("field") or "memory"
            with st.chat_message("assistant"):
                if field == "understanding":
                    st.markdown("**Understanding** rewritten")
                    st.caption(
                        f"now {event.get('total_chars', 0):,} characters · "
                        f"during {stage_label(stage)}"
                    )
                else:
                    st.markdown("**Memory** grew")
                    st.caption(
                        f"+{len(event.get('added') or ''):,} characters, now "
                        f"{event.get('total_chars', 0):,} · during {stage_label(stage)}"
                    )
                st.code(event.get("added") or "", language=None, wrap_lines=True)
        elif kind == "answer":
            with st.chat_message("assistant"):
                st.markdown("**Presentation agent** produced the final answer")
        else:
            with st.chat_message("assistant"):
                st.error(f"{event.get('where')}: {event.get('message')}")


def render_code(trace):
    """The coding agent's conversation: request, code, and what it printed."""
    events = [
        e for e in trace.events()
        if e["kind"] in ("code_task", "code_proposed", "code_output")
    ]
    if not events:
        st.caption(
            "No code generated yet. GLOSS writes Python to answer the question, "
            "runs it in a container, and reads the output."
        )
        return

    for event in events:
        kind = event["kind"]
        if kind == "code_task":
            st.markdown("**The coding agent was asked to:**")
            st.info(event.get("request") or "")
        elif kind == "code_proposed":
            if event.get("has_code"):
                st.markdown(f"**Generated code** (round {event.get('round_index')})")
                st.code(event.get("code_block") or "", language="python", wrap_lines=True)
                with st.expander("The agent's full message"):
                    st.markdown(event.get("code") or "")
            else:
                st.markdown(f"**The agent said** (round {event.get('round_index')})")
                st.markdown(event.get("code") or "")
        else:
            st.markdown("**Output from running it**")
            st.code(event.get("output") or "", language="text", wrap_lines=True)
        st.divider()


# --------------------------------------------------------------------------
# Agent graph
# --------------------------------------------------------------------------

# Laid out and coloured to match the diagram in the GLOSS4HAR write-up, so the
# dashboard and the paper show one picture. Coordinates and palette are that
# diagram's own; its day palette is used for both Streamlit themes because
# every box carries its own fill, so the boxes stay legible whatever the page
# behind them is doing. Only the arrows are a neutral grey for that reason.
PANEL, INK, LINE = "#FBFCFA", "#1B2428", "#DBE0D8"
DBLUE, LBLUE, LBLUE_B = "#3E4E96", "#E7ECFA", "#6E86D8"
ACCENT, ARROW = "#12786F", "#8C9BAB"

# "agents" is how a node claims calls from the trace. Local and global
# sensemaking are one agent module, told apart only by the stage they run in,
# which is why a node can match on stage too.
GRAPH_NODES = [
    {"id": "query", "label": "Query", "x": 26, "y": 56, "w": 124, "h": 100,
     "kind": "io", "symbol": "?"},
    {"id": "plan", "label": "Action Plan\nGeneration Agent", "x": 195, "y": 66,
     "w": 190, "h": 68, "style": "white", "agents": ("Action-plan agent",)},
    {"id": "next", "label": "Next Step\nAgent", "x": 520, "y": 66,
     "w": 170, "h": 68, "style": "white", "agents": ("Next-step agent",)},
    {"id": "seek", "label": "Information\nSeeking Agent", "x": 912, "y": 69,
     "w": 184, "h": 62, "style": "blue", "agents": ("Information-seeking agent",)},
    {"id": "dbm", "label": "Database / Model\nManager Agent", "x": 878, "y": 196,
     "w": 178, "h": 70, "style": "blue", "agents": ("Database manager", "Summarizer")},
    {"id": "code", "label": "Code\nGeneration", "x": 1072, "y": 196,
     "w": 116, "h": 70, "style": "blue", "agents": ("Coding agent",)},
    {"id": "global", "label": "Global\nSensemaking Agent", "x": 500, "y": 246,
     "w": 188, "h": 62, "style": "lblue", "agents": ("Sensemaking agent",),
     "stages": ("GLOBAL SENSEMAKING",)},
    {"id": "local", "label": "Local\nSensemaking Agent", "x": 636, "y": 352,
     "w": 188, "h": 70, "style": "lblue", "agents": ("Sensemaking agent",),
     "stages": ("LOCAL SENSEMAKING",)},
    {"id": "present", "label": "Presentation\nAgent", "x": 195, "y": 356,
     "w": 186, "h": 70, "style": "white", "agents": ("Presentation agent",)},
    {"id": "answer", "label": "Answer", "x": 26, "y": 350, "w": 124, "h": 100,
     "kind": "io", "symbol": "✓"},
    # The write-up's sensor-streams panel. Here it lists the databases actually
    # registered on this instance, since that is what the agents can reach.
    {"id": "databases", "label": "Databases", "x": 870, "y": 452,
     "w": 324, "h": 150, "kind": "panel"},
]

GRAPH_EDGES = [
    [(150, 106), (191, 106)],
    [(385, 100), (516, 100)],
    [(690, 100), (908, 100)],
    [(1004, 131), (1004, 196)],
    [(1056, 231), (1072, 231)],
    [(940, 266), (940, 387), (828, 387)],
    [(636, 387), (594, 387), (594, 310)],
    [(600, 246), (600, 136)],
    [(524, 134), (440, 134), (440, 344), (288, 344), (288, 354)],
    [(195, 391), (154, 391)],
]

# The two dashed links from the data side down to the databases.
GRAPH_DASHED = [
    [(970, 266), (970, 452)],
    [(1120, 266), (1120, 452)],
]

NODE_FILL = {"white": PANEL, "blue": DBLUE, "lblue": LBLUE,
             "io": "#00000000", "panel": PANEL}
NODE_STROKE = {"white": LINE, "blue": DBLUE, "lblue": LBLUE_B,
               "io": "#00000000", "panel": LINE}
NODE_TEXT = {"white": INK, "blue": "#FFFFFF", "lblue": INK,
             "io": INK, "panel": INK}


def node_style(node):
    return node.get("style") or node.get("kind") or "white"


def graph_calls(trace, node):
    """The model calls belonging to one node of the graph."""
    if not node.get("agents"):
        return []
    stages = node.get("stages")
    return [
        event for event in trace.events(kind="llm_call")
        if event.get("agent") in node["agents"]
        and (not stages or (event.get("stage") or "") in stages)
    ]


def node_for_event(event):
    """Which box a model call belongs to, or None if the diagram has no box."""
    for node in GRAPH_NODES:
        if not node.get("agents"):
            continue
        if event.get("agent") in node["agents"]:
            stages = node.get("stages")
            if not stages or (event.get("stage") or "") in stages:
                return node
    return None


def graph_steps(maker, trace):
    """The run as an ordered walk: the query, each model call, then the answer.

    One step per call rather than per agent, because an agent is visited more
    than once -- the next-step agent runs every iteration -- and the point of
    stepping is to follow the order things actually happened in.
    """
    steps = [{"node": "query", "title": "Query", "event": None}]
    for event in trace.events(kind="llm_call"):
        node = node_for_event(event)
        steps.append({
            "node": node["id"] if node else None,
            "title": event.get("agent") or "A model call",
            "event": event,
        })
    if maker.answer:
        steps.append({"node": "answer", "title": "Answer", "event": None})
    return steps


# An icon per data stream, as the write-up's sensor panel has. Matched on a
# keyword rather than the full name so a renamed or newly registered database
# still gets one, falling back to a generic card index.
DATABASE_ICONS = (
    ("app", "📱"), ("call", "📞"), ("lock", "🔓"), ("unlock", "🔓"),
    ("sms", "💬"), ("text", "💬"), ("sens", "📡"), ("location", "📍"),
    ("step", "👣"), ("heart", "❤️"), ("audio", "🔊"), ("sound", "🔊"),
    ("sleep", "🌙"), ("model", "🧠"),
)


def database_icon(name):
    for keyword, icon in DATABASE_ICONS:
        if keyword in name.lower():
            return icon
    return "🗃️"


def database_names():
    """The databases registered on this instance, labelled for the panel.

    "app usage database" reads as "app usage" here: the panel is already
    titled Databases, and the short form is what the write-up's sensor panel
    uses.
    """
    try:
        names = sorted(get_all_databases().keys())
    except Exception:  # noqa: BLE001 - the panel is decoration, never fatal
        return []
    labels = []
    for name in names:
        short = name.lower().replace(" database", "").strip() or name
        labels.append(f"{database_icon(name)}  {short}")
    return labels


def agent_graph_chart(trace, active_node):
    """The pipeline, with the agent of the current step lit and the rest dimmed.

    Display-only, and deliberately so: Streamlit 1.39 raises on any chart that
    both composes layers and takes selections, and a diagram needs layers. The
    stepper above it does the driving instead.
    """
    rows, labels = [], []
    for node in GRAPH_NODES:
        style = node_style(node)
        lit = active_node is None or node["id"] == active_node
        calls = len(graph_calls(trace, node))

        if node.get("kind") == "io":
            # A bubble with the symbol in it, and the word underneath.
            size = 46
            cx = node["x"] + node["w"] / 2
            rows.append({"x1": cx - size / 2, "x2": cx + size / 2,
                         "y1": node["y"] + 6, "y2": node["y"] + 6 + size,
                         "fill": PANEL, "stroke": INK, "opacity": 1.0 if lit else 0.28,
                         "width": 2.0, "id": node["id"], "label": node["label"],
                         "detail": "the question" if node["id"] == "query" else "the answer"})
            labels.append({"x": cx, "y": node["y"] + 6 + size / 2, "text": node["symbol"],
                           "color": INK, "size": 22, "opacity": 1.0 if lit else 0.28})
            labels.append({"x": cx, "y": node["y"] + 6 + size + 18, "text": node["label"],
                           "color": INK, "size": 13, "opacity": 1.0 if lit else 0.28})
            continue

        text = node["label"]
        if node.get("kind") == "panel":
            names = database_names()
            text = node["label"] + "\n" + ("\n".join(names) if names else "none registered")

        rows.append({"x1": node["x"], "x2": node["x"] + node["w"],
                     "y1": node["y"], "y2": node["y"] + node["h"],
                     "fill": NODE_FILL[style], "stroke": ACCENT if (lit and active_node) else NODE_STROKE[style],
                     "opacity": 1.0 if lit else 0.28,
                     "width": 3.0 if (lit and active_node) else 1.0,
                     "id": node["id"], "label": node["label"].replace("\n", " "),
                     "detail": f"{calls} call(s) in this run" if calls else "not used in this run"})
        labels.append({"x": node["x"] + node["w"] / 2,
                       "y": node["y"] + node["h"] / 2,
                       "text": text, "color": NODE_TEXT[style],
                       "size": 11 if node.get("kind") == "panel" else 13,
                       "opacity": 1.0 if lit else 0.28})

    node_frame = pd.DataFrame(rows)
    label_frame = pd.DataFrame(labels)

    x_scale = alt.Scale(domain=[0, 1220], nice=False)
    y_scale = alt.Scale(domain=[30, 620], nice=False, reverse=True)
    blank = alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None)

    def edge_layer(edges, dash):
        points = []
        for index, line in enumerate(edges):
            for order, (x, y) in enumerate(line):
                points.append({"edge": f"{dash}{index}", "order": order, "x": x, "y": y})
        return alt.Chart(pd.DataFrame(points)).mark_line(
            color=ARROW, strokeWidth=1.6,
            strokeDash=[5, 4] if dash else [1, 0],
        ).encode(
            x=alt.X("x:Q", scale=x_scale, axis=blank),
            y=alt.Y("y:Q", scale=y_scale, axis=blank),
            order="order:Q", detail="edge:N",
        )

    boxes = alt.Chart(node_frame).mark_rect(cornerRadius=7).encode(
        x=alt.X("x1:Q", scale=x_scale, axis=blank), x2="x2:Q",
        y=alt.Y("y1:Q", scale=y_scale, axis=blank), y2="y2:Q",
        fill=alt.Fill("fill:N", scale=None),
        stroke=alt.Stroke("stroke:N", scale=None),
        strokeWidth=alt.StrokeWidth("width:Q", scale=None),
        opacity=alt.Opacity("opacity:Q", scale=None),
        tooltip=[alt.Tooltip("label:N", title="Step"),
                 alt.Tooltip("detail:N", title="This run")],
    )

    text = alt.Chart(label_frame).mark_text(
        lineBreak="\n", fontWeight=600, align="center", baseline="middle",
    ).encode(
        x=alt.X("x:Q", scale=x_scale, axis=blank),
        y=alt.Y("y:Q", scale=y_scale, axis=blank),
        text="text:N",
        color=alt.Color("color:N", scale=None),
        size=alt.Size("size:Q", scale=None),
        opacity=alt.Opacity("opacity:Q", scale=None),
    )

    return alt.layer(
        edge_layer(GRAPH_EDGES, False), edge_layer(GRAPH_DASHED, True), boxes, text
    ).properties(height=440).configure_view(stroke=None)


def step_back():
    st.session_state.graph_step = max(0, st.session_state.get("graph_step", 0) - 1)


def step_forward(last):
    st.session_state.graph_step = min(last, st.session_state.get("graph_step", 0) + 1)


def render_graph(maker, trace):
    """Walk the run one step at a time, lighting the agent that was working."""
    steps = graph_steps(maker, trace)
    last = len(steps) - 1
    index = min(st.session_state.get("graph_step", 0), last)
    step = steps[index]

    back, position, forward = st.columns([1, 3, 1])
    back.button("◀ Previous", use_container_width=True, disabled=index == 0,
                on_click=step_back, key="graph_prev")
    position.markdown(
        f"<div style='text-align:center;padding-top:6px'><b>Step {index + 1} of "
        f"{len(steps)}</b> — {step['title']}</div>",
        unsafe_allow_html=True,
    )
    forward.button("Next ▶", use_container_width=True, disabled=index == last,
                   on_click=step_forward, args=(last,), key="graph_next")

    st.altair_chart(agent_graph_chart(trace, step["node"]), use_container_width=True)

    event = step["event"]
    if step["node"] == "query":
        st.subheader("The question")
        st.code(maker.user_query or "", language=None, wrap_lines=True)
        return
    if step["node"] == "answer":
        st.subheader("The answer")
        st.code(maker.answer, language=None, wrap_lines=True)
        return

    st.subheader(step["title"])
    st.caption(
        f"during {stage_label(event.get('stage'))} · {event['seconds']:.1f}s · "
        f"{event.get('prompt_tokens') or 0} in / {event.get('completion_tokens') or 0} out tokens"
        f" · worker {event.get('worker') or 'unknown'}"
    )
    if step["node"] is None:
        st.caption("This agent has no box in the diagram.")
    render_exchange(event)


# --------------------------------------------------------------------------
# Main area
# --------------------------------------------------------------------------

st.title("GLOSS 🔍")
st.caption("Group of LLMs for Open-ended Sensemaking of passive sensing data")

# Only poll while a run is in flight; otherwise render once. A fragment keeps
# the rest of the page interactive, unlike the blocking loop this replaces.
@st.fragment(run_every=1.0 if is_running() else None)
def live_area():
    maker = st.session_state.sense_maker

    if maker is None:
        st.info("Enter a question in the sidebar, or pick an example, then press Run.")
        with st.expander("What happens when you run one?"):
            st.markdown(
                "- **Action plan** — an agent decides how to approach the question\n"
                "- **Information seeking** — it chooses which databases to ask\n"
                "- **Code generation** — it writes Python, runs it in a container, "
                "and reads the output\n"
                "- **Local / global sensemaking** — results become memory, then a "
                "running understanding\n"
                "- **Presentation** — the understanding is turned into an answer\n\n"
                "Once a run starts, each of those steps gets its own tab. Code "
                "generation prints nothing while it runs; a few minutes of "
                "quiet is normal."
            )
        return

    trace = maker.trace

    if st.session_state.run_active and not is_running():
        # The worker thread has just exited. This function is a fragment, and a
        # fragment rerun does not re-execute the main script body -- which is
        # where the sidebar's Run button lives -- so the controls would stay
        # stuck on "Running…" until something forced a full rerun. Pressing
        # Stop used to be the only thing that did. Do it automatically instead,
        # once, which also re-evaluates run_every and ends the polling.
        st.session_state.run_active = False
        st.rerun(scope="app")

    if is_running():
        st.info(f"Running — {maker.current_step or 'starting'}", icon="⏳")
    elif trace.events(kind="error"):
        st.warning("Finished with problems — see Overview.", icon="⚠️")
    else:
        st.success("Finished", icon="✅")

    overview, graph, activity, code = st.tabs(
        ["Overview", "Agent graph", "Agent activity", "Generated code"]
    )
    with overview:
        explain("overview")
        render_overview(maker, trace)
    with graph:
        explain("graph")
        render_graph(maker, trace)
    with activity:
        explain("activity")
        render_activity(trace)
    with code:
        explain("code")
        render_code(trace)


live_area()
