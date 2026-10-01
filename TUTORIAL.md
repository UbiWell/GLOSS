# GLOSS Tutorial — Extending GLOSS

**Demo script.** Participants work in the dashboard only; the code changes
happen on the projector. The one thing participants do themselves is run a
query before and after, so the difference is something they hit rather than
something they are told.

Two demos, independent of each other:

1. **Registering a database** — GLOSS cannot answer at all, then it can.
2. **Registering a helper function** — GLOSS answers, but everyone gets a
   *different* answer, then everyone gets the same one.

The participant in the sample data is always **`user1`**, and the data spans
**2019–2022**.

---

# Demo 1 — Registering a database

## What this demonstrates

GLOSS can only answer from databases that have been **registered**. The sample
instance ships one that is fully written but deliberately unregistered, so the
difference registration makes is visible in a single before/after.

The passive sensing features are split into two databases:

- **sensing mobility database** — where the participant was and how they moved:
  distance travelled, places visited, hours at home, activity recognition.
  *Registered.*
- **sensing behavior database** — sleep, phone use, ambient sound and light,
  daily communication aggregates. *Written, not registered.*

Both are thin views over the same machinery in `sensing_data.py` — worth saying
out loud, because it makes the point that a GLOSS database is a **registered
view** (metadata plus function references), not necessarily a new data source.

---

## Before the session

Check the instances are in the unregistered state:

```bash
grep -c "^# database_info" /srv/gloss/_template/data_streams/sensing_behavior_database.py
```

`1` means commented out and ready. `0` means someone already registered it —
restore with `git checkout data_streams/sensing_behavior_database.py` and
redistribute.

Have your own instance open on the projector, with a terminal for editing and
the dashboard in a browser.

---

## Part 1 — Participants hit the wall (3 min)

**Ask everyone to run this in their dashboard:**

> How many hours did user1 sleep on 2019-10-06?

It fails. GLOSS either refuses at the planning stage (`❌ Not possible to answer
the question with current data`) or reports that the query cannot be answered
with the given datasets.

**Then point at the sidebar.** The caption reads:

```
5 databases  ·  1 not loaded yet
```

and under **Available data**, below the five live ones, greyed out:

> **sensing behavior database** — not loaded yet
> Sleep, phone use, ambient sound and light, and the study's own daily call and
> message aggregates. Written but not registered — registering it is
> demonstrated during the tutorial.

So the database exists. GLOSS just cannot reach it.

> ⚠️ **GLOSS may try to infer sleep** from how long the phone sat locked. That
> is a reasonable guess and a wrong answer — the lock/unlock database does not
> measure sleep. If it happens, it is worth a sentence: this is what an agent
> does when you ask for something it cannot measure.
>
> For a question nothing else can fake, use **"How many conversations was user1
> around on 2019-10-06?"** — no other database records audio at all.

---

## Part 2 — Show how a database is wired (5 min, on the projector)

Every database is **two files** in `data_streams/`:

| File | What it holds |
|---|---|
| `<name>_data.py` | The functions that read and summarise data, plus a `functions` dictionary describing each one |
| `<name>_database.py` | `database_info`, `function_refs`, and `register_database()` |

At start-up the registry imports **every file in `data_streams/` ending in
`_database.py`**. There is no central list to edit — the filename is the wiring.

**Open the data file first:**

```bash
vi data_streams/sensing_behavior_data.py
```

Everything works: `get_behavior_daily`, `find_behavior_feature`, and the
`functions` metadata describing them. Nothing is missing here.

**Then the registration file:**

```bash
vi data_streams/sensing_behavior_database.py
```

Here is the gap — the registration block is commented out. The registry imports
this file, finds nothing to register, moves on.

**The line worth dwelling on** is `database_info["info"]`. That string is what
the agent reads when it decides which database can answer a question. It is not
documentation; it is behaviour. The same is true of `functions` one level down:
the model never sees your implementation, only the `description`, `params`,
`returns` and `example` you wrote — so a description that promises something
the function does not return produces a confidently wrong answer.

---

## Part 3 — Register it (2 min)

Uncomment everything below the banner. Cursor on the `# database_info = {` line
(not the banner above it), then:

```
:.,$s/^# \{0,1\}//
```

Save with `:wq`. Also delete the `pending_registration` block above — that is
what puts it in the "not loaded yet" list, and it has done its job.

Three things were uncommented:

1. **`database_info`** — the name and description the agent reads
2. **`function_refs`** — name → the actual Python function
3. **`register_database()`** — hands both to the registry

> **Worth mentioning:** `database_info` had to be commented out too, not just
> the function. A module exposing both `functions` and `database_info` gets
> registered *automatically*, even without `register_database()`.

