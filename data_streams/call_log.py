import sys
import os

from data_processing.plotting_utils import plot_blocks

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import IOS_CALLLOG, time_zone_dict
from agents.coding_agent import run_coding_agent
import pytz

functions = {
    "CALLLOG1": {
        "name": "get_call_log_records",
        "usecase": [],
        "function_call_instructions": "only call this function when difference between startime and endtime are less than 5 hours apart",
        "description": "Retrieves records of call logs for a user within a specified time range.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period."},
            "end_time": {"type": "str", "description": "The end time of the period."}
        },
        "returns": "A list of call log records with timestamps and call details for the specified time range.",
    },
    "CALLLOG2": {
        "name": "get_call_log_blocks",
        "usecase": ["function_calling", "code_generation"],
        "description": "return information about different calls including phone ringing and call duration (in seconds).",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period."},
            "end_time": {"type": "str", "description": "The end time of the period."}
        },
        "returns": {
            'call_id': {"type": "str", "description": "call id for the call"},
            'call_type': {"type": "str", "description": "incoming or outgoing"},
            'call_time': {"type": "str", "description": "time of the call"},
            'call_duration': {"type": "float", "description": "duration of the call"},
            'phone_ringing_duration': {"type": "float", "description": "duration of the phone ringing"},
            'call_status': {"type": "str", "description": "missed or received"}
        },
        "example": "[{'call_id': 'C23D6FFC-FB6D-4933-9E3E-4340B1C6D7C0', 'call_type': 'outgoing', 'call_time': '2024-07-09 00:11:55', 'call_duration': 2144.0, 'phone_ringing_duration': 22.0, 'call_status': 'received'}]"
    },
    "CALLLOG3": {
        "name": "get_call_log_stats",
        "usecase": ["code_generation", "function_calling"],
        "description": "Calculates call statistics such as total call time (in seconds), incoming and outgoing call counts, etc., based on user ID and time range.",
        "params": {
            "uid": {"type": "str", "description": "The user ID for whom call statistics are calculated."},
            "start_time": {"type": "str",
                           "description": "The start of the time range in which to calculate call statistics (e.g., 'YYYY-MM-DD HH:MM:SS')."},
            "end_time": {"type": "str",
                         "description": "The end of the time range in which to calculate call statistics (e.g., 'YYYY-MM-DD HH:MM:SS')."}
        },
        "returns": "A dictionary of aggregated call statistics including total time, incoming and outgoing call counts, and missed calls. All time duration is in seconds.",
        "example": {
            "total_time": 480,
            "total_time_incoming": 180,
            "total_time_outgoing": 300,
            "total_calls": 2,
            "total_calls_incoming": 1,
            "total_calls_outgoing": 1
        }
    },

}

def get_call_log_records(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    call_log_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_CALLLOG)

    return call_log_records


def get_call_log_blocks(uid, start_time, end_time):
    call_log_records = get_call_log_records(uid, start_time, end_time)
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc

    calls = {}
    for call in call_log_records:
        call_id = call['callId']
        call_type = call['callType']
        call_duration = call['duration']
        call_timestamp = call['timestamp']

        call_timestamp = datetime.fromtimestamp(call_timestamp, pytz.utc).astimezone(timezone).strftime(
            '%Y-%m-%d %H:%M:%S')

        if call_id in calls:
            calls[call_id][call_type] = {"timestamp": call_timestamp, "duration": call_duration}
        else:
            calls[call_id] = {}
            calls[call_id][call_type] = {"timestamp": call_timestamp, "duration": call_duration}

    call_logs = []
    for call in calls:

        d = {}
        d['call_id'] = call

        if('Incoming' in calls[call]):
            d['call_type'] = "incoming"
        else:
            d['call_type'] = "outgoing"

        if('Connected' in calls[call] and 'Disconnected' in calls[call]):
            d['call_time'] = calls[call]['Connected']['timestamp']
            d['call_duration'] = calls[call]['Disconnected']['duration']
            d['phone_ringing_duration'] = calls[call]['Connected']['duration']
            d['call_status'] = "missed" if calls[call]['Disconnected']['duration'] == 0 else "received"

            call_logs.append(d)
    return call_logs


def get_call_log_stats(uid, start_time, end_time):
    call_log_blocks = get_call_log_blocks(uid, start_time, end_time)
    total_time = 0
    total_time_incoming = 0
    total_time_outgoing = 0
    total_calls = len(call_log_blocks)
    total_calls_incoming = 0
    total_calls_outgoing = 0

    for call in call_log_blocks:
        total_time += call['call_duration']

        if call['call_type']  == "outgoing":
            total_calls_outgoing += 1
            total_time_outgoing += call['call_duration']
        else:
            total_calls_incoming += 1
            total_time_incoming += call['call_duration']

    return {"total_time": total_time, "total_time_incoming": total_time_incoming,
            "total_time_outgoing": total_time_outgoing, "total_calls": total_calls,
            "total_calls_incoming": total_calls_incoming, "total_calls_outgoing": total_calls_outgoing}


if __name__ == "__main__":
    call_log_records = get_call_log_blocks("test007", "2024-07-09 00:00:00", "2024-07-15 00:00:00")
    print(call_log_records)
    # print(get_call_logs_through_data_computation("total number of outgoing calls on 2024-07-09 for test004 before noon"))
