import sys
import os
import pytz

from data_processing.plotting_utils import plot_blocks

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

from datetime import datetime, timedelta
from data_processing.data_processing_utils import fetch_documents_between_timestamps

from data_streams.constants import IOS_ACTIVITY, time_zone_dict
import agents.generic_summarizer

functions = {
    "ACT1": {
        "name": "get_activity_records",
        "description": "Retrieves activity records for a specific user within a specified time range. Just provides what activity the user was doing at each time. For activity blocks use get_activity_blocks instead.",
        "function_call_instructions": "call this only when the time range between start_time and end_time is less than 3 hours",
        "code_generation_instructions": "Use this function to get activity records in raw data. If other functions can be used to get the data use them as they have processed data.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of activity records, where each record contains activity data. Possible activities include 'cycling', 'walking', 'running', 'automotive', 'stationary'.",
        "example": "[{'timestamp': '2024-07-19 00:04:21', 'activity': ['stationary']}, {'timestamp': '2024-07-19 00:04:41', 'activity': ['stationary']}, {'timestamp': '2024-07-19 00:05:50', 'activity': ['stationary']}]"
    },
    "ACT2": {
        "name": "get_activity_summary",
        "usecase": ["function_calling"],
        "function_call_instructions": "Use this function for qualitative/subjective requests.Only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "description": "Retrieves a summary of activity for a specific user within a given time range based on provided instructions. Use this function for special processing instructions; otherwise, use other functions if possible.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of activity records based on provided instructions."
    },
    "ACT3": {
        "name": "get_activity_blocks",
        "usecase": ["code_generation", "function_calling"],
        "description": "Retrieves contiguous blocks of different activities (walking, cycling, stationary, running, automotive) for a specific user within a specified time range, showing the start and end time of each activity block.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of activity blocks with 'activity' (type), 'start_time', and 'end_time' for each block.",
        "example": "[{'activity': 'stationary', 'start_time': '2024-07-19 00:04:21', 'end_time': '2024-07-19 15:56:16', 'duration': 57115.0}, {'activity': 'walking', 'start_time': '2024-07-19 15:56:16', 'end_time': '2024-07-19 15:57:21', 'duration': 65.0}]"
    },
    "ACT4": {
        "name": "generate_total_activity",
        "usecase": ["code_generation", "function_calling"],
        "description": "Calculates the total time spent on each activity by a user within a specified time range.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A dictionary with activities as keys and the total time spent on each in minutes as values.",
        "example": "{'stationary': 1301.5333333333326, 'walking': 96.65000000000002, 'cycling': 1.7833333333333334, 'automotive': 13.066666666666666}"
    },
    "ACT5": {
        "name": "get_activity_at_given_time",
        "usecase": ["code_generation", "function_calling"],
        "description": "Retrieves the activity record for a given user at a specific time. Use this function when query requries activities at a given time.",
        "code_generation_instructions": "Use this function  whenever you want to get activity record for a user at a specific time.",
        "params": {
            "uid": {"type": "str", "description": "The user ID for whom the activity is to be fetched."},
            "given_time": {"type": "str",
                           "description": "The specific timestamp in '%Y-%m-%d %H:%M:%S' format."}
        },
        "returns": "A dictionary containing the activity and timestamp closest to the given time.",
        "example": "{'activity': ['stationary'], 'timestamp': '2024-07-19 00:00:00'}"
    },

}


def get_activity_records(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)
    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    activity_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_ACTIVITY)
    return process_records(uid, activity_records)


def process_records(uid, activity_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in activity_records:
        d = {}
        time = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)
        d['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        d['activity'] = r['activity']
        records.append(d)
    return records


def get_activity_summary(uid, start_time, end_time, instructions):
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
        location_records = get_activity_records(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': location_records, 'summary_n_1': last_summary, 'instructions': instructions, 'type': 'location',
             'window': '5'})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination(
            {'summaries': summaries, 'instructions': instructions, 'type': 'activity', 'window': '5'})
        summary = summary['summary']

    return summary


def get_activity_blocks(uid, start_time, end_time):
    activity_records = get_activity_records(uid, start_time, end_time)
    if activity_records:
        start_activity = activity_records[0]['activity'][0]
        start_time = activity_records[0]['timestamp']
        activity_blocks = []

        for i in range(1, len(activity_records)):
            if activity_records[i]['activity'] != activity_records[i - 1]['activity']:
                end_time = activity_records[i]['timestamp']
                start_time_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
                end_time_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()
                duration = end_time_timestamp - start_time_timestamp
                activity_blocks.append(
                    {
                        "activity": start_activity,
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration
                    }
                )
                # Update for the new activity block
                start_activity = activity_records[i]['activity'][0]
                start_time = activity_records[i]['timestamp']

        # Add the last activity block
        end_time = activity_records[-1]['timestamp']

        start_time_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
        end_time_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()
        duration = end_time_timestamp - start_time_timestamp
        activity_blocks.append(
            {
                "activity": start_activity,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration
            }
        )
        return activity_blocks
    else:
        return []


def get_activity_at_given_time(uid, given_time):
    # Parse the given time
    given_time_ = datetime.strptime(given_time, "%Y-%m-%d %H:%M:%S")

    # Define the start and end time with a 5-minute range
    start_time = given_time_ - timedelta(minutes=5)
    end_time = given_time_ + timedelta(minutes=5)

    # Fetch activity records for the user within the given time window
    activity_records = get_activity_records(uid, start_time, end_time)

    # Find the closest record by comparing the time difference
    if not activity_records:
        return {}
    closest_record = min(activity_records, key=lambda record: abs(
        datetime.strptime(record['timestamp'], "%Y-%m-%d %H:%M:%S") - given_time_))

    return {'activity': closest_record['activity'], 'timestamp': given_time}


def generate_total_activity(uid, start_time, end_time):
    activity_blocks = get_activity_blocks(uid, start_time, end_time)
    total_time = {}
    for entry in activity_blocks:
        activity = entry['activity']
        start_time = entry['start_time']
        end_time = entry['end_time']

        start_time_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
        end_time_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

        duration = end_time_timestamp - start_time_timestamp

        if activity in total_time:
            total_time[activity] += duration / (60)
        else:
            total_time[activity] = duration / (60)
    return total_time


def get_activity_metrics(uid, start_time, end_time):
    activity_records = get_activity_records(uid, start_time, end_time)
    print(activity_records)
    activity_blocks = get_activity_blocks(uid, start_time, end_time)
    # plot_activity(activity_blocks)
    print(activity_blocks)
    print(generate_total_activity(uid, start_time, end_time))


def plot_activity(activity_blocks):
    plot_blocks(activity_blocks, 'Activity')


if __name__ == "__main__":
    start_datetime = "2024-07-20 14:15:48"
    end_datetime = "2023-05-19 11:11:59"

    activities = (get_activity_at_given_time('u010', end_datetime))
    print(activities)
