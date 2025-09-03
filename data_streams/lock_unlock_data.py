import sys
import os
import pytz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime, timedelta
from data_processing.data_processing_utils import fetch_documents_between_timestamps

from data_streams.constants import IOS_LOCK_UNLOCK, time_zone_dict

import agents.generic_summarizer
from agents.coding_agent import run_coding_agent

functions = {
    "UL1": {
        "name": "get_lock_unlock_blocks",
        "description": "Returns periods of consistent lock state for a user within a specified time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "int", "description": "User identifier."},
            "start_time": {"type": "string", "description": "Start of the time range"},
            "end_time": {"type": "string", "description": "End of the time range."}
        },
        "returns": "A list of dictionaries, each containing: 'state' (str) - 'locked' or 'unlocked', 'start_time' (str) - Block start time formatted as '%Y-%m-%d %H:%M:%S', and 'end_time' (str) - Block end time formatted as '%Y-%m-%d %H:%M:%S'.",
        "example": "[{'state': 'unlocked', 'start_time': '2024-07-10 00:00:00', 'end_time': '2024-07-10 00:09:42'}, {'state': 'unlocked', 'start_time': '2024-07-10 00:09:42', 'end_time': '2024-07-10 00:09:43'}, {'state': 'locked', 'start_time': '2024-07-10 00:09:43', 'end_time': '2024-07-10 00:12:22'}]"
    },
    "UL2": {
        "name": "get_total_lock_unlock_duration",
        "description": "Summarizes total time spent in each lock state for a user within a specified time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "int", "description": "User identifier."},
            "start_time": {"type": "string", "description": "Start of the time rang ."},
            "end_time": {"type": "string", "description": "End of the time range."}
        },
        "returns": "A dictionary containing total hours spent in each state: 'locked' (float) - Total hours spent locked, and 'unlocked' (float) - Total hours spent unlocked.",
        "example": "{'unlocked': 1.0733333333333337, 'locked': 10.926666666666666}"
    },
    "UL3": {
        "name": "get_lock_unlock_state_at_given_time",
        "description": "Retrieves the lock/unlock state for a given timestamp for a specific user.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose lock/unlock data is to be fetched."},
            "given_time": {"type": "str",
                           "description": "The timestamp for which lock/unlock data is required."}
        },
        "returns": "A dictionary containing the lock state at the specified timestamp and the timestamp itself.",
        "example": "{'state': 'locked', 'timestamp': '2024-07-10 00:00:00'}"
    },

    "UL5": {
        "name": "get_lock_unlock_summary",
        "usecase": ["function_calling"],
        "description": "Retrieves a summary of lock/unlock phone events for a specific user within a given time range based on instructions provided.",
        "function_call_instructions": "Use this function for qualitative/subjective requests.Only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose lock/unlock data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which lock/unlock data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which lock/unlock data is required."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of phone lock/unlock records based on the provided instructions."
    },

}

def get_lock_unlock_records(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()
    lock_unlock_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_LOCK_UNLOCK)
    return process_records(uid, lock_unlock_records)


def process_records(uid, lock_unlock_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in lock_unlock_records:
        d = {}
        time = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)
        d['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        d['lock_state'] = r['lock_state']
        records.append(d)
    return records


from datetime import datetime


def get_lock_unlock_blocks(uid, start_time, end_time):
    lock_unlock_records = get_lock_unlock_records(uid, start_time, end_time)

    if not lock_unlock_records:
        return []

    lock_unlock_blocks = []

    # Parse the start_time and end_time from string if they are provided in string format
    start_time_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    first_record_time = datetime.strptime(lock_unlock_records[0]['timestamp'], '%Y-%m-%d %H:%M:%S')

    # Initialize the first block
    lock_unlock_blocks.append({
        "state": "locked" if lock_unlock_records[0]["lock_state"] == 1 else "unlocked",
        "start_time": start_time,
        "end_time": first_record_time.strftime('%Y-%m-%d %H:%M:%S')
    })

    start_state = lock_unlock_records[0]['lock_state']
    start_time = first_record_time  # datetime object for tracking start of block

    for i in range(1, len(lock_unlock_records)):
        current_time = datetime.strptime(lock_unlock_records[i]['timestamp'], '%Y-%m-%d %H:%M:%S')

        # Check if the state has changed from the previous state
        if lock_unlock_records[i]['lock_state'] != lock_unlock_records[i - 1]['lock_state']:
            start_state_string = "locked" if start_state == 1 else "unlocked"
            formatted_start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
            formatted_end_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

            lock_unlock_blocks.append({
                "state": start_state_string,
                "start_time": formatted_start_time,
                "end_time": formatted_end_time
            })

            # Update the start time and state
            start_state = lock_unlock_records[i]['lock_state']
            start_time = current_time

    # Append the last block
    lock_unlock_blocks.append({
        "state": "locked" if start_state == 1 else "unlocked",
        "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
        "end_time": end_time
    })

    return lock_unlock_blocks


def get_lock_unlock_state_at_given_time(uid, given_time):
    given_time_ = datetime.strptime(given_time, "%Y-%m-%d %H:%M:%S")

    # Define the start and end time with a 6-hour range
    start_time = given_time_ - timedelta(hours=6)
    end_time = given_time_ + timedelta(hours=6)

    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    # Fetch lock/unlock blocks within the given time range
    blocks = get_lock_unlock_blocks(uid, start_time_str, end_time_str)

    # Iterate through the blocks and check if the given time falls within any block
    for block in blocks:

        block_start_time = datetime.strptime(block['start_time'], "%Y-%m-%d %H:%M:%S")
        block_end_time = datetime.strptime(block['end_time'], "%Y-%m-%d %H:%M:%S")

        # print(block_start_time)
        # print(block_end_time)
        # print(block['state'])
        # print("=====")

        if block_start_time <= given_time_ <= block_end_time:
            return {
                'state': block['state'],
                'timestamp': given_time
            }
    return {}


def get_total_lock_unlock_duration(uid, start_time, end_time):
    lock_unlock_blocks = get_lock_unlock_blocks(uid, start_time, end_time)

    total_time = {}
    for entry in lock_unlock_blocks:
        lock_unlock = entry['state']
        start_time = datetime.strptime(entry['start_time'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(entry['end_time'], '%Y-%m-%d %H:%M:%S')

        duration = (end_time - start_time).total_seconds()

        if lock_unlock in total_time:
            total_time[lock_unlock] += duration / (60 * 60)
        else:
            total_time[lock_unlock] = duration / (60 * 60)
    return total_time


def get_lock_unlock_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    summarizer = agents.generic_summarizer.GenericSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=5)
        lock_unlock_records = get_lock_unlock_blocks(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': lock_unlock_records, 'summary_n_1': last_summary, 'instructions': instructions,
             'type': 'Phone lock unlock time blocks', 'window': "5"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination(
            {'summaries': summaries, 'instructions': instructions, 'type': 'Phone lock unlock time blocks',
             'window': "5"})
        summary = summary['summary']

    return summary

if __name__ == "__main__":
    lock_unlock_records = get_total_lock_unlock_duration('test004', "2024-07-10 05:00:00", "2024-07-10 12:59:59")
    print(lock_unlock_records)
