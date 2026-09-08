"""
Adapters from the Android study dataset to the record shapes GLOSS expects.

The original sample data was an iOS/Garmin study (uid ``test004``). The current
sample data comes from an Android study and stores the same phenomena in a
different shape, so each adapter translates raw CSV rows into the record format
the existing data_streams modules already parse. Downstream block/statistic
logic is then unchanged.

Applied right after ``fetch_documents_between_timestamps`` in the modules that
consume them.
"""

# Android CallLog.Calls type codes.
# https://developer.android.com/reference/android/provider/CallLog.Calls
CALL_TYPE_INCOMING = 1
CALL_TYPE_OUTGOING = 2
CALL_TYPE_MISSED = 3
CALL_TYPE_REJECTED = 5

# Foreground-app samples arrive every ~2-4 minutes (240s median). Anything
# longer is treated as sampling having stopped rather than continued use.
MAX_SAMPLE_GAP_SECONDS = 600

_CALL_TYPE_NAMES = {
    CALL_TYPE_INCOMING: "incoming",
    CALL_TYPE_OUTGOING: "outgoing",
    CALL_TYPE_MISSED: "missed",
    CALL_TYPE_REJECTED: "rejected",
}


def adapt_lock_unlock(records):
    """Convert unlock rows into ``lock_state`` records.

    The dataset's ``data`` column is inverted relative to GLOSS's convention:
    ``data == 1`` marks the phone being unlocked, while GLOSS treats
    ``lock_state == 1`` as locked. Established from the data itself -- states
    alternate 99.4% of the time, and ``data == 0`` accounts for 84.6% of
    elapsed time with a 139s median hold versus 9s for ``data == 1``, so the
    long-held state is the locked one.
    """
    adapted = []
    for record in records:
        if "data" not in record:
            adapted.append(record)
            continue
        converted = dict(record)
        converted["lock_state"] = 0 if int(record["data"]) == 1 else 1
        adapted.append(converted)
    return adapted


def adapt_running_apps(records, max_gap_seconds=MAX_SAMPLE_GAP_SECONDS):
    """Convert periodic foreground-app samples into open/close events.

    The Android data samples the running app every few minutes rather than
    logging transitions, so a session is inferred: a change in the sampled
    package closes the previous app and opens the new one. Durations are
    therefore accurate only to the sampling interval.

    Sampling also stops while the phone is off, and without a guard the app
    seen last would be credited the entire silent stretch. A gap longer than
    ``max_gap_seconds`` is treated as an interruption: the running app is
    closed ``max_gap_seconds`` after its last sighting, bounding the error
    instead of attributing hours of idle time to it.

    Emits the ``{appName, status, timestamp}`` records that app_usage_data
    already understands, with ``status`` of "open" or "close".
    """
    samples = sorted(
        (r for r in records if r.get("data")), key=lambda r: r["timestamp"]
    )
    if not samples:
        return []

    events = []
    current_app = None
    previous_timestamp = None

    for sample in samples:
        app = sample["data"]
        timestamp = sample["timestamp"]

        if current_app is None:
            events.append({"appName": app, "status": "open", "timestamp": timestamp})
            current_app, previous_timestamp = app, timestamp
            continue

        if timestamp - previous_timestamp > max_gap_seconds:
            # Sampling stopped; close where the evidence ended.
            events.append(
                {
                    "appName": current_app,
                    "status": "close",
                    "timestamp": previous_timestamp + max_gap_seconds,
                }
            )
            events.append({"appName": app, "status": "open", "timestamp": timestamp})
            current_app = app
        elif app != current_app:
            events.append({"appName": current_app, "status": "close", "timestamp": timestamp})
            events.append({"appName": app, "status": "open", "timestamp": timestamp})
            current_app = app

        previous_timestamp = timestamp

    # Close the final session at the last observed sample.
    events.append(
        {"appName": current_app, "status": "close", "timestamp": previous_timestamp}
    )
    return events


def adapt_call_log(records):
    """Convert flat call rows into the per-call event triples GLOSS parses.

    The iOS data logged each call as separate Incoming/Connected/Disconnected
    events sharing a ``callId``; the Android data has one row per call carrying
    a type code and a duration. Each row is expanded back into that triple so
    ``get_call_log_blocks`` works unchanged.

    A missed or rejected call becomes a zero-duration Disconnected event, which
    is exactly how the existing code recognises a missed call.

    Each event also carries ``callStatus``, taken from the Android type code
    rather than inferred from the duration. Duration alone cannot tell a call
    missed by the user from an outgoing call the other party never picked up --
    both are zero seconds -- so the distinction is preserved here and used by
    ``get_call_log_blocks``.
    """
    adapted = []
    for record in records:
        call_type = _CALL_TYPE_NAMES.get(_as_int(record.get("type")))
        if call_type is None:
            # The dataset contains a few out-of-range codes (e.g. 6503) that
            # match no documented call type; skip rather than guess.
            continue

        call_id = record.get("_id") or record.get("id")
        duration = _as_int(record.get("duration")) or 0
        timestamp = record["timestamp"]

        direction = "Incoming" if call_type in ("incoming", "missed", "rejected") else "Outgoing"
        connected_duration = 0 if call_type in ("missed", "rejected") else duration

        if call_type == "missed":
            status = "missed"
        elif call_type == "rejected":
            status = "rejected"
        elif duration == 0:
            # Connected for zero seconds: an outgoing call nobody picked up, or
            # an incoming one that never really started.
            status = "no answer"
        else:
            status = "received"

        for event_type, event_duration in (
            (direction, 0),
            ("Connected", connected_duration),
            ("Disconnected", 0 if call_type in ("missed", "rejected") else duration),
        ):
            adapted.append(
                {
                    "callId": call_id,
                    "callType": event_type,
                    "duration": event_duration,
                    "timestamp": timestamp,
                    "number": record.get("number"),
                    "callStatus": status,
                }
            )
    return adapted


def _as_int(value):
    """Best-effort int conversion; returns None when the value is unusable."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
