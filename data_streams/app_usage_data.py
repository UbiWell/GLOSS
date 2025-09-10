import math
import sys
import os
import pytz

from datetime import datetime, timedelta
from agents.coding_agent import run_coding_agent

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

import matplotlib.pyplot as plt
import agents.generic_summarizer
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.lock_unlock_data import get_lock_unlock_blocks

from data_streams.constants import APP_USAGE_LOGS, IOS_LOCK_UNLOCK, time_zone_dict

app_map = {
    "SNAP": "SnapChat",
    "IG": "Instagram",
    "TT": "TikTok",
    "IM": "iMessage",
    "SAFA": "Safari",
    "APPMU": "Apple Music",
    "CAM": "Camera",
    "CALL": "Phone Calls",
    "PHO": "Photos",
    "TWIT": "Twitter",
    "PIN": "Pinterest",
    "SPOT": "Spotify",
    "FT": "FaceTime",
    "GC": "Google Chrome",
    "CAN": "Canva",
    "GM": "Gmail",
    "YT": "YouTube",
    "PS": "Photoshop",
    "RB": "Red Book",
    "WHT": "Whatsapp"
}

functions = {
    "APP1": {
        "name": "get_app_usage_blocks",
        "usecase": ["code_generation", "function_calling"],
        "description": "Retrieves time blocks of app usage for a given user within a specified time range. Provides blocks of app usage including app name, open time, close time, and duration.",
        "function_call_instructions": "Call this function to get app usage block when difference betwen start_time and end_time is less than 24 hours",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of app usage blocks.",
        "example": "[{'app': 'SnapChat', 'open': '2024-07-15 17:38:57', 'close': '2024-07-15 18:13:32', 'duration': 2075.0}, {'app': 'SnapChat', 'open': '2024-07-15 19:07:34', 'close': '2024-07-15 19:08:12', 'duration': 38.0}]"
    },
    "APP2": {
        "name": "get_most_recent_app",
        "usecase": ["code_generation", "function_calling"],
        "description": "Gives the app usage block of the most recent app used, including app name, open time, close time, and duration.",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose app usage data is to be fetched."},
            "timestamp": {"type": "str", "description": "Most recent use before this timestamp."}
        },
        "returns": "Most recent app usage information.",
        "example": "{'app': 'SnapChat', 'open': '2024-07-15 14:27:39', 'close': '2024-07-15 14:27:49', 'duration': 10.0}"
    },

    "APP4": {
        "name": "get_app_usage_summary",
        "usecase": ["function_calling"],
        "description": "Retrieves a summary of app usage for a specific user within a given time range based on instructions provided. Use this function when special processing instructions are needed; otherwise, use other functions if possible.",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose app usage data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which app usage data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which app usage data is required."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of app usage records based on the provided instructions."
    }
}


def convert_timestamp_to_string(timestamp):
    # Convert timestamp to datetime object
    dt_object = datetime.fromtimestamp(timestamp)
    # Format datetime object as a string in the desired format
    return dt_object.strftime('%Y-%m-%d %H:%M:%S')


