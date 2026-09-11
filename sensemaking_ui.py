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

    worker = threading.Thread(target=work, daemon=True)
    st.session_state.worker = worker
    worker.start()


def stop_run():
    maker = st.session_state.sense_maker
    if maker is not None:
        maker.cancel.set()


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

    errors = trace.events(kind="error")
    if errors:
        with st.container(border=True):
            st.error(f"{len(errors)} problem(s) during this run")
            for event in errors[-4:]:
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
                st.markdown(f"**{stage}** asked the model")
                st.caption(
                    f"{event['seconds']:.1f}s · {tokens} tokens · "
                    f"worker {event.get('worker') or 'unknown'}"
                    + (f" · attempt {event['attempt']}" if event.get("attempt", 1) > 1 else "")
                )
        elif kind == "db_query":
            with st.chat_message("user"):
                st.markdown(f"**{stage}** queried {', '.join(event.get('databases') or [])}")
                st.caption(event.get("request") or "")
        elif kind == "answer":
            with st.chat_message("assistant"):
                st.markdown("**PRESENTATION** produced the final answer")
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
                st.code(event.get("code_block") or "", language="python")
                with st.expander("The agent's full message"):
                    st.markdown(event.get("code") or "")
            else:
                st.markdown(f"**The agent said** (round {event.get('round_index')})")
                st.markdown(event.get("code") or "")
        else:
            st.markdown("**Output from running it**")
            st.code(event.get("output") or "", language="text")
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
                "Each tab above shows one of these. Code generation prints nothing "
                "while it runs; a few minutes of quiet is normal."
            )
        return

    trace = maker.trace

    if is_running():
        st.info(f"Running — {maker.current_step or 'starting'}", icon="⏳")
    elif trace.events(kind="error"):
        st.warning("Finished with problems — see Overview.", icon="⚠️")
    else:
        st.success("Finished", icon="✅")

    overview, activity, code, memory, data, raw = st.tabs(
        ["Overview", "Agent activity", "Generated code", "Memory", "Data", "Trace"]
    )
    with overview:
        render_overview(maker, trace)
    with activity:
        render_activity(trace)
    with code:
        render_code(trace)
    with memory:
        render_memory(maker)
    with data:
        render_data(maker, trace)
    with raw:
        render_trace(trace)


live_area()
