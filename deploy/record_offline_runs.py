#!/usr/bin/env python3
"""
Record the tutorial's example queries so they can be replayed without a model.

Run this on the SERVER, with the gateway working, before the session. Each
query is run for real and the whole run -- stages, generated code, model
latencies, answer -- is written to ``offline_runs/``. The dashboard's Offline
mode then replays them, so a slow or dead gateway cannot derail the examples in
front of a room.

    python3 deploy/record_offline_runs.py              # record everything missing
    python3 deploy/record_offline_runs.py --list       # what is recorded already
    python3 deploy/record_offline_runs.py --force      # re-record everything
    python3 deploy/record_offline_runs.py --only sleep # just matching questions

Two of these questions have different right answers before and after the
tutorial's demos:

    "how many hours did user1 sleep"      fails until the sensing behaviour
                                          database is registered
    "how many separate texting ..."       varies until the conversation helper
                                          is registered

Each recording stores a fingerprint of what was registered when it ran, and
replay prefers the recording matching the current state. So record these twice:
once as shipped, then again after uncommenting the two demos -- and remember to
put the files back afterwards.

    python3 deploy/record_offline_runs.py                   # before state
    # ... uncomment both demos, per TUTORIAL.md ...
    python3 deploy/record_offline_runs.py                   # after state
    git checkout data_streams/                              # back to the demo state

Recording every query takes a while: these are real runs.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import offline_runs  # noqa: E402

# sensemaking_process pulls in the whole agent stack, which needs the full
# conda environment. Imported lazily inside main() so --list and --help work
# anywhere, including a checkout without the model libraries installed.

CLEAR = "clear and concise"

# Order here is the order of the dashboard's picker.
QUERIES = [
    {
        "label": "Texts sent and received",
        "query": "How many text messages did user1 send and receive on 2019-10-06, "
                 "and with how many different contacts?",
        "instructions": "Be clear and concise",
    },
    {
        "label": "Longest call, and apps during it (JSON)",
        "query": "On 2019-10-06, what was user1's longest phone call, and which apps "
                 "was user1 using while that call was going on?",
        "instructions": "Give as JSON with follow fields call-duration: , start_time, "
                        "app_names = []",
    },
    {
        "label": "Summarise a day",
        "query": "Summarize what user1's day looked like on 2021-07-17.",
        "instructions": "focus on qualitative aspects",
    },
    # The dashboard's own starter examples.
    {
        "label": "Most used app",
        "query": "on nov 2 2020, for user1 what was the most used app by duration?",
        "instructions": CLEAR,
    },
    {
        "label": "Texts on nov 2",
        "query": "on nov 2 2020, for user1 how many text messages were sent and received?",
        "instructions": CLEAR,
    },
    {
        "label": "Hours at home",
        "query": "on nov 2 2020, for user1 how many hours were spent at home?",
        "instructions": CLEAR,
    },
    {
        "label": "Missed calls",
        "query": "on nov 2 2020, for user1 how many calls were missed?",
        "instructions": CLEAR,
    },
    # TUTORIAL.md demo 1 -- record before and after registering the database.
    {
        "label": "Sleep (demo 1)",
        "query": "How many hours did user1 sleep on 2019-10-06?",
        "instructions": CLEAR,
        "note": "Demo 1. Fails before the sensing behaviour database is registered.",
    },
    {
        "label": "Conversations overheard (demo 1 alternative)",
        "query": "How many conversations was user1 around on 2019-10-06?",
        "instructions": CLEAR,
        "note": "Demo 1 alternative, for when sleep gets inferred from lock/unlock.",
    },
    # TUTORIAL.md demo 2 -- record before and after registering the helper.
    {
        "label": "Texting conversations (demo 2)",
        "query": "How many separate texting conversations did user1 have on 2019-10-06?",
        "instructions": CLEAR,
        "note": "Demo 2. Answer varies until get_sms_conversation_blocks is registered.",
    },
]


def existing_ids():
    return {
        offline_runs.recording_id(
            r["query"], r.get("instructions"), r.get("fingerprint", "")
        )
        for r in offline_runs.load_recordings()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true",
                        help="show what is already recorded and exit")
    parser.add_argument("--force", action="store_true",
                        help="re-record even where a recording exists for this state")
    parser.add_argument("--only", default=None,
                        help="only questions containing this text (case-insensitive)")
    args = parser.parse_args()

    fingerprint = offline_runs.state_fingerprint()

    if args.list:
        recordings = offline_runs.load_recordings()
        if not recordings:
            print(f"No recordings in {offline_runs.RECORDINGS_DIR}")
            return 0
        print(f"{len(recordings)} recording(s) in {offline_runs.RECORDINGS_DIR}")
        print(f"this instance's state fingerprint: {fingerprint}\n")
        for r in recordings:
            mark = "*" if r.get("fingerprint") == fingerprint else " "
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("recorded_at", 0)))
            print(f" {mark} [{r.get('fingerprint','?')}] {when}  {r['query'][:64]}")
        print("\n* = recorded in this instance's current state")
        return 0

    wanted = QUERIES
    if args.only:
        needle = args.only.lower()
        wanted = [q for q in QUERIES
                  if needle in q["query"].lower() or needle in q["label"].lower()]
        if not wanted:
            print(f"Nothing matches --only {args.only!r}")
            return 1

    import sensemaking_process  # noqa: PLC0415 - see the note at the imports

    already = existing_ids()
    print(f"==> State fingerprint: {fingerprint}")
    print(f"==> Writing to: {offline_runs.RECORDINGS_DIR}\n")

    recorded = skipped = failed = 0
    for index, item in enumerate(wanted, start=1):
        query, instructions = item["query"], item.get("instructions", CLEAR)
        identifier = offline_runs.recording_id(query, instructions, fingerprint)

        if identifier in already and not args.force:
            print(f"[{index}/{len(wanted)}] already recorded for this state: {item['label']}")
            skipped += 1
            continue

        print(f"[{index}/{len(wanted)}] recording: {item['label']}")
        print(f"            {query}")
        started = time.time()
        try:
            maker = sensemaking_process.SenseMaker(query, instructions)
            maker.make_sense(verbose=False)
        except Exception as exc:  # noqa: BLE001 - one bad run must not stop the rest
            print(f"            FAILED after {time.time() - started:.0f}s: {exc}\n")
            failed += 1
            continue

        # A refusal is a legitimate recording: demo 1 depends on replaying one.
        path = offline_runs.save_recording(
            query=query, instructions=instructions, fingerprint=fingerprint,
            maker=maker, label=item["label"], note=item.get("note", ""),
            order=QUERIES.index(item),
        )
        answer = (maker.answer or "").replace("\n", " ")[:72]
        print(f"            {time.time() - started:.0f}s -> {os.path.basename(path)}")
        print(f"            answer: {answer}\n")
        recorded += 1

    print(f"==> {recorded} recorded, {skipped} skipped, {failed} failed.")
    if failed:
        print("==> Re-run to retry the failures; existing recordings are kept.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
