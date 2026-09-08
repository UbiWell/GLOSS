"""
Sensing database - daily passive sensing feature aggregates.

Unlike the other data streams this file holds one row per day rather than
per event, with each feature pre-aggregated over the whole day, over three
epochs, and over each of the 24 hours. It therefore reads the CSV directly:
the shared loader filters on a ``timestamp`` column, which this file does not
have.

Column layout, per feature family ``F``:

    F_ep_0    whole day
    F_ep_1    00:00-09:00
    F_ep_2    09:00-18:00
    F_ep_3    18:00-24:00
    F_hr_0 .. F_hr_23   one value per hour

The epoch boundaries and the meaning of ``ep_0`` were derived from the data:
``F_ep_0`` equals ``F_ep_1 + F_ep_2 + F_ep_3`` on every row for 15 of the 27
summable families, and equals the sum of all 24 hourly columns. Treat ``ep_0``
as the daily total, never as a fourth time-of-day slot.
"""

import os
import sys
from datetime import datetime

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_streams.constants import SENSING

# Derived empirically; see module docstring.
EPOCH_LABELS = {
    0: "whole day",
    1: "00:00-09:00",
    2: "09:00-18:00",
    3: "18:00-24:00",
}

# Bookkeeping columns that are not sensing features.
NON_FEATURE_COLUMNS = ("uid", "is_ios", "day", "date", "timestamp")

# Feature names are terse, and picking a near-miss silently answers the wrong
# question, so every feature is returned with a description.
FEATURE_DESCRIPTIONS = {
    "act_in_vehicle": "seconds spent in a vehicle",
    "act_on_bike": "seconds spent cycling",
    "act_on_foot": "seconds spent on foot, walking or running",
    "act_running": "seconds spent running",
    "act_walking": "seconds spent walking",
    "act_still": "seconds spent stationary",
    "act_tilting": "seconds the phone was tilting",
    "act_unknown": "seconds of unclassified activity",
    "audio_amp_mean": "mean ambient audio amplitude",
    "audio_amp_std": "standard deviation of ambient audio amplitude",
    "audio_convo_duration": "seconds spent in conversation",
    "audio_convo_num": "number of conversations detected",
    "audio_voice": "seconds a human voice was detected",
    # These call features are the study's own daily aggregates, computed
    # separately from the raw call log and binned into four fixed epochs. They
    # do not reconcile with the call log database (for user1's 2019-09-30 week
    # they report 54/64/0 against the log's 46/40/17), so questions about call
    # counts should go to the call log database instead.
    "call_in_duration": "seconds spent on incoming calls, as aggregated by the study; use the call log database for call counts",
    "call_in_num": "number of incoming calls, as aggregated by the study; use the call log database for call counts",
    "call_out_duration": "seconds spent on outgoing calls, as aggregated by the study; use the call log database for call counts",
    "call_out_num": "number of outgoing calls, as aggregated by the study; use the call log database for call counts",
    "call_miss_num": "number of missed calls, as aggregated by the study; often 0 even when the call log records missed calls, so use the call log database for missed-call counts",
    "light_mean": "mean ambient light level",
    "light_std": "standard deviation of ambient light level",
    "loc_dist": "total distance travelled",
    "loc_max_dis_from_campus": "furthest distance from campus",
    "loc_visit_num": "number of places visited",
    "sms_in_num": "number of text messages received",
    "sms_out_num": "number of text messages sent",
    "unlock_duration": "seconds the phone was unlocked",
    "unlock_num": "number of times the phone was unlocked",
    "other_playing_duration": "seconds spent playing",
    "other_playing_num": "number of play sessions",
    "sleep_duration": "hours slept",
    "sleep_start": "time sleep started",
    "sleep_end": "time sleep ended",
    "quality_activity": "data-quality indicator for the activity sensor, not a behavioural measure",
    "quality_audio": "data-quality indicator for the audio sensor, not a behavioural measure",
    "quality_light": "data-quality indicator for the light sensor, not a behavioural measure",
    "quality_loc": "data-quality indicator for the location sensor, not a behavioural measure",
}

# The loc_<place>_<metric> families decompose into these two parts.
_PLACE_LABELS = {
    "food": "food venues",
    "health": "health facilities",
    "home": "home",
    "leisure": "leisure venues",
    "other_dorm": "someone else's dorm",
    "self_dorm": "their own dorm",
    "social": "social venues",
    "study": "study locations",
    "workout": "workout locations",
    "worship": "places of worship",
}

