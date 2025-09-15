import sys
import os

from data_processing.plotting_utils import plot_blocks

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime, timedelta
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import IOS_WIFI, time_zone_dict
import agents.generic_summarizer
from agents.coding_agent import run_coding_agent
import pytz
import pandas as pd

functions = {
    "WIFI0": {

        "name": "get_wifi_records",
        "description": "Retrieves Wi-Fi connection records for a user within a specified time range.",
        "function_call_instructions": "1) You can also use this function to get wifi connection at a givent time 't' just search wifi connections around 5 minutes of t and choose closest time. 2) call this function when startime and endtime are less than 3 hours apart",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of Wi-Fi records containing timestamps and Wi-Fi name if connected.",
        "example": "[{'timestamp': '2024-07-12 00:04:20', 'wifi_name': 'FeelTheConnection'}, {'timestamp': '2024-07-12 17:29:42', 'wifi_name': 'NUwave'}, {'timestamp': '2024-07-12 17:53:43', 'wifi_name': 'not connected'}]"
    },
    "WIFI1": {
        "name": "get_wifi_blocks",
        "description": "Retrieves Wi-Fi connection blocks containing status and Wi-Fi name for a user within a specified time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of Wi-Fi blocks, each containing start and end timestamps, and Wi-Fi name if connected, or 'Not Connected' status.",
        "example": "[{wifi_name:'FeelTheConnection', start_time:'2024-07-12 00:04:20', end_time':2024-07-12 17:29:42'], {wifi_name:'not connected', start_time:'2024-07-12 17:29:42', end_time:'2024-07-12 17:53:43'}]"
    },
    "WIFI2": {
        "name": "generate_wifi_total_duration",
        "usecase": ["code_generation", "function_calling"],
        "description": "Calculates the total time spent connected to Wi-Fi or disconnected by a user within a specified time range.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start timestamp for the time range."},
            "end_time": {"type": "str", "description": "The end timestamp for the time range."}
        },
        "returns": "A list of Wi-Fi names or 'Not Connected' status along with total duration spent connected or disconnected to each Wi-Fi.",
        "example": "{'FeelTheConnection': 18.573055555555555, 'not connected': 1.8861111111111113, 'NUwave': 3.2675, 'Wi-Fi-4': 0.20083333333333334}"
    },
    "WIFI3": {
        "name": "get_wifi_usage_summary",
        "usecase": ["function_calling"],
        "description": "Retrieves a summary of Wi-Fi data for a specific user within a given time range based on provided instructions.",
        "function_call_instructions": "Use this function for qualitative/subjective requests.Only call this function when other functions can't answer the query. Do not call this function if startime and endtime are more than 24 hours apart",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose Wi-Fi data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which Wi-Fi data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which Wi-Fi data is required."},
            "instructions": {"type": "str", "description": "Instructions for summarizing the data."}
        },
        "returns": "A summary of Wi-Fi records based on the provided instructions."
    },

    "WIFI5": {
        "name": "get_wifi_at_a_time",
        "description": "This function provides wifi connection name if connected at a specific time.",
        "usecase": ["function_calling", "code_generation"],
        "function_call_instructions": "Call this function to do perform calculation and computation on wifi data.",
        "params": {
            "uid": {"type": "str",
                    "description": "user id for user"},
            "given_time": {"type": "str", "description": "The time to check in the format '%Y-%m-%d %H:%M:%S'."}
        },
        "returns": "wifi name of connected otherwise 'not connected'",
    }

}


def get_wifi_records(uid, start_time, end_time):
    # Use New York time zone if the user's timezone is "est"
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    # Convert start and end time if they are strings
    if not isinstance(start_time, float):
        if isinstance(start_time, str):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    # Fetch WiFi records
    wifi_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_WIFI)
    return process_wifi_records(uid, wifi_records)


