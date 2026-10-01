import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import SMS_LOG, time_zone_dict
import pytz

# Message type codes as recorded by the study app.
MSG_TYPE_INCOMING = 1
MSG_TYPE_OUTGOING = 2
MSG_TYPE_MISSED = 3

_MSG_TYPE_NAMES = {
    MSG_TYPE_INCOMING: "incoming",
    MSG_TYPE_OUTGOING: "outgoing",
    MSG_TYPE_MISSED: "missed",
}

functions = {
    "SMS1": {
        "name": "get_sms_records",
        "usecase": ["function_calling", "code_generation"],
        "description": "Retrieves text message records for a user within a specified time range. Message contents are not stored; only metadata such as length, direction and an anonymized contact.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end time of the period, in the format '%Y-%m-%d %H:%M:%S'."}
        },
        "returns": {
            'message_time': {"type": "str", "description": "local time the message was sent or received"},
            'message_type': {"type": "str", "description": "incoming, outgoing or missed"},
            'body_length': {"type": "int", "description": "number of characters in the message"},
            'is_read': {"type": "bool", "description": "whether the message has been read"},
            'contact': {"type": "str", "description": "anonymized phone number of the other party"}
        },
        "example": "[{'message_time': '2020-11-02 09:14:03', 'message_type': 'incoming', 'body_length': 43, 'is_read': True, 'contact': 'f75c2b422899769c01ac678dad1fb6e354b3b86c'}]"
    },
    "SMS2": {
        "name": "get_sms_stats",
        "usecase": ["function_calling", "code_generation"],
        "description": "Calculates messaging statistics such as the number of messages sent and received, how many characters were exchanged, how many distinct contacts were messaged, and how many incoming messages went unread.",
        "params": {
            "uid": {"type": "str", "description": "The user ID for whom messaging statistics are calculated."},
            "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."}
        },
        "returns": "A dictionary of aggregated messaging statistics. Character counts refer to message length, not content.",
        "example": {
            "total_messages": 12,
            "total_messages_incoming": 7,
            "total_messages_outgoing": 5,
            "total_characters": 631,
            "total_characters_incoming": 402,
            "total_characters_outgoing": 229,
            "unique_contacts": 3,
            "unread_incoming": 1
        }
    },
    "SMS3": {
        "name": "get_sms_contact_breakdown",
        "usecase": ["function_calling", "code_generation"],
        "description": "Breaks messaging down per anonymized contact, so the most-messaged contacts over a period can be identified.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."}
        },
        "returns": "A list of per-contact message counts and character totals, ordered by total messages descending.",
        "example": "[{'contact': 'f75c2b42...', 'total_messages': 8, 'messages_incoming': 5, 'messages_outgoing': 3, 'total_characters': 402}]"
    },

    # ---------------------------------------------------------------------
    # TUTORIAL DEMO: UNCOMMENT TO GIVE THE AGENT THE CONVERSATION HELPER
    #
    # get_sms_conversation_blocks() below is written and working. It is left
    # out of this dictionary on purpose, and this dictionary is the whole of
    # what the model knows: a function missing from it does not exist as far
    # as the agent is concerned, so asked to count conversations it writes its
    # own grouping code and invents a gap threshold. Different runs invent
    # different thresholds and report different numbers.
    #
    # Uncommenting this entry, and the matching one in sms_database.py, is all
    # it takes for the agent to call the helper instead and for everyone to
    # get the same answer.
    # ---------------------------------------------------------------------

    # "SMS4": {
    #     "name": "get_sms_conversation_blocks",
    #     "usecase": ["function_calling", "code_generation"],
    #     "description": "Groups text messages into conversations: runs of messages with the same contact where consecutive messages are no more than gap_minutes apart. Use this for any question about conversations, exchanges or back-and-forths, rather than grouping messages by hand -- the gap that separates two conversations is a judgement call, and this function fixes it so the same question always gives the same answer.",
    #     "params": {
    #         "uid": {"type": "str", "description": "The unique identifier for the user."},
    #         "start_time": {"type": "str", "description": "The start of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
    #         "end_time": {"type": "str", "description": "The end of the time range, in the format '%Y-%m-%d %H:%M:%S'."},
    #         "gap_minutes": {"type": "int", "description": "Silence that ends a conversation, in minutes. Optional; leave it out to use the documented default of 30 minutes, which is what makes repeated runs agree. Pass a value only when the question explicitly asks for a different threshold."}
    #     },
    #     "returns": "A list of conversations ordered by start time, each with the contact, start and end time, duration in minutes, message counts by direction, and the gap_minutes used. The number of conversations is the length of this list.",
    #     "example": "[{'contact': 'f75c2b42...', 'start_time': '2019-10-06 09:14:02', 'end_time': '2019-10-06 09:41:55', 'duration_minutes': 27.9, 'total_messages': 6, 'messages_outgoing': 2, 'messages_incoming': 4, 'gap_minutes': 30}]"
    # },
}