_METRIC_LABELS = {
    "dur": "hours spent at",
    "still": "seconds spent stationary at",
    "audio_amp": "mean ambient audio amplitude at",
    "audio_voice": "seconds a voice was detected at",
    "convo_duration": "seconds spent in conversation at",
    "convo_num": "number of conversations at",
    "unlock_duration": "seconds the phone was unlocked at",
    "unlock_num": "number of phone unlocks at",
}


# Words that mean the same thing when searching for a feature.
_SEARCH_SYNONYMS = {
    "hours": "duration", "hour": "duration", "hrs": "duration", "hr": "duration",
    "time": "duration", "long": "duration", "spent": "duration",
    "minutes": "duration", "seconds": "duration", "secs": "duration",
    "count": "number", "many": "number", "num": "number", "times": "number",
    "texts": "message", "text": "message", "sms": "message", "messages": "message",
    "talking": "conversation", "talk": "conversation", "conversations": "conversation",
    "phone": "unlock", "screen": "unlock",
    "asleep": "sleep", "slept": "sleep",
    "walked": "walking", "steps": "walking",
}

# Metric suffixes ranked by how likely they are to be the "primary" reading of
# a place. Someone asking about a place usually means time spent there.
_METRIC_PRIORITY = ["dur", "still", "convo_duration", "convo_num",
                    "unlock_duration", "unlock_num", "audio_voice", "audio_amp"]


def _tokenize(text):
    """Lowercase word tokens with synonyms folded together."""
    words = [w for w in "".join(
        c if c.isalnum() else " " for c in str(text).lower()
    ).split() if w]
    return {_SEARCH_SYNONYMS.get(w, w) for w in words}


def _metric_rank(name):
    """Sort key placing a place's primary metric first."""
    for index, metric in enumerate(_METRIC_PRIORITY):
        if name.endswith("_" + metric):
            return index
    return len(_METRIC_PRIORITY)


def find_sensing_feature(uid, query):
    """Rank sensing features against a plain-language description.

    Feature names are near-duplicates -- every ``loc_home_*`` feature mentions
    home, and only ``loc_home_dur`` is the time spent there. Matching by
    substring picks whichever happens to come first, so the ranking is done
    here rather than left to the caller.

    Returns the best matches first, each with its name, description and score.
    """
    frame = _load(uid)
    if frame.empty:
        return []

    time_resolved, daily_only = _families(frame)
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = []
    for name in time_resolved + daily_only:
        description = describe_feature(name)
        feature_tokens = _tokenize(name) | _tokenize(description)
        overlap = query_tokens & feature_tokens
        if not overlap:
            continue
        # Fraction of the question's words the feature accounts for, then the
        # primary-metric rank as a tie-break between same-place features.
        score = len(overlap) / len(query_tokens)
        scored.append({
            "feature": name,
            "description": description,
            "score": round(score, 3),
            "granularity": "time_resolved" if name in set(time_resolved) else "daily_only",
            "_rank": _metric_rank(name),
        })

    scored.sort(key=lambda e: (-e["score"], e["_rank"], e["feature"]))
    for entry in scored:
        entry.pop("_rank")
    return scored[:10]


def describe_feature(name):
    """Human-readable description of a feature name."""
    if name in FEATURE_DESCRIPTIONS:
        return FEATURE_DESCRIPTIONS[name]
    if name.startswith("loc_"):
        remainder = name[len("loc_"):]
        for metric, metric_label in _METRIC_LABELS.items():
            if remainder.endswith("_" + metric):
                place = remainder[: -len(metric) - 1]
                if place in _PLACE_LABELS:
                    return f"{metric_label} {_PLACE_LABELS[place]}"
    return "no description available"

