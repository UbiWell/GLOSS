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
    "graph_node": "query",
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
        "asked. Each entry also shows how long the model took, how many tokens "
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
    "memory": (
        "Memory is the record of each question GLOSS asked of the data and what "
        "came back. Understanding is the running synthesis built from it, and is "
        "what the final answer is written from. Watching these grow is the "
        "clearest view of how the system reasons."
    ),
    "data": (
        "Which databases were consulted, and with what request. With code "
        "generation enabled, the data functions are usually called from inside "
        "the generated code rather than directly, so the lower table is often "
        "empty -- look at the Generated code tab instead."
    ),
    "trace": (
        "The raw event log for this run. Every stage change, model call, piece of "
        "generated code and error, in order. Download it to compare two runs, or "
        "to see exactly where the time went."
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
        if e["kind"] in ("llm_call", "db_query", "error", "answer")
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


def render_memory(maker):
    left, right = st.columns(2)
    with left:
        st.subheader("Memory")
        st.caption("What the run has established so far, one question at a time.")
        if maker.memory.strip():
            st.text_area("memory", maker.memory, height=420,
                         label_visibility="collapsed", disabled=True)
            st.download_button("Download memory", maker.memory,
                               file_name="gloss-memory.txt")
        else:
            st.caption("_empty_")
    with right:
        st.subheader("Understanding")
        st.caption("The running synthesis that becomes the final answer.")
        if maker.understanding.strip():
            st.text_area("understanding", maker.understanding, height=420,
                         label_visibility="collapsed", disabled=True)
            st.download_button("Download understanding", maker.understanding,
                               file_name="gloss-understanding.txt")
        else:
            st.caption("_empty_")


def render_data(maker, trace):
    st.subheader("Information requests")
    requests = trace.events(kind="db_query")
    if requests:
        st.dataframe(
            [{"databases": ", ".join(e.get("databases") or []),
              "request": e.get("request")} for e in requests],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("None yet.")

    st.subheader("Data functions called")
    calls = maker.function_calls
    if calls:
        rows = []
        for call in calls:
            if isinstance(call, dict):
                rows.append({"function": call.get("name"),
                             "params": json.dumps(call.get("params", {}), default=str)})
            else:
                rows.append({"function": str(call), "params": ""})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("None yet. With code generation on, GLOSS usually calls data "
                   "functions from inside the generated code instead.")


def render_trace(trace):
    events = trace.events()
    st.caption(
        f"{len(events)} events. This is the raw record of the run — useful for "
        "seeing exactly what happened, and for comparing two runs."
    )
    if events:
        st.dataframe(
            [{"seq": e["seq"], "at": f"{e['elapsed']:.1f}s",
              "stage": e.get("stage"), "kind": e["kind"]} for e in events],
            use_container_width=True, hide_index=True, height=420,
        )
        st.download_button("Download trace (JSON)", trace.to_json(),
                           file_name="gloss-trace.json", mime="application/json")


# --------------------------------------------------------------------------
# Agent graph
# --------------------------------------------------------------------------

# The same picture as the GLOSS4HAR write-up, so the dashboard and the paper
# agree. Coordinates are that diagram's own pixel space; the chart only scales
# them, so moving a box here keeps the two in step.
#
# "agents" is how a node claims events from the trace. The local and global
# sensemaking boxes are one agent module, told apart by the stage they run in,
# which is why a node can match on stage as well.
GRAPH_NODES = [
    {"id": "query", "label": "Query", "x": 26, "y": 56, "w": 124, "h": 100,
     "kind": "io"},
    {"id": "plan", "label": "Action Plan\nGeneration Agent", "x": 195, "y": 66,
     "w": 190, "h": 68, "kind": "agent", "agents": ("Action-plan agent",)},
    {"id": "next", "label": "Next Step\nAgent", "x": 520, "y": 66,
     "w": 170, "h": 68, "kind": "agent", "agents": ("Next-step agent",)},
    {"id": "seek", "label": "Information\nSeeking Agent", "x": 912, "y": 69,
     "w": 184, "h": 62, "kind": "agent", "agents": ("Information-seeking agent",)},
    {"id": "dbm", "label": "Database / Model\nManager Agent", "x": 878, "y": 196,
     "w": 178, "h": 70, "kind": "agent", "agents": ("Database manager", "Summarizer")},
    {"id": "code", "label": "Code\nGeneration", "x": 1072, "y": 196,
     "w": 116, "h": 70, "kind": "agent", "agents": ("Coding agent",)},
    {"id": "global", "label": "Global\nSensemaking Agent", "x": 500, "y": 246,
     "w": 188, "h": 62, "kind": "agent", "agents": ("Sensemaking agent",),
     "stages": ("GLOBAL SENSEMAKING",)},
    {"id": "local", "label": "Local\nSensemaking Agent", "x": 636, "y": 352,
     "w": 188, "h": 70, "kind": "agent", "agents": ("Sensemaking agent",),
     "stages": ("LOCAL SENSEMAKING",)},
    {"id": "present", "label": "Presentation\nAgent", "x": 195, "y": 356,
     "w": 186, "h": 70, "kind": "agent", "agents": ("Presentation agent",)},
    {"id": "answer", "label": "Answer", "x": 26, "y": 350, "w": 124, "h": 100,
     "kind": "io"},
]

# Elbow polylines, taken from the same diagram.
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


def graph_calls(trace, node):
    """The model calls belonging to one node of the graph."""
    if node["kind"] != "agent":
        return []
    stages = node.get("stages")
    return [
        event for event in trace.events(kind="llm_call")
        if event.get("agent") in node["agents"]
        and (not stages or (event.get("stage") or "") in stages)
    ]


def graph_frame(trace):
    """One row per node, carrying what this run did in it."""
    rows = []
    for node in GRAPH_NODES:
        calls = graph_calls(trace, node)
        seconds = sum(e.get("seconds") or 0 for e in calls)
        if node["kind"] == "io":
            status = "start/end"
        elif calls:
            status = "ran"
        else:
            status = "not used"
        rows.append({
            "id": node["id"],
            "label": node["label"],
            "x1": node["x"], "x2": node["x"] + node["w"],
            "y1": node["y"], "y2": node["y"] + node["h"],
            "cx": node["x"] + node["w"] / 2,
            "cy": node["y"] + node["h"] / 2,
            "calls": len(calls),
            "seconds": round(seconds, 1),
            "status": status,
            "detail": (f"{len(calls)} call(s) · {seconds:.0f}s" if calls
                       else ("click to see it" if node["kind"] == "io" else "not used in this run")),
        })
    return pd.DataFrame(rows)


def graph_edge_frame():
    rows = []
    for index, points in enumerate(GRAPH_EDGES):
        for order, (x, y) in enumerate(points):
            rows.append({"edge": index, "order": order, "x": x, "y": y})
    return pd.DataFrame(rows)


def agent_graph_chart(trace, selected):
    """The pipeline as a clickable diagram.

    The layout is fixed rather than solved by a layout engine, so the boxes
    stay where a reader last saw them instead of shuffling between runs.

    The diagram is display-only. Streamlit 1.39 raises on any chart that both
    composes layers and accepts selections, and a diagram needs layers: boxes,
    elbow lines and labels are three different mark types. So the boxes below
    do the selecting, named to match, with the chosen one outlined here.
    """
    nodes = graph_frame(trace)
    if selected:
        nodes["chosen"] = nodes["id"].eq(selected)
    else:
        nodes["chosen"] = False

    x_scale = alt.Scale(domain=[0, 1220], nice=False)
    # Reversed so the diagram reads top-down, the way it is drawn.
    y_scale = alt.Scale(domain=[30, 470], nice=False, reverse=True)
    no_axis = alt.Axis(labels=False, ticks=False, domain=False, grid=False, title=None)

    edges = alt.Chart(graph_edge_frame()).mark_line(
        color="#8c9bab", strokeWidth=1.6, point=False,
    ).encode(
        x=alt.X("x:Q", scale=x_scale, axis=no_axis),
        y=alt.Y("y:Q", scale=y_scale, axis=no_axis),
        order="order:Q",
        detail="edge:N",
    )

    boxes = alt.Chart(nodes).mark_rect(cornerRadius=6, strokeWidth=2).encode(
        x=alt.X("x1:Q", scale=x_scale, axis=no_axis),
        x2="x2:Q",
        y=alt.Y("y1:Q", scale=y_scale, axis=no_axis),
        y2="y2:Q",
        # Mid-tones deliberately: they carry white text and sit legibly on
        # both the light and the dark Streamlit background.
        color=alt.Color("status:N", scale=alt.Scale(
            domain=["ran", "not used", "start/end"],
            range=["#2f6db5", "#6b7683", "#3c8f6b"]),
            legend=alt.Legend(title=None, orient="top")),
        stroke=alt.condition("datum.chosen", alt.value("#f0a202"), alt.value("#00000000")),
        tooltip=[alt.Tooltip("label:N", title="Agent"),
                 alt.Tooltip("detail:N", title="This run")],
    )

    labels = alt.Chart(nodes).mark_text(
        color="white", fontSize=12, fontWeight=600, lineBreak="\n",
    ).encode(
        x=alt.X("cx:Q", scale=x_scale, axis=no_axis),
        y=alt.Y("cy:Q", scale=y_scale, axis=no_axis),
        text="label:N",
    )

    counts = alt.Chart(nodes[nodes["calls"] > 0]).mark_text(
        color="white", fontSize=10, dy=24,
    ).encode(
        x=alt.X("cx:Q", scale=x_scale, axis=no_axis),
        y=alt.Y("cy:Q", scale=y_scale, axis=no_axis),
        text="detail:N",
    )

    return (edges + boxes + labels + counts).properties(height=420).configure_view(
        stroke=None
    )


def select_node(node_id):
    st.session_state.graph_node = node_id


def render_graph(maker, trace):
    """The pipeline diagram, and whatever the chosen box did."""
    selected = st.session_state.get("graph_node") or "query"
    trace_calls = {n["id"]: len(graph_calls(trace, n)) for n in GRAPH_NODES}

    st.altair_chart(agent_graph_chart(trace, selected), use_container_width=True)

    # One button per box, in the rows the diagram uses, so picking an agent
    # reads as picking it off the picture.
    st.caption("Choose an agent to see exactly what it was sent and what it replied")
    rows = [["query", "plan", "next", "seek"],
            ["dbm", "code"],
            ["global", "local"],
            ["present", "answer"]]
    titles = {n["id"]: n["label"].replace("\n", " ") for n in GRAPH_NODES}
    for row in rows:
        columns = st.columns(len(row))
        for column, node_id in zip(columns, row):
            calls = trace_calls.get(node_id, 0)
            label = titles[node_id] + (f"  ({calls})" if calls else "")
            column.button(
                label,
                key=f"graph_pick_{node_id}",
                use_container_width=True,
                type="primary" if node_id == selected else "secondary",
                on_click=select_node,
                args=(node_id,),
            )

    node = next((n for n in GRAPH_NODES if n["id"] == selected), GRAPH_NODES[0])
    st.divider()
    st.subheader(titles[node["id"]])

    if node["id"] == "query":
        st.caption("What this run was asked.")
        st.code(maker.user_query or "", language=None, wrap_lines=True)
        return
    if node["id"] == "answer":
        st.caption("What it answered.")
        if maker.answer:
            st.code(maker.answer, language=None, wrap_lines=True)
        else:
            st.info("No answer yet.")
        return

    calls = graph_calls(trace, node)
    if not calls:
        st.info(
            "This agent has not run in this query. Not every run uses every "
            "agent -- the next-step agent decides which are needed."
        )
        return

    total = sum(e.get("seconds") or 0 for e in calls)
    st.caption(f"{len(calls)} model call(s) · {total:.0f}s in total")
    for index, event in enumerate(calls, start=1):
        with st.container(border=True):
            st.markdown(
                f"**Call {index} of {len(calls)}** · during {stage_label(event.get('stage'))}"
            )
            st.caption(
                f"{event['seconds']:.1f}s · "
                f"{event.get('prompt_tokens') or 0} in / "
                f"{event.get('completion_tokens') or 0} out tokens"
                f" · worker {event.get('worker') or 'unknown'}"
            )
            render_exchange(event)

    # An agent with no box would silently vanish from this view, so say so.
    known = {a for n in GRAPH_NODES if n["kind"] == "agent" for a in n["agents"]}
    seen = {e.get("agent") for e in trace.events(kind="llm_call") if e.get("agent")}
    missing = sorted(a for a in seen - known if a)
    if missing:
        st.caption(f"Not shown in the diagram: {', '.join(missing)}.")


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

    overview, graph, activity, code, memory, data, raw = st.tabs(
        ["Overview", "Agent graph", "Agent activity", "Generated code",
         "Memory", "Data", "Trace"]
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
    with memory:
        explain("memory")
        render_memory(maker)
    with data:
        explain("data")
        render_data(maker, trace)
    with raw:
        explain("trace")
        render_trace(trace)


live_area()