def process_wifi_records(uid, wifi_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in wifi_records:
        if "ssid" in r:
            d = {}
            time = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)
            d['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            if pd.isna(r['ssid']):
                d['wifi_name'] = ''
            else:
                d['wifi_name'] = r['ssid']
            records.append(d)
    return records


def get_wifi_blocks(uid, start_time, end_time):
    wifi_records = get_wifi_records(uid, start_time, end_time)
    if(wifi_records == []):
        return []

    first_flag = True
    wifi_blocks = []
    for i in range(1, len(wifi_records)):
        if "wifi_name" in wifi_records[i]:
            if wifi_records[i]["wifi_name"] == "nil" or wifi_records[i]["wifi_name"] == '':
                wifi_records[i]["wifi_name"] = 'not connected'

            if first_flag == True:
                start_wifi = wifi_records[1]['wifi_name']
                start_time = wifi_records[1]['timestamp']
                last_wifi_info = i
                first_flag = False

            if wifi_records[i]['wifi_name'] != wifi_records[last_wifi_info]['wifi_name']:
                wifi_blocks.append(
                    {"wifi_name": start_wifi, "start_time": start_time, "end_time": wifi_records[i]['timestamp']})
                start_wifi = wifi_records[i]['wifi_name']
                start_time = wifi_records[i]['timestamp']
                last_wifi_info = i
    wifi_blocks.append({"wifi_name": start_wifi, "start_time": start_time, "end_time": end_time})
    return wifi_blocks


def generate_wifi_total_duration(uid, start_time, end_time):
    wifi_blocks = get_wifi_blocks(uid, start_time, end_time)
    total_time = {}
    for entry in wifi_blocks:
        wifi = entry['wifi_name']
        start_time = entry['start_time']
        end_time = entry['end_time']

        start_time_timestamp = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
        end_time_timestamp = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

        duration = end_time_timestamp - start_time_timestamp

        if wifi in total_time:
            total_time[wifi] += duration / (60 * 60)
        else:
            total_time[wifi] = duration / (60 * 60)
    return total_time


def get_wifi_usage_summary(uid, start_time, end_time, instructions):
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
        wifi_records = get_wifi_records(uid, current_time.timestamp(), next_time.timestamp())
        summary = summarizer.invoke_granular(
            {'values': wifi_records, 'summary_n_1': last_summary, 'instructions': instructions,
             'type': 'data on what wifi the phone is connected to', 'window': "3"})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = summarizer.invoke_combination({'summaries': summaries, 'instructions': instructions,
                                                 'type': 'data on what wifi the phone is connected to', "window": "3"})
        summary = summary['summary']

    return summary


def get_wifi_at_a_time(uid, given_time):
    """
    Finds the Wi-Fi connection name at a specific time.

    Args:
        records (list): A list of dictionaries containing Wi-Fi connection details.
                        Each dictionary has 'wifi_name', 'start_time', and 'end_time'.
        given_time (str): The time to check in the format '%Y-%m-%d %H:%M:%S'.

    Returns:
        str: The Wi-Fi name at the given time, or 'not connected' if no match is found.
    """
    # Convert the given time to a datetime object
    given_time = datetime.strptime(given_time, '%Y-%m-%d %H:%M:%S')
    end_datetime = given_time + timedelta(hours=5)  # Add 5 hours to convert to UTC
    start_datetime = given_time - timedelta(hours=5)  # Subtract 5 hours to convert to UTC
    start_time = start_datetime.strftime('%Y-%m-%d %H:%M:%S')
    end_time = end_datetime.strftime('%Y-%m-%d %H:%M:%S')
    records = get_wifi_blocks(uid, start_time, end_time)

    for record in records:
        # Convert start and end times to datetime objects
        start_time = datetime.strptime(record['start_time'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(record['end_time'], '%Y-%m-%d %H:%M:%S')

        # Check if the given time falls within the start and end times
        if start_time <= given_time <= end_time:
            return {"wifi": record['wifi_name']}

    # If no match is found, return 'not connected'
    return {"wifi": 'not connected'}


if __name__ == "__main__":
    start_datetime = "2024-07-09 04:34:44"
    end_datetime = "2024-07-10 16:34:44"

    wifi_records = get_wifi_records('test004', start_datetime, end_datetime)
    wifi_activity_blocks = get_wifi_blocks('test004', start_datetime, end_datetime)
    print(get_wifi_at_a_time("test004", "2024-07-09 04:34:44"))