**Restart the dashboard — `Ctrl-C`, then `streamlit run sensemaking_ui.py`.**
A page reload is not enough: the registry is built once when the module is
first imported. (From the command line there is nothing to restart; each run is
a fresh process.)

The sidebar now says `6 databases`, with no "not loaded yet".

---

## Part 4 — Ask again (2 min)

Same query, unchanged:

> How many hours did user1 sleep on 2019-10-06?

**3.0 hours.**

Nothing about the data changed. Nothing about the functions changed. GLOSS now
knows the database exists, because `database_info` told it what the database
holds and `function_refs` told it what it may call.

---

## Optional — Let participants see it on their own instances

Their containers still have the unregistered version. To push yours out:

```bash
cd ~/gloss-repo
sudo bash deploy/update_instances.sh --apply
```

Changes are live immediately (the checkouts are bind-mounted), but **every
participant must restart their dashboard** — `Ctrl-C`, then
`streamlit run sensemaking_ui.py` — before the new database appears.

Good moment if the room is keeping up, and it makes the point concrete. Skip it
if you are short on time or the group is still catching up: the demo works fine
as something they watch. Note it also overwrites any file a participant has
edited, keeping a copy under `/srv/gloss/_backups/`.

---

## Talking points — demo 1

- **Discovery is by filename.** `*_database.py` in `data_streams/`. No registry
  file to edit, no import to add elsewhere.
- **Descriptions are behaviour.** The agent picks a database by reading
  `info` and `additional_instructions`. Vague descriptions mean wrong routing.
- **Metadata is the prompt.** `functions` is what the model reads before writing
  code. It must be honest about what the function actually returns — this repo
  has a real bug from exactly that: a stats function advertised missed calls it
  never computed, so the agent read a key that did not exist and reported zero.

**If someone asks how to add a function** — three edits, no other wiring: write
it in the `*_data.py` file, describe it in that file's `functions` dictionary,
add it to `function_refs` in the matching `*_database.py`.

**If someone asks how to add a whole database** — drop a CSV in `sample_data/`,
write the two files (`sensing_mobility_database.py` is the worked example),
restart. Add it to `REQUIRED_DATA_FILES` in `agents/database_registry.py` so it
is skipped cleanly when its data file is missing rather than advertised and
broken.

---

# Demo 2 — Registering a helper function

## What this demonstrates

Demo 1 was about a question GLOSS *could not answer*. This one is worse and more
interesting: a question it answers perfectly well, differently, every time.

When no helper function covers a question, the coding agent writes its own code
— and where the question needs a judgement call, it quietly makes one. Nothing
warns you. The answer just depends on who ran it.

## The query

> How many separate texting conversations did user1 have on 2019-10-06?

A "conversation" needs a gap threshold: how much silence ends one. There is no
right answer, and the count moves a long way with it. On this day, 90 messages
across 9 contacts:

| Silence that ends a conversation | Conversations |
|---|---|
| 5 minutes | **33** |
| 15 minutes | **26** |
| 30 minutes | **22** |
| 60 minutes | **17** |
| 120 minutes | **14** |

Every one of those is defensible. The agent has to pick one, and it never
mentions that it did.

## Part 1 — Everyone runs it, nobody agrees (5 min)

**Ask everyone to run the query above in their dashboard, then call out their
number.** Expect the room to disagree.

Write the numbers on the board. Then ask: *who was right?*

**Now project the Generated code tab** — yours, or ask someone with an odd
number to read theirs out. The threshold is sitting there as a bare number:

```python
if (next_message - previous_message).total_seconds() > 1800:   # 30 minutes
```

Nobody asked for 1800. Nobody was told about it. It is the single most
important decision in the answer and it was made by a language model, silently,
at the moment the code was written.

> If the room happens to agree, the point still lands — ask what would have
> happened with a 5-minute threshold, and show the table. The agreement was
> luck, not design.

## Part 2 — The fix (5 min, on the projector)

```bash
vi data_streams/sms_data.py
```

Scroll to `get_sms_conversation_blocks`. **It already exists.** It is written,
working, and documented, with the threshold as a named default:

```python
DEFAULT_CONVERSATION_GAP_MINUTES = 30
```

So why did the agent not use it? Scroll up to the `functions` dictionary. The
entry describing it is commented out — and that dictionary is the whole of what
the model knows. The model never reads your implementation. A function missing
from the metadata **does not exist** as far as the agent is concerned.

This is the same lesson as demo 1, one level down: `database_info` tells the
agent which database can help, `functions` tells it what it may call. Both are
behaviour, not documentation.

## Part 3 — Register the helper (2 min)

Uncomment the `"SMS4"` entry in `data_streams/sms_data.py`:

```
:91,103s/^    # /    /
```

