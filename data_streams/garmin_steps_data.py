import sys
import os
import pytz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime, timedelta
import agents.generic_summarizer
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import GARMIN_STEPS, time_zone_dict
from agents.coding_agent import run_coding_agent

functions = {
    "GARMINSTEP1": {
        "name": "get_total_garmin_steps",
        "description": "Retrieves total step records for a specified user within a given time range gathered from Garmin smart watch.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period."},
            "end_time": {"type": "str", "description": "The end time of the period."}
        },
        "returns": {
            "total_steps": {"type": "int", "description": "The sum of steps recorded."}
        },
        "example": "{'total_steps': 11982.0}"
    },
    "GARMINSTEP2": {
        "name": "get_garmin_steps_records",
        "usecase": ["code_generation"],
        "description": "Retrieves a records of steps every minute for a specific user within a given time range.",
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
        "example": "[{'start_timestamp': '2024-07-20 00:01:00', 'steps_timestamp': '2024-07-20 00:02:00', 'steps': 0.0, 'total_steps': 0.0}, {'start_timestamp': '2024-07-20 00:02:00', 'steps_timestamp': '2024-07-20 00:03:00', 'steps': 0.0, 'total_steps': 0.0}]"
    },


    "GARMINSTEP4": {
        "name": "get_garmin_steps_summary",
        "usecase": ["function_calling"],
        "description": "Retrieves a summary of steps recorded using Garmin smart watch for a specific user within a given time range based on instructions provided.",
        "function_call_instructions": "only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose steps data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which steps data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which steps data is required."},
            "instructions": {"type": "str", "description": "Specific instructions for summarizing the data."}
        },
        "returns": "A summary of steps records based on the provided instructions."
    }
}


def get_garmin_steps_records(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    step_records = fetch_documents_between_timestamps(uid, start_time, end_time, GARMIN_STEPS)
    return process_records(uid, step_records)


def get_total_garmin_steps(uid, start_time, end_time):
    step_records = get_garmin_steps_records(uid, start_time, end_time)
    total_steps = 0
    for entry in step_records:
        total_steps += entry['steps']
    return {"total_steps": total_steps}


def process_records(uid, step_records):
    unique_data = {record['start_timestamp']: record for record in step_records}
    step_records = list(unique_data.values())

    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in step_records:
        d = {}
        start_time = datetime.fromtimestamp(r['start_timestamp'], pytz.utc).astimezone(timezone)
        steps_time = datetime.fromtimestamp(r['steps_timestamp'], pytz.utc).astimezone(timezone)
        d['start_timestamp'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        d['steps_timestamp'] = steps_time.strftime('%Y-%m-%d %H:%M:%S')
        d['steps'] = r['steps']
        d['total_steps'] = r['total_steps']
        records.append(d)
    return records


def get_garmin_steps_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    summarizer = agents.generic_summarizer.GenericSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=3)
        step_records = get_garmin_steps_records(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': step_records, 'summary_n_1': last_summary, 'instructions': instructions,
             'type': 'Steps taken each day calculated using garmin smart watch', 'window': "3"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination({'summaries': summaries, 'instructions': instructions,
                                                 'type': 'Steps taken each day calculated using garmin smart watch',
                                                 'window': "3"})
        summary = summary['summary']

    return summary


if __name__ == "__main__":
    step_records = get_garmin_steps_records('test004', "2024-07-20 00:00:00", "2024-07-20 2:59:59")
    print(step_records)