functions = {
    "SENSE1": {
        "name": "list_sensing_features",
        "usecase": ["function_calling", "code_generation"],
        "description": "Lists the passive sensing feature families available in the sensing database, so a valid feature name can be chosen before querying values. Some families contain no data for a given user and are reported as unavailable.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."}
        },
        "returns": "A dictionary with 'time_resolved' (usable with all sensing functions), 'daily_only' (usable with get_sensing_daily only, mainly the loc_* place features) and 'empty' lists. Each entry gives the exact feature name and a description of what it measures; match the description to the question rather than guessing from the name, since similar names measure different things.",
        "example": "{'time_resolved': [{'feature': 'act_still', 'description': 'seconds spent stationary'}], 'daily_only': [{'feature': 'loc_home_dur', 'description': 'hours spent at home'}], 'empty': [{'feature': 'act_walking', 'description': 'seconds spent walking'}]}"
    },
    "SENSE5": {
        "name": "find_sensing_feature",
        "usecase": ["function_calling", "code_generation"],
        "description": "Finds the right sensing feature name from a plain-language description, ranked best first. Prefer this over scanning list_sensing_features by hand: many features share wording, for example every loc_home_* feature mentions home while only loc_home_dur is the time spent there, so substring matching picks the wrong one.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "query": {"type": "str", "description": "Plain-language description of the wanted measure, e.g. 'hours spent at home' or 'number of conversations'."}
        },
        "returns": "A list of candidate features ordered best-match first, each with its exact name, description, match score, and whether it supports epoch/hourly breakdowns. Take the first entry unless its description contradicts the question.",
        "example": "[{'feature': 'loc_home_dur', 'description': 'hours spent at home', 'score': 0.75, 'granularity': 'daily_only'}]"
    },
    "SENSE2": {
        "name": "get_sensing_daily",
        "usecase": ["function_calling", "code_generation"],
        "description": "Returns the daily total of a passive sensing feature for each day in the time range. Use this for questions about how much of something happened per day.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "feature": {"type": "str", "description": "The feature name, e.g. 'act_still', 'audio_convo_duration' or a daily-only place feature such as 'loc_home_dur'. Call list_sensing_features first if unsure."}
        },
        "returns": "A list of per-day values for the feature.",
        "example": "[{'date': '2020-11-02', 'feature': 'act_still', 'value': 77001.0}]"
    },
    "SENSE3": {
        "name": "get_sensing_by_epoch",
        "usecase": ["function_calling", "code_generation"],
        "description": "Returns a passive sensing feature split into time-of-day epochs for each day: night/morning (00:00-09:00), day (09:00-18:00) and evening (18:00-24:00), alongside the whole-day total. Use this for questions about when during the day something happened.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "feature": {"type": "str", "description": "The feature family name, e.g. 'act_still'."}
        },
        "returns": "A list of per-day epoch breakdowns. 'whole_day' is the daily total, not a fourth epoch, and equals the sum of the three epochs for additive features.",
        "example": "[{'date': '2020-11-02', 'feature': 'act_still', 'whole_day': 77001.0, '00:00-09:00': 31115.0, '09:00-18:00': 27563.0, '18:00-24:00': 18322.0}]"
    },
    "SENSE4": {
        "name": "get_sensing_hourly",
        "usecase": ["function_calling", "code_generation"],
        "description": "Returns a passive sensing feature broken down by hour of day for each day in the range. Use this for questions about a specific hour or about the shape of a day.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "feature": {"type": "str", "description": "The feature family name, e.g. 'act_still'."}
        },
        "returns": "A list of per-day, per-hour values with 'hour' as an integer from 0 to 23.",
        "example": "[{'date': '2020-11-02', 'feature': 'act_still', 'hour': 0, 'value': 3308.0}]"
    },
}


def _load(uid):
    """Read the sensing CSV and return this user's rows, indexed by date."""
    if os.getenv("RUNNING_IN_DOCKER") == "true":
        path = f"/workspace/sample_data/{SENSING}.csv"
    else:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(repo_root, "sample_data", f"{SENSING}.csv")

    try:
        frame = pd.read_csv(path)
    except FileNotFoundError:
        print(f"Error: CSV file '{path}' not found")
        return pd.DataFrame()

    frame = frame[frame["uid"] == uid].copy()
    # `day` is an integer such as 20181012.
    frame["date"] = pd.to_datetime(frame["day"].astype(str), format="%Y%m%d")
    return frame.sort_values("date")


def _in_range(frame, start_time, end_time):
    """Filter whole days overlapping the requested range.

    A day is included when the day itself falls between the start and end
    dates, since the rows carry no finer timing than the epoch and hour
    columns.
    """
    if frame.empty:
        return frame
    start_date = _parse(start_time).date()
    end_date = _parse(end_time).date()
    dates = frame["date"].dt.date
    return frame[(dates >= start_date) & (dates <= end_date)]


