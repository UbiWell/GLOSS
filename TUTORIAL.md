# GLOSS Tutorial — Running the Demos

Two demos, each the same shape: participants run a query and it fails or
disagrees, you uncomment a block, everyone runs it again and it works.

Participants only ever use the dashboard. The code changes are yours.

---

## Connecting

Each participant has a number, a UI port (`8500 +` their number) and a password,
all on their handout.

```bash
ssh -p 65173 -L 8501:127.0.0.1:<THEIR-UI-PORT> p<NN>@<server>
streamlit run sensemaking_ui.py
```

Then <http://localhost:8501>. Question and presentation instructions go in the
sidebar; both must be filled before **Run** works.

---

## Demo 1 — registering a database

The sensing features are split in two. **sensing mobility** (location,
activity) is registered; **sensing behavior** (sleep, phone use, audio, light)
is written but not registered.

**Query:**

> How many hours did user1 sleep on 2019-10-06?

Before: it fails, and the sidebar shows `5 databases · 1 not loaded yet`.
After: **3.0 hours**.

**Uncomment** `data_streams/sensing_behavior_database.py` — the block under
`UNCOMMENT EVERYTHING BELOW`, which is `database_info`, `function_refs` and
`register_database()`. Delete the `pending_registration` block above it.

> If GLOSS infers sleep from how long the phone sat locked, say so — that is
> what an agent does when asked for something it cannot measure, and the
> lock/unlock database does not measure sleep.
>
> Do **not** fall back on *"How many conversations was user1 around on
> 2019-10-06?"*. Unregistered it does not refuse, and its answer is not so
> much wrong as to a different question. The planner reads "conversations" as
> phone calls plus texting threads, drops "around" — the word that would have
> pinned it to the microphone — and composes a plan from the call log and sms
> databases, never needing the one it does not have. It answers 46.
>
> That is demo 2's problem turning up inside demo 1: an ambiguous word with a
> plausible stand-in already registered. Sleep works precisely because nothing
> registered can pretend to measure it.

---

## Demo 2 — registering a helper function

**Query:**

> On 2019-10-06, how many separate back-and-forth texting exchanges did user1
> have, where a long gap with no messages starts a new one?

Before: **9**. After: **22**.

The agent makes two silent decisions to get 9. It picks a gap — 30 minutes,
unprompted — and it sorts every message into one stream, so a text to one
person and a text to another twenty minutes later count as the same
conversation. Both are invisible in the answer:

| gap it picks | one combined stream (what it does) | per contact (what the helper does) |
|---|---|---|
| 5 min | 24 | 33 |
| 30 min | **9** | **22** |
| 120 min | 4 | 14 |

The helper encodes both decisions, so everyone gets 22. Show the **Generated
code** tab on each side — before, a hand-rolled loop with a bare `timedelta(minutes=30)`;
after, one call to `get_sms_conversation_blocks`, with the agent saying it is
using the function because it "handles the long gap logic".

> The 9 is a coincidence worth not being caught out by: user1 texted 9 people
> that day, so the wrong method lands on a number that looks like an obvious
> right answer.

> Do not shorten this to "how many separate texting conversations". That reads
> as "how many people did they text", and the agent answers it with
> `unique_contacts` — 9, identically with and without the helper, so the demo
> shows nothing.

**Uncomment** two things: the `"SMS4"` entry in `data_streams/sms_data.py`
(lines 91–103) and the matching line in `data_streams/sms_database.py`
(line 41).

The function itself already exists and works. Only its entry in the `functions`
metadata was missing, and that metadata is all the model sees.

---

## Deploying a change to every instance

Edit on the host, then push it out. `~/gloss-repo` is a git checkout; the
instances are not.

```bash
cd ~/gloss-repo
vi data_streams/sensing_behavior_database.py      # or the sms files
sudo bash deploy/update_instances.sh --apply
```

Non-interactive, if you would rather not drive vi live:

```bash
cd ~/gloss-repo
L=$(grep -n "^# database_info" data_streams/sensing_behavior_database.py | cut -d: -f1)
ex -s -c "${L},\$s/^# \{0,1\}//" -c wq data_streams/sensing_behavior_database.py
ex -s -c "91,103s/^    # /    /" -c wq data_streams/sms_data.py
ex -s -c "41s/^    # /    /"     -c wq data_streams/sms_database.py
sudo bash deploy/update_instances.sh --apply
```

Check it registered — expect **6** databases and **4** sms functions:

```bash
docker exec -u p01 -w /srv/gloss/p01 gloss-p01 bash -lc \
  'python -c "from agents.database_registry import get_all_databases as g, \
   get_functions_for_database as f; print(len(g()), len(f(\"sms database\")))"'
```

**Everyone must restart Streamlit** — `Ctrl-C`, then
`streamlit run sensemaking_ui.py`. The registry is built once when the process
starts, so a page reload will not pick up the new database.

**Afterwards, put it back:**

```bash
cd ~/gloss-repo
git checkout data_streams/
sudo bash deploy/update_instances.sh --apply
```

---

## Offline mode

Replays recorded runs instead of calling the model, so the examples work even
if the gateway is slow or down. A sidebar toggle, off by default; the question
box becomes a dropdown of recorded questions.

The demos work offline too. Each demo question is recorded twice and both are
listed, as `(commented)` and `(uncommented)` — so you pick the side you want
rather than depending on what happens to be registered:

```
Sleep (demo 1)  (commented)        → refuses
Sleep (demo 1)  (uncommented)      → 3.0 hours
```

### Recording, before the session

Run the recorder **inside a container** — the host has no Python environment.
Collect **before** reverting: reverting rsyncs the source over the instance,
and deletions are mirrored inside `offline_runs/`.

```bash
# 1. everything, in the shipped state
docker exec -d -u p10 -w /srv/gloss/p10 gloss-p10 \
    bash -lc 'python -u deploy/record_offline_runs.py > offline_record.log 2>&1'
tail -f /srv/gloss/p10/offline_record.log          # ends: ==> 10 recorded

# 2. register both demos in that instance
docker exec -u p10 -w /srv/gloss/p10 gloss-p10 bash -lc \
  'L=$(grep -n "^# database_info" data_streams/sensing_behavior_database.py | cut -d: -f1) && \
   ex -s -c "${L},\$s/^# \{0,1\}//" -c wq data_streams/sensing_behavior_database.py && \
   ex -s -c "91,103s/^    # /    /" -c wq data_streams/sms_data.py && \
   ex -s -c "41s/^    # /    /" -c wq data_streams/sms_database.py'

# 3. confirm — expect "6 4". If it says 5, stop: step 4 would record the
#    before-answers a second time.
docker exec -u p10 -w /srv/gloss/p10 gloss-p10 bash -lc \
  'python -c "from agents.database_registry import get_all_databases as g, \
   get_functions_for_database as f; print(len(g()), len(f(\"sms database\")))"'

# 4. the three demo questions again, now registered
docker exec -d -u p10 -w /srv/gloss/p10 gloss-p10 \
    bash -lc 'python -u deploy/record_offline_runs.py --demos > offline_demos.log 2>&1'

# 5. collect, BEFORE reverting
rm -f /srv/gloss/p10/offline_record.log /srv/gloss/p10/offline_demos.log
mkdir -p ~/gloss-repo/offline_runs
sudo cp /srv/gloss/p10/offline_runs/*.json ~/gloss-repo/offline_runs/
sudo chown -R $USER:$USER ~/gloss-repo/offline_runs
ls ~/gloss-repo/offline_runs/*.json | wc -l        # expect 13

# 6. revert the instance and distribute, in one step
sudo bash deploy/update_instances.sh --apply
```

Thirteen files, thirteen rows in the picker: seven questions recorded once,
three recorded twice. Recordings are not committed to git.

Other flags, all run the same way:

| Flag | What it does |
|---|---|
| `--list` | what is recorded, and under which state |
| `--only <text>` | record one question |
| `--demos` | the three demo questions only |
| `--prune` | delete recordings whose question or instructions have since been edited |
| `--relabel` | stamp `(commented)`/`(uncommented)` onto recordings made before labels existed; run in the shipped state |

---

## If something goes wrong

| Problem | Fix |
|---|---|
| Nothing changed after uncommenting | Restart Streamlit — a page reload is not enough |
| `IndentationError` or `SyntaxError` | A line kept a stray `#`; the block must line up with its neighbours |
| Database still missing | `grep -c "^database_info" data_streams/sensing_behavior_database.py` — expect `1` |
| Agent still invents its own grouping code | The `"SMS4"` metadata entry is what it reads, not `function_refs` |
| A non-demo question appears twice | A stale recording whose question or instructions were edited: `--prune`. The three demo questions are meant to appear twice |
| A demo question has no `(commented)`/`(uncommented)` label | Recorded before labels existed: `--relabel` |
| A demo question appears once, not twice | Only one state was recorded — do the `--demos` pass in the other |
| Start over | `git checkout data_streams/` on the host, then `--apply`. Instances are not git checkouts |
