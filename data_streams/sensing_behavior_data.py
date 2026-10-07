"""
Sensing behaviour database - what the phone and its surroundings recorded.

The other half of the passive sensing features; location and activity live in
``sensing_mobility_data.py``. Both read the same daily-aggregate CSV through
``sensing_data.py``, which keeps all the loading, searching and granularity
logic. A "database" in GLOSS is a registered *view*: a set of feature names, a
description of what they mean, and functions the coding agent may call.

This half owns:

    sleep_*    sleep duration, start and end
    unlock_*   how often and how long the phone was unlocked
    audio_*    ambient sound level, detected voice, conversations
    light_*    ambient light level
    call_*     the study's own daily call aggregates
    sms_*      the study's own daily message aggregates
    other_*    time spent playing

together with the two data-quality indicators for those sensors.

This module is complete and working. What it does NOT have is registration --
see ``sensing_behavior_database.py``.
"""

from data_streams import sensing_data

# Declared explicitly rather than as "whatever mobility does not claim", so a
# feature added later belongs to neither half until someone decides which.
FEATURE_PREFIXES = (
    "sleep_", "unlock_", "audio_", "light_", "call_", "sms_", "other_",
)
EXTRA_FEATURES = {"quality_audio", "quality_light"}

OTHER_DATABASE = "sensing mobility database"


def owns_feature(name):
    """True when `name` is one of this database's features."""
    return name.startswith(FEATURE_PREFIXES) or name in EXTRA_FEATURES


def _guard(feature):
    """Reject a feature belonging to the other half, and say where it lives."""
    if not owns_feature(feature):
        raise ValueError(
            f"'{feature}' is not a behaviour feature. Sleep, phone use, sound, light "
            f"and communication features are served here; location and activity "
            f"features belong to the {OTHER_DATABASE}."
        )


# The shared engine raises advice naming its own functions -- "available as:
# hourly via get_sensing_hourly(...)". Those are not what this database
# exposes, and following that advice would take the agent around the
# registration it is supposed to go through. Rewrite the names to this
# database's own before the message reaches anyone.
_ENGINE_NAMES = {
    "list_sensing_features": "list_behavior_features",
    "find_sensing_feature": "find_behavior_feature",
    "get_sensing_daily": "get_behavior_daily",
    "get_sensing_by_epoch": "get_behavior_by_epoch",
    "get_sensing_hourly": "get_behavior_hourly",
}


def _own_names(error):
    """Re-raise an engine error with this database's function names in it."""
    message = str(error)
    for engine, ours in _ENGINE_NAMES.items():
        message = message.replace(engine, ours)
    return ValueError(message)


def list_behavior_features(uid):
    """Behaviour feature families, split the same way sensing_data splits them."""
    everything = sensing_data.list_sensing_features(uid)
    return {
        bucket: [e for e in entries if owns_feature(e["feature"])]
        for bucket, entries in everything.items()
    }


def find_behavior_feature(uid, query):
    """Rank this database's features against a plain-language description."""
    ranked = sensing_data.find_sensing_feature(uid, query)
    return [e for e in ranked if owns_feature(e["feature"])][:10]


def get_behavior_daily(uid, start_time, end_time, feature):
    """Daily total of a behaviour feature for each day in the range."""
    _guard(feature)
    try:
        return sensing_data.get_sensing_daily(uid, start_time, end_time, feature)
    except ValueError as error:
        raise _own_names(error) from None


def get_behavior_by_epoch(uid, start_time, end_time, feature):
    """Behaviour feature split into time-of-day epochs for each day."""
    _guard(feature)
    try:
        return sensing_data.get_sensing_by_epoch(uid, start_time, end_time, feature)
    except ValueError as error:
        raise _own_names(error) from None


def get_behavior_hourly(uid, start_time, end_time, feature):
    """Behaviour feature broken down by hour of day for each day."""
    _guard(feature)
    try:
        return sensing_data.get_sensing_hourly(uid, start_time, end_time, feature)
    except ValueError as error:
        raise _own_names(error) from None


functions = {
    "BEHAVIOR1": {
        "name": "list_behavior_features",
        "usecase": ["function_calling", "code_generation"],
        "description": "Lists the sleep, phone-use, sound, light and communication feature families available, so a valid feature name can be chosen before querying values. Families holding no data for this user are reported as unavailable.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."}
        },
        "returns": "A dictionary with three lists: 'time_resolved' (features with daily, epoch and hourly values), 'daily_only' (features recorded once per day, such as the sleep features), and 'empty' (families with no data for this user). Each entry has a feature name and a description.",
        "example": {
            "time_resolved": [{"feature": "unlock_num", "description": "number of times the phone was unlocked"}],
            "daily_only": [{"feature": "sleep_duration", "description": "hours slept"}],
            "empty": [{"feature": "other_playing_num", "description": "number of play sessions"}],
        },
    },
    "BEHAVIOR2": {
        "name": "find_behavior_feature",
        "usecase": ["function_calling", "code_generation"],
        "description": "Finds the right sleep, phone-use, sound, light or communication feature from a plain-language description. Feature names are terse and easy to confuse, so use this rather than guessing a name.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "query": {"type": "str", "description": "Plain-language description of the wanted measure, e.g. 'how long they slept' or 'how often they checked their phone'."},
        },
        "returns": "A list of candidate features ordered best-match first, each with its exact name, description, match score, and whether it supports epoch/hourly breakdowns. Take the first entry unless its description contradicts the question.",
        "example": [{"feature": "sleep_duration", "description": "hours slept", "score": 0.67, "granularity": "daily_only"}],
    },
    "BEHAVIOR3": {
        "name": "get_behavior_daily",
        "usecase": ["function_calling", "code_generation"],
        "description": "Daily total of one sleep, phone-use, sound, light or communication feature, for each day in the range. Coverage is ragged: a feature may be recorded at some granularities and not others, and the error names the function to use instead.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name, as returned by find_behavior_feature."},
        },
        "returns": "A list of one entry per day, each with date, feature and value. A value of None means the sensor reported nothing that day.",
        "example": [{"date": "2019-10-06", "feature": "sleep_duration", "value": 3.0}],
    },
    "BEHAVIOR4": {
        "name": "get_behavior_by_epoch",
        "usecase": ["function_calling", "code_generation"],
        "description": "A behaviour feature split into time-of-day epochs for each day: night/morning (00:00-09:00), day (09:00-18:00) and evening (18:00-24:00), alongside the whole-day total. Use this for questions about when during the day something happened.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name. The sleep features are daily only and have no epochs."},
        },
        "returns": "A list of per-day epoch breakdowns. 'whole_day' is the daily total, not a fourth epoch, and equals the sum of the three epochs for additive features.",
        "example": [{"date": "2019-10-06", "feature": "unlock_num", "whole_day": 240, "00:00-09:00": 106, "09:00-18:00": 98, "18:00-24:00": 36}],
    },
    "BEHAVIOR5": {
        "name": "get_behavior_hourly",
        "usecase": ["function_calling", "code_generation"],
        "description": "A behaviour feature broken down by hour of day, for each day in the range. Use this when the question is about the shape of a day rather than its total.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name. Only time-resolved features have hourly columns."},
        },
        "returns": "A list of one entry per day and hour, each with date, feature, hour (0-23) and value.",
        "example": [{"date": "2019-10-06", "feature": "unlock_num", "hour": 0, "value": 52}],
    },
}
