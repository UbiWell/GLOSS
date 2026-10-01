"""
Sensing mobility database - where the participant was and how they moved.

One half of the passive sensing features; the other half lives in
``sensing_behavior_data.py``. Both read the same daily-aggregate CSV through
``sensing_data.py``, which keeps all the loading, searching and granularity
logic. A "database" in GLOSS is a registered *view*: a set of feature names, a
description of what they mean, and functions the coding agent may call. Nothing
here re-reads the CSV.

This half owns:

    loc_*    distance travelled, places visited, and the per-place families
             (hours at home, conversation at study locations, and so on)
    act_*    activity recognition -- still, on foot, in a vehicle, cycling

together with the two data-quality indicators for those sensors.
"""

from data_streams import sensing_data

# Feature families this database answers for. The behaviour database declares
# the rest explicitly rather than taking "everything else", so a feature added
# later belongs to neither until someone decides which -- better than being
# silently absorbed by whichever half happens to match first.
FEATURE_PREFIXES = ("loc_", "act_")
EXTRA_FEATURES = {"quality_loc", "quality_activity"}

OTHER_DATABASE = "sensing behavior database"


def owns_feature(name):
    """True when `name` is one of this database's features."""
    return name.startswith(FEATURE_PREFIXES) or name in EXTRA_FEATURES


def _guard(feature):
    """Reject a feature belonging to the other half, and say where it lives.

    Without this the call would reach sensing_data and fail with "unknown
    feature", sending the coding agent looking for a spelling mistake instead
    of the database next door.
    """
    if not owns_feature(feature):
        raise ValueError(
            f"'{feature}' is not a mobility feature. Location and activity features "
            f"are served here; sleep, phone use, sound, light and communication "
            f"features belong to the {OTHER_DATABASE}."
        )


def list_mobility_features(uid):
    """Mobility feature families, split the same way sensing_data splits them."""
    everything = sensing_data.list_sensing_features(uid)
    return {
        bucket: [e for e in entries if owns_feature(e["feature"])]
        for bucket, entries in everything.items()
    }


def find_mobility_feature(uid, query):
    """Rank this database's features against a plain-language description."""
    ranked = sensing_data.find_sensing_feature(uid, query)
    return [e for e in ranked if owns_feature(e["feature"])][:10]


def get_mobility_daily(uid, start_time, end_time, feature):
    """Daily total of a mobility feature for each day in the range."""
    _guard(feature)
    return sensing_data.get_sensing_daily(uid, start_time, end_time, feature)


def get_mobility_by_epoch(uid, start_time, end_time, feature):
    """Mobility feature split into time-of-day epochs for each day."""
    _guard(feature)
    return sensing_data.get_sensing_by_epoch(uid, start_time, end_time, feature)


def get_mobility_hourly(uid, start_time, end_time, feature):
    """Mobility feature broken down by hour of day for each day."""
    _guard(feature)
    return sensing_data.get_sensing_hourly(uid, start_time, end_time, feature)


functions = {
    "MOBILITY1": {
        "name": "list_mobility_features",
        "usecase": ["function_calling", "code_generation"],
        "description": "Lists the location and activity feature families available, so a valid feature name can be chosen before querying values. Families holding no data for this user are reported as unavailable.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."}
        },
        "returns": "A dictionary with three lists: 'time_resolved' (features with daily, epoch and hourly values), 'daily_only' (features recorded once per day, which is most of the per-place loc_* features), and 'empty' (families with no data for this user). Each entry has a feature name and a description.",
        "example": {
            "time_resolved": [{"feature": "loc_dist", "description": "total distance travelled"}],
            "daily_only": [{"feature": "loc_home_dur", "description": "hours spent at home"}],
            "empty": [{"feature": "act_walking", "description": "seconds spent walking"}],
        },
    },
    "MOBILITY2": {
        "name": "find_mobility_feature",
        "usecase": ["function_calling", "code_generation"],
        "description": "Finds the right location or activity feature from a plain-language description. Feature names are near-duplicates -- every loc_home_* feature mentions home, but only loc_home_dur is the time spent there -- so use this rather than guessing a name.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "query": {"type": "str", "description": "Plain-language description of the wanted measure, e.g. 'hours spent at home' or 'how far they travelled'."},
        },
        "returns": "A list of candidate features ordered best-match first, each with its exact name, description, match score, and whether it supports epoch/hourly breakdowns. Take the first entry unless its description contradicts the question.",
        "example": [{"feature": "loc_home_dur", "description": "hours spent at home", "score": 0.75, "granularity": "daily_only"}],
    },
    "MOBILITY3": {
        "name": "get_mobility_daily",
        "usecase": ["function_calling", "code_generation"],
        "description": "Daily total of one location or activity feature, for each day in the range. Works for every mobility feature, including the per-place loc_* ones that have no finer breakdown.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name, as returned by find_mobility_feature."},
        },
        "returns": "A list of one entry per day, each with date, feature and value. A value of None means the sensor reported nothing that day.",
        "example": [{"date": "2019-10-06", "feature": "loc_home_dur", "value": 22.38}],
    },
    "MOBILITY4": {
        "name": "get_mobility_by_epoch",
        "usecase": ["function_calling", "code_generation"],
        "description": "A mobility feature split into time-of-day epochs for each day: night/morning (00:00-09:00), day (09:00-18:00) and evening (18:00-24:00), alongside the whole-day total. Use this for questions about when during the day something happened.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name. Only time-resolved features have epochs; the per-place loc_* features do not."},
        },
        "returns": "A list of per-day epoch breakdowns. 'whole_day' is the daily total, not a fourth epoch, and equals the sum of the three epochs for additive features.",
        "example": [{"date": "2019-10-06", "feature": "act_still", "whole_day": 71580, "00:00-09:00": 31020, "09:00-18:00": 25560, "18:00-24:00": 15000}],
    },
    "MOBILITY5": {
        "name": "get_mobility_hourly",
        "usecase": ["function_calling", "code_generation"],
        "description": "A mobility feature broken down by hour of day, for each day in the range. Use this when the question is about the shape of a day rather than its total.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "Start of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "end_time": {"type": "str", "description": "End of the range, 'YYYY-MM-DD HH:MM:SS'."},
            "feature": {"type": "str", "description": "Exact feature name. Only time-resolved features have hourly columns."},
        },
        "returns": "A list of one entry per day and hour, each with date, feature, hour (0-23) and value.",
        "example": [{"date": "2019-10-06", "feature": "loc_dist", "hour": 14, "value": 311.4}],
    },
}