def process_records(uid, app_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in app_records:
        d = {}
        time = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)
        d['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        d['appName'] = app_map[r['appName']] if r['appName'] in app_map else r['appName']
        d['status'] = r['status']
        records.append(d)
    return records


def get_app_usage_records(uid, start_time, end_time, debug=False):
    start_time_orig = start_time
    end_time_orig =  end_time

    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)
    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)

        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    start_time_ = datetime.fromtimestamp(start_time, tz=pytz.UTC).astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')
    end_time_ = datetime.fromtimestamp(end_time, tz=pytz.UTC).astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')


    app_usage_records = fetch_documents_between_timestamps(uid, start_time, end_time, APP_USAGE_LOGS)


    lock_unlock_blocks = get_lock_unlock_blocks(uid, start_time_orig, end_time_orig)

    if not app_usage_records:
        return []
    if debug:
        for p in process_records(uid, app_usage_records):
            print(p)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    if not lock_unlock_blocks:
        lock_unlock_blocks = [{"start_time": start_time_, "end_time": end_time_}]

    block_index = 0

    updated_app_usage_records = []

    j = 0
    while (j < len(app_usage_records)):
        for i in range(block_index, len(lock_unlock_blocks)):
            block_start_time = timezone.localize(
                datetime.strptime(lock_unlock_blocks[i]['start_time'], "%Y-%m-%d %H:%M:%S")).astimezone(
                pytz.UTC).timestamp()
            block_end_time = timezone.localize(
                datetime.strptime(lock_unlock_blocks[i]['end_time'], "%Y-%m-%d %H:%M:%S")).astimezone(
                pytz.UTC).timestamp()

            if (app_usage_records[j]['timestamp'] > block_end_time):
                continue
            block_index = i
            break

        if (j == 0):
            if app_usage_records[j]['status'] == "close":
                record = {"appName": app_usage_records[0]["appName"], "timestamp": block_start_time, "status": "open"}
                if debug: print("Appending:", process_records(uid, [record]))
                updated_app_usage_records.append(record)
            if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
            updated_app_usage_records.append(app_usage_records[j])
            j += 1
            continue

        if (j == len(app_usage_records) - 1):
            if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
            updated_app_usage_records.append(app_usage_records[j])
            if app_usage_records[j]['status'] == "open":
                record = {"appName": app_usage_records[j]["appName"], "timestamp": block_end_time, "status": "close"}
                if debug: print("Appending:", process_records(uid,[record]))
                updated_app_usage_records.append(record)
            j += 1
            continue

        if (app_usage_records[j]['status'] == "close"):
            if j - 1 >= 0:
                if updated_app_usage_records[-1]['status'] == "open":
                    if updated_app_usage_records[-1]["appName"] == app_usage_records[j]['appName']:
                        if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
                        updated_app_usage_records.append(app_usage_records[j])
                    else:
                        previous_block_end = datetime.strptime(lock_unlock_blocks[i - 1]['end_time'],
                                                               "%Y-%m-%d %H:%M:%S").timestamp()
                        if (block_start_time > updated_app_usage_records[-1]['timestamp']):
                            update_time = previous_block_end
                        else:
                            update_time = app_usage_records[j]['timestamp']
                        record_close = {"appName": updated_app_usage_records[-1]["appName"], "timestamp": update_time,
                                        "status": "close"}

                        if debug: print("Appending:", process_records(uid, [record_close]))
                        updated_app_usage_records.append(record_close)

                        update_time = max(updated_app_usage_records[-1]['timestamp'], block_start_time)
                        record_open = {"appName": app_usage_records[j]["appName"], "timestamp": update_time,
                                       "status": "open"}
                        if debug: print("Appending:", process_records(uid, [record_open]))
                        updated_app_usage_records.append(record_open)
                        if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
                        updated_app_usage_records.append(app_usage_records[j])

                else:
                    update_time = max(updated_app_usage_records[-1]['timestamp'], block_start_time)
                    record_open = {"appName": app_usage_records[j]["appName"], "timestamp": update_time,
                                   "status": "open"}
                    if debug: print("Appending:", process_records(uid, [record_open]))
                    updated_app_usage_records.append(record_open)
                    if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
                    updated_app_usage_records.append(app_usage_records[j])

        if (app_usage_records[j]['status'] == "open"):
            if j - 1 < len(app_usage_records) and updated_app_usage_records[-1]['status'] == "close":
                if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
                updated_app_usage_records.append(app_usage_records[j])
            else:
                update_time = min(app_usage_records[j]['timestamp'], block_end_time)
                record_close = {"appName": app_usage_records[j - 1]["appName"], "timestamp": update_time,
                                "status": "close"}
                if debug: print("Appending:", process_records(uid, [record_close]))
                updated_app_usage_records.append(record_close)
                if debug: print("Appending:", process_records(uid, [app_usage_records[j]]))
                updated_app_usage_records.append(app_usage_records[j])

        if debug: print(process_records(uid, updated_app_usage_records[-4:]))
        j += 1

    # print("adding fixed records:", len(updated_app_usage_records) - len(app_usage_records))

    app_usage_records.sort(key=lambda x: x['timestamp'])

    return process_records(uid, updated_app_usage_records)


