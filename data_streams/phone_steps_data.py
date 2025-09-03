import sys
import os
import pytz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime, timedelta
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import IOS_STEPS, time_zone_dict
from agents.generic_summarizer import GenericSummarizer
from agents.coding_agent import run_coding_agent

functions = {
    "PHONESTEP1": {
        "name": "get_phone_steps_stats",
        "usecase": ["code_generation", "function_calling"],
        "description": "Retrieves aggregated step records for a specified user within a given time range.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period."},
            "end_time": {"type": "str", "description": "The end time of the period."}
        },
        "returns": "A dictionary containing 'total_steps' (int) - the sum of steps recorded, 'total_distance' (float) - distance covered in meters, 'total_floors_ascended' (int) - floors ascended, and 'total_floors_descended' (int) - floors descended within the specified time range.",
        "example": "{'total_steps': 7967, 'total_distance': 4724.26, 'total_floors_ascended': 6.0, 'total_floor_descended': 11.0}"
    },
    "PHONESTEP2": {
        "name": "get_phone_steps_records",
        "usecase": ["code_generation"],
        "description": "Retrieves a records of steps, distance covered, floors ascended, and floors descended every minute for a specific user within a given time range.",
        "function_call_instructions": "only call this function when difference between startime and endtime are less than 5 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose steps data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which steps data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which steps data is required."},
        },
        "returns": "A list of steps records, distance covered, floors ascended, and floors descended per minute.",
        "example": "[{'start_timestamp': '2024-07-20 00:15:08', 'end_timestamp': '2024-07-20 00:15:08', 'steps': 0, 'distance': 0.0, 'floors_ascended': 0.0, 'floors_descended': 0.0}, {'start_timestamp': '2024-07-20 02:16:15', 'end_timestamp': '2024-07-20 02:16:15', 'steps': 0, 'distance': 0.0, 'floors_ascended': 0.0, 'floors_descended': 0.0}, {'start_timestamp': '2024-07-20 02:16:15', 'end_timestamp': '2024-07-20 02:55:33', 'steps': 0, 'distance': 0.0, 'floors_ascended': 0.0, 'floors_descended': 0.0}]"
    },

    "PHONESTEP4": {
        "name": "get_phone_steps_summary",
        "description": "Retrieves a summary of steps, distance covered, floors ascended, and floors descended for a specific user within a given time range based on instructions provided.",
        "function_call_instructions": "only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose steps data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which steps data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which steps data is required."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of steps records, distance covered, floors ascended, and floors descended based on the provided instructions."
    }
}


def get_phone_steps_records(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    steps_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_STEPS)
    return process_records(uid, steps_records)


def process_records(uid, step_records):
    unique_data = {record['start_timestamp']: record for record in step_records}
    step_records = list(unique_data.values())
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in step_records:
        d = {}
        prev = r
        start_time = datetime.fromtimestamp(r['start_timestamp'], pytz.utc).astimezone(timezone)
        end_time = datetime.fromtimestamp(r['end_timestamp'], pytz.utc).astimezone(timezone)

        d['start_timestamp'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        d['end_timestamp'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
        d['steps'] = r['steps']
        d['distance'] = r['distance']
        d['floors_ascended'] = r['floors_ascended']
        d['floors_descended'] = r['floors_descended']
        records.append(d)
    return records


def get_phone_steps_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    summarizer = GenericSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=3)
        location_records = get_phone_steps_records(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': location_records, 'summary_n_1': last_summary, 'instructions': instructions,
             'type': 'Steps taken each day calculated using phone', 'window': "3"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination({'summaries': summaries, 'instructions': instructions,
                                                 'type': 'Steps taken each day calculated using phone', 'window': "3"})
        summary = summary['summary']

    return summary


def get_phone_steps_stats(uid, start_time, end_time):
    steps_records = get_phone_steps_records(uid, start_time, end_time)

    total_steps = 0
    total_distance = 0
    total_floors_ascended = 0
    total_floor_descended = 0

    for record in steps_records:
        total_steps += record['steps']
        total_distance += record['distance']
        total_floors_ascended += record['floors_ascended']
        total_floor_descended += record['floors_descended']

    return {"total_steps": total_steps, "total_distance": total_distance,
            "total_floors_ascended": total_floors_ascended, "total_floor_descended": total_floor_descended}


if __name__ == "__main__":
    steps_records = get_phone_steps_records('test004', "2024-07-20 23:00:00", "2024-07-20 23:59:59")
    print(steps_records)