and the matching line in `data_streams/sms_database.py`:

```
:41s/^    # /    /
```

Save each with `:wq`. (Line numbers are correct as shipped; if they have drifted,
search for `SMS4` and `get_sms_conversation_blocks`.)

Worth reading the description aloud before moving on — it does two jobs:

- tells the agent to use this *instead of* grouping messages by hand
- tells it to leave `gap_minutes` alone unless the question asks for a
  different threshold

That second line is what makes repeated runs agree.

**Restart the dashboard** — `Ctrl-C`, then `streamlit run sensemaking_ui.py`.

## Part 4 — Ask again (3 min)

Same query. Everyone gets **22**.

Project the Generated code tab once more: the hand-rolled grouping loop is gone,
replaced by a call to the helper. The judgement call did not disappear — it
moved out of the model and into a function, where it is written down, has a
name, and can be argued with.

> **Push it further if there is time:** ask *"How many conversations did user1
> have on 2019-10-06, counting a conversation as ending after 5 minutes of
> silence?"* and it returns 33. The default is a default, not a cage — but it
> is now an explicit choice rather than an accident.

## Talking points — demo 2

- **A helper function is a decision, recorded.** 30 minutes is not more correct
  than 15. What matters is that it is written down once instead of being
  reinvented on every run.
- **Reproducibility is the real deliverable.** Two researchers asking the same
  question of the same data should get the same number. Without the helper they
  did not.
- **This is the same failure as a wrong description.** This repo has a real bug
  from exactly that: a stats function advertised missed calls it never computed,
  so the agent read a key that did not exist and reported zero one run and 25
  the next.

---

## If something goes wrong — the demos

| Problem | Fix |
|---|---|
| Nothing changed after uncommenting | Restart the dashboard — a page reload is not enough |
| `IndentationError` or `SyntaxError` | A line kept a stray `#` or leading space; the block must line up with its neighbours |
| Database appears twice, one greyed | The `pending_registration` block is still there |
| Agent still writes its own grouping code | The `"SMS4"` metadata entry is what it reads — check that one, not `function_refs` |
| Start over (demo 1) | `git checkout data_streams/sensing_behavior_database.py` |
| Start over (demo 2) | `git checkout data_streams/sms_data.py data_streams/sms_database.py` |

---

# Offline mode

The dashboard can replay recorded runs instead of calling the model. The
example queries then work regardless of whether the gateway is up, fast, or
having a bad afternoon in front of a room.

## Recording, before the session

Run the recorder **inside a container**, not on the host. The host has no
Python environment — `provision.sh` installs only Docker, and GLOSS's
dependencies live inside the images. On the host it fails with
`ModuleNotFoundError: No module named 'langchain_openai'`.

```bash
docker exec -u p10 -w /srv/gloss/p10 gloss-p10 \
    bash -lc 'python deploy/record_offline_runs.py'
```

`bash -lc` matters: a login shell is what picks up `GATEWAY_API_KEY` and the
conda environment. Use any spare instance. These are real runs, so it takes a
while.

The two demo queries have **different right answers before and after** their
demo, so record them twice — uncommenting inside the instance you are
recording from, since that is where the state is read:

```bash
# 1. record the shipped state (command above)
# 2. uncomment both demos in /srv/gloss/p10, per the sections above
# 3. record again
# 4. git checkout data_streams/   in that instance, back to the demo state
```

Each recording stores a fingerprint of what was registered when it ran, and
replay picks the one matching the instance's current state. So the before/after
demos work offline too, and still show the difference.

Then collect and distribute. `/srv/gloss/p10` is bind-mounted, so the
recordings are already on the host at that path:

```bash
mkdir -p ~/gloss-repo/offline_runs
sudo cp /srv/gloss/p10/offline_runs/*.json ~/gloss-repo/offline_runs/
sudo bash deploy/update_instances.sh --apply
```

Recordings are not committed to git — they are deployment artifacts, and
`update_instances.sh` rsyncs them to every instance anyway.

## Using it

**Offline mode** is a toggle at the top of the sidebar, off by default. Turn it
on and the question box is replaced by a dropdown of the recorded questions:
only those can be run, and nothing reaches the model.

A replay takes about 25 seconds. It is deliberately not instant — it keeps the
original run's shape, so the long pause in code generation is still the longest
pause, and every tab fills in as it would during a real run. Stop works.

## If something goes wrong — offline mode

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: langchain_openai` | The recorder was run on the host; run it inside a container with `docker exec` |
| "No recorded runs found" | Recordings have not reached that instance — run `update_instances.sh --apply` |
| A demo query replays the wrong answer | It was recorded in only one state; record it again in the other |
| Want a different replay speed | `TARGET_SECONDS` in `agents/offline_runs.py` |