def _to_epoch(uid, start_time, end_time):
    """Normalise the standard '%Y-%m-%d %H:%M:%S' local strings to epoch seconds."""
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if not isinstance(start_time, float):
        if isinstance(start_time, str):
            start_time = timezone.localize(
                datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(
                datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()
    return start_time, end_time, timezone


def get_sms_records(uid, start_time, end_time):
    """Return text message metadata for the user over the time range."""
    start_time, end_time, timezone = _to_epoch(uid, start_time, end_time)
    raw_records = fetch_documents_between_timestamps(uid, start_time, end_time, SMS_LOG)

    records = []
    for record in raw_records:
        message_type = _MSG_TYPE_NAMES.get(_as_int(record.get("msg_type")))
        if message_type is None:
            # Undocumented type code; skip rather than guess its direction.
            continue
        local_time = datetime.fromtimestamp(record["timestamp"], pytz.utc).astimezone(timezone)
        records.append({
            "message_time": local_time.strftime("%Y-%m-%d %H:%M:%S"),
            "message_type": message_type,
            "body_length": _as_int(record.get("body_len")) or 0,
            "is_read": _as_int(record.get("is_read")) == 1,
            "contact": record.get("number"),
        })
    return records


def get_sms_stats(uid, start_time, end_time):
    """Aggregate messaging statistics over the time range."""
    records = get_sms_records(uid, start_time, end_time)

    stats = {
        "total_messages": len(records),
        "total_messages_incoming": 0,
        "total_messages_outgoing": 0,
        "total_characters": 0,
        "total_characters_incoming": 0,
        "total_characters_outgoing": 0,
        "unique_contacts": len({r["contact"] for r in records if r["contact"]}),
        "unread_incoming": 0,
    }

    for record in records:
        length = record["body_length"]
        stats["total_characters"] += length
        if record["message_type"] == "outgoing":
            stats["total_messages_outgoing"] += 1
            stats["total_characters_outgoing"] += length
        else:
            # Incoming and missed are both inbound.
            stats["total_messages_incoming"] += 1
            stats["total_characters_incoming"] += length
            if not record["is_read"]:
                stats["unread_incoming"] += 1

    return stats


def get_sms_contact_breakdown(uid, start_time, end_time):
    """Per-contact messaging totals, most-messaged first."""
    records = get_sms_records(uid, start_time, end_time)

    by_contact = {}
    for record in records:
        contact = record["contact"]
        entry = by_contact.setdefault(contact, {
            "contact": contact,
            "total_messages": 0,
            "messages_incoming": 0,
            "messages_outgoing": 0,
            "total_characters": 0,
        })
        entry["total_messages"] += 1
        entry["total_characters"] += record["body_length"]
        if record["message_type"] == "outgoing":
            entry["messages_outgoing"] += 1
        else:
            entry["messages_incoming"] += 1

    return sorted(by_contact.values(), key=lambda e: e["total_messages"], reverse=True)


# Default gap between messages that starts a new conversation. There is no
# principled value here -- 30 minutes is a convention, not a fact, and the
# count moves a lot with it (on 2019-10-06: 33 conversations at 5 minutes, 22
# at 30, 14 at 120). The point of putting it in a function is not that 30 is
# right, but that everyone asking the same question gets the same answer, and
# the choice is written down where it can be argued with.
DEFAULT_CONVERSATION_GAP_MINUTES = 30


def get_sms_conversation_blocks(uid, start_time, end_time,
                                gap_minutes=DEFAULT_CONVERSATION_GAP_MINUTES):
    """Group messages into conversations, one entry per back-and-forth.

    A conversation is messages with the same contact where consecutive
    messages are no more than ``gap_minutes`` apart. A longer silence ends it,
    and the next message starts a new one.
    """
    records = get_sms_records(uid, start_time, end_time)
    gap_seconds = gap_minutes * 60

    by_contact = {}
    for record in records:
        moment = datetime.strptime(record["message_time"], "%Y-%m-%d %H:%M:%S")
        by_contact.setdefault(record["contact"], []).append((moment, record))

    conversations = []
    for contact, entries in by_contact.items():
        entries.sort(key=lambda e: e[0])
        current = []
        for moment, record in entries:
            if current and (moment - current[-1][0]).total_seconds() > gap_seconds:
                conversations.append(_conversation(contact, current, gap_minutes))
                current = []
            current.append((moment, record))
        if current:
            conversations.append(_conversation(contact, current, gap_minutes))

    return sorted(conversations, key=lambda c: c["start_time"])


def _conversation(contact, entries, gap_minutes):
    """One conversation block from its messages."""
    records = [record for _, record in entries]
    outgoing = sum(1 for r in records if r["message_type"] == "outgoing")
    return {
        "contact": contact,
        "start_time": entries[0][0].strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": entries[-1][0].strftime("%Y-%m-%d %H:%M:%S"),
        "duration_minutes": round((entries[-1][0] - entries[0][0]).total_seconds() / 60, 1),
        "total_messages": len(records),
        "messages_outgoing": outgoing,
        "messages_incoming": len(records) - outgoing,
        "gap_minutes": gap_minutes,
    }


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    print(get_sms_stats("user1",
                        "2020-11-02 00:00:00", "2020-11-02 23:59:59"))