def get_app_usage_blocks(uid, start_time, end_time):
    app_usage_records = get_app_usage_records(uid, start_time, end_time)

    # for r in app_usage_records:
    #     print(r)

    if not app_usage_records:
        return []
    app_usage_blocks = []

    for i in range(1, len(app_usage_records)):
        # Convert timestamps to datetime objects
        current_timestamp = datetime.strptime(app_usage_records[i]['timestamp'], "%Y-%m-%d %H:%M:%S")
        previous_timestamp = datetime.strptime(app_usage_records[i - 1]['timestamp'], "%Y-%m-%d %H:%M:%S")

        if app_usage_records[i]['appName'] != app_usage_records[i - 1]['appName']:
            if app_usage_records[i - 1]['status'] == "open":
                app_usage_blocks.append({
                    "app": app_usage_records[i - 1]['appName'],
                    "open": app_usage_records[i - 1]['timestamp'],
                    "close": app_usage_records[i]['timestamp'],
                    "duration": (current_timestamp - previous_timestamp).total_seconds()
                })
        else:
            if (not (app_usage_records[i - 1]['status'] == "close" and app_usage_records[i]['status'] == "open")):
                app_usage_blocks.append({
                    "app": app_usage_records[i - 1]['appName'],
                    "open": app_usage_records[i - 1]['timestamp'],
                    "close": app_usage_records[i]['timestamp'],
                    "duration": (current_timestamp - previous_timestamp).total_seconds()
                })
    return app_usage_blocks


def get_total_app_usage(uid, start_time, end_time):
    app_usage_blocks = get_app_usage_blocks(uid, start_time, end_time)
    summary = {}
    for entry in app_usage_blocks:
        app = entry['app']
        duration = entry['duration']
        if app in summary:
            summary[app]['count'] += 1
            summary[app]['total_duration'] += duration
        else:
            summary[app] = {'count': 1, 'total_duration': duration}

    return summary


def get_most_recent_app(uid, timestamp):
    # Convert the timestamp string to a datetime object
    target_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    # Calculate the start time as 8 hours before the given timestamp
    start_time = (target_time - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


    # Get app usage blocks within the last 8 hours
    app_usage_blocks = get_app_usage_blocks(uid, start_time, timestamp)

    # If there are no usage blocks, return None
    if not app_usage_blocks:
        return None

    # Find the most recent app usage block before or at the given timestamp
    most_recent_block = None
    for block in app_usage_blocks:
        block_close_time = datetime.strptime(block['close'], "%Y-%m-%d %H:%M:%S")
        if block_close_time <= target_time:
            most_recent_block = block
        else:
            break

    return most_recent_block


def get_app_usage_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    summarizer = agents.generic_summarizer.GenericSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=5)
        app_usage_records = get_app_usage_blocks(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': app_usage_records, 'summary_n_1': last_summary, 'instructions': instructions,
             'type': 'app usage data', 'window': "5"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination(
            {'summaries': summaries, 'instructions': instructions, 'type': 'app usage', 'window': "5"})
        summary = summary['summary']

    return summary





import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime


def plot_app_durations(data):
    # Convert timestamps to datetime and prepare durations and app names
    times = [datetime.strptime(entry['open'], "%Y-%m-%d %H:%M:%S") for entry in data]
    durations = [entry['duration'] for entry in data]
    apps = [entry['app'] for entry in data]

    # Assign a unique color to each app
    unique_apps = set(apps)
    colors = plt.colormaps['tab10'](range(len(unique_apps)))
    app_colors = {app: colors[i] for i, app in enumerate(unique_apps)}

    # Plot each app's durations using scatter plot and draw dashed lines to x-axis
    plt.figure(figsize=(12, 6))
    for i in range(len(data)):
        plt.scatter(times[i], durations[i], color=app_colors[apps[i]], s=50,
                    label=apps[i] if i == 0 or apps[i] != apps[i - 1] else "")
        plt.vlines(times[i], 0, durations[i], color=app_colors[apps[i]], linestyles='dashed')

    # Formatting the plot
    plt.xlabel('Time')
    plt.ylabel('Duration (seconds)')
    plt.title('App Usage Duration Over Time')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.gcf().autofmt_xdate()
    plt.legend(title="Apps")
    plt.ylim(0)

    plt.show()


if __name__ == "__main__":
    start_timestamp = "2025-08-28 00:00:47"
    end_timestamp = "2025-08-28 23:59:47"

    app_usage_blocks = get_app_usage_blocks('test004', start_timestamp, end_timestamp)


    for l in (app_usage_blocks):
        print(l)