def _parse(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _clean(value):
    """Convert pandas NaN to None.

    Roughly 16% of cells are NaN, meaning the sensor reported nothing for that
    day or hour. NaN is not valid JSON and reads as the string "nan" once a
    result reaches a prompt, so missing data is returned as None instead.
    """
    return None if pd.isna(value) else value


def _feature_columns(frame, feature, kind):
    """Return the existing columns for a feature family and suffix kind."""
    if kind == "ep":
        candidates = [f"{feature}_ep_{i}" for i in range(4)]
    else:
        candidates = [f"{feature}_hr_{h}" for h in range(24)]
    return [c for c in candidates if c in frame.columns]


def _families(frame):
    """Split feature names into time-resolved and daily-only groups.

    Most features carry epoch and hour columns. The place-based ``loc_*``
    features are recorded once per day only, as a bare column.
    """
    time_resolved = {
        c.rsplit("_ep_", 1)[0] for c in frame.columns if "_ep_" in c
    } | {
        c.rsplit("_hr_", 1)[0] for c in frame.columns if "_hr_" in c
    }
    daily_only = {
        c for c in frame.columns
        if c not in NON_FEATURE_COLUMNS
        and "_ep_" not in c and "_hr_" not in c
    }
    return sorted(time_resolved), sorted(daily_only)


def _daily_column(frame, feature):
    """The column holding a feature's daily value, whichever form it takes."""
    for candidate in (f"{feature}_ep_0", feature):
        if candidate in frame.columns:
            return candidate
    return None


def list_sensing_features(uid):
    """List feature families, separating ones that hold no data for this user.

    Time-resolved features work with all four functions; daily-only features
    work with get_sensing_daily alone.
    """
    frame = _load(uid)
    if frame.empty:
        return {"time_resolved": [], "daily_only": [], "empty": []}

    time_resolved, daily_only = _families(frame)

    result = {"time_resolved": [], "daily_only": [], "empty": []}
    for family, key in (
        [(f, "time_resolved") for f in time_resolved] + [(f, "daily_only") for f in daily_only]
    ):
        columns = [c for c in frame.columns if c == family or c.startswith(family + "_")]
        total = frame[columns].fillna(0).abs().to_numpy().sum()
        bucket = key if total > 0 else "empty"
        result[bucket].append({"feature": family, "description": describe_feature(family)})
    return result


def get_sensing_daily(uid, start_time, end_time, feature):
    """Daily total of a feature for each day in the range.

    Works for both time-resolved features and the daily-only ``loc_*`` ones.
    """
    frame = _in_range(_load(uid), start_time, end_time)
    if frame.empty:
        return []

    column = _daily_column(frame, feature)
    if column is None:
        return _unknown_feature(feature, frame)

    return [
        {"date": row["date"].strftime("%Y-%m-%d"), "feature": feature, "value": _clean(row[column])}
        for _, row in frame.iterrows()
    ]

def get_sensing_by_epoch(uid, start_time, end_time, feature):
    """Feature split by time-of-day epoch for each day in the range."""
    frame = _in_range(_load(uid), start_time, end_time)
    if frame.empty:
        return []

    columns = _feature_columns(frame, feature, "ep")
    if not columns:
        return _unknown_feature(feature, frame, time_resolved_only=True)

    results = []
    for _, row in frame.iterrows():
        entry = {"date": row["date"].strftime("%Y-%m-%d"), "feature": feature}
        for index in range(4):
            column = f"{feature}_ep_{index}"
            if column in frame.columns:
                key = "whole_day" if index == 0 else EPOCH_LABELS[index]
                entry[key] = _clean(row[column])
        results.append(entry)
    return results


def get_sensing_hourly(uid, start_time, end_time, feature):
    """Feature broken down by hour of day for each day in the range."""
    frame = _in_range(_load(uid), start_time, end_time)
    if frame.empty:
        return []

    columns = _feature_columns(frame, feature, "hr")
    if not columns:
        return _unknown_feature(feature, frame, time_resolved_only=True)

    results = []
    for _, row in frame.iterrows():
        date = row["date"].strftime("%Y-%m-%d")
        for hour in range(24):
            column = f"{feature}_hr_{hour}"
            if column in frame.columns:
                results.append({
                    "date": date, "feature": feature, "hour": hour, "value": _clean(row[column])
                })
    return results


def _unknown_feature(feature, frame, time_resolved_only=False):
    """Explain an unrecognised feature rather than returning silently empty."""
    time_resolved, daily_only = _families(frame)
    if time_resolved_only:
        return {
            "error": f"Sensing feature '{feature}' has no epoch or hourly breakdown.",
            "hint": "Daily-only features such as the loc_* place features are available through get_sensing_daily.",
            "available_features": [
                {"feature": f, "description": describe_feature(f)} for f in time_resolved
            ],
        }
    return {
        "error": f"Unknown sensing feature '{feature}'.",
        "available_features": [
            {"feature": f, "description": describe_feature(f)}
            for f in time_resolved + daily_only
        ],
    }


if __name__ == "__main__":
    UID = "user1"
    print(get_sensing_daily(UID, "2020-11-02 00:00:00", "2020-11-02 23:59:59", "act_still"))
    print(get_sensing_by_epoch(UID, "2020-11-02 00:00:00", "2020-11-02 23:59:59", "act_still"))
