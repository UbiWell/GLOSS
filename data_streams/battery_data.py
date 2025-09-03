import sys
import os
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import IOS_BATTERY, time_zone_dict
import matplotlib.pyplot as plt
from agents.coding_agent import run_coding_agent
import pytz

functions = {
    "BATTERY1": {
        "name": "get_battery_records",
        "usecase": ["code_generation", "function_calling"],
        "function_call_instructions": "only call this function when difference between startime and endtime are less than 24 hours apart. If not use other functions like get_battery_through_data_computation",
        "description": "Retrieves records of battery percentage whenever it changes.",
        "params": {
            "uid": {"type": "str", "description": "The unique identifier for the user."},
            "start_time": {"type": "str", "description": "The start time of the period."},
            "end_time": {"type": "str", "description": "The end time of the period."}
        },
        "returns": "A dictionary containing batter left information within the specified time range.",
        "example": "[{'timestamp': '2024-07-09 12:56:54', 'battery_left': 20}, {'timestamp': '2024-07-09 12:56:54', 'battery_left': 20}, {'timestamp': '2024-07-09 13:24:34', 'battery_left': 15}]"
    },
    "BATTERY2": {
        "name": "get_discharging_charging_events",
        "usecase": ["function_calling", "code_generation"],
        "description": "Retrieves a charging and discharging events for a specific user within a given time range.",
        "params": {
            "uid": {"type": "str",
                    "description": "The unique identifier for the user whose battery data is to be fetched."},
            "start_time": {"type": "str",
                           "description": "The start of the time range for which battery data is required."},
            "end_time": {"type": "str",
                         "description": "The end of the time range for which battery data is required."},
        },
        "returns": "A list of charging discharging event within given time range.",
        "example": "[{'start_time': '2024-07-09 12:00:00', 'end_time': '2024-07-09 14:30:15', 'battery_state': 'discharging', 'duration': 150.25}, {'start_time': '2024-07-09 14:30:15', 'end_time': '2024-07-09 14:30:33', 'battery_state': 'charging', 'duration': 0.3}]"
    },

}


def process_records(uid, battery_records):
    records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for r in battery_records:
        d = {}
        timestamp = datetime.fromtimestamp(r['timestamp'], pytz.utc).astimezone(timezone)

        d['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        if ('battery_left' in r):
            d['battery_left'] = r['battery_left']
        if ('battery_state' in r):
            d['battery_state'] = r['battery_state']
        records.append(d)
    return records


def get_battery_records(uid, start_time, end_time):
    battery_records = get_battery_records_all(uid, start_time, end_time)
    return [b for b in battery_records if 'battery_left' in b]


def get_battery_records_all(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()

    battery_records = fetch_documents_between_timestamps(uid, start_time, end_time, IOS_BATTERY)
    return process_records(uid, battery_records)


def get_discharging_charging_events(uid, start_time, end_time):
    battery_records = get_battery_records_all(uid, start_time, end_time)
    charging_events = []
    prev_battery_state = -1
    for b in battery_records:
        if 'battery_state' in b:
            if (prev_battery_state != b['battery_state']):
                state = "charging" if b['battery_state'] == 1 else "discharging"
                duration = (datetime.strptime(b['timestamp'], "%Y-%m-%d %H:%M:%S").timestamp() - datetime.strptime(
                    start_time, "%Y-%m-%d %H:%M:%S").timestamp()) / 60
                charging_events.append({"start_time": start_time, "end_time": b['timestamp'], "battery_state": state,
                                        "duration": duration})
                prev_battery_state = b['battery_state']
                start_time = b['timestamp']

    state = "charging" if prev_battery_state == 2 else "discharging"
    duration = (datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").timestamp() - datetime.strptime(start_time,
                                                                                                       "%Y-%m-%d %H:%M:%S").timestamp()) / 60
    charging_events.append(
        {"start_time": start_time, "end_time": end_time, "battery_state": state, "duration": duration})
    return charging_events


def plot_battery(battery_records, charging_events):
    # Parse battery records to get battery levels and timestamps
    battery_left = []
    timestamps = []
    for entry in battery_records:
        if "battery_left" in entry:
            battery_left.append(entry['battery_left'])
            timestamps.append(datetime.fromtimestamp(entry['timestamp']))

    # Create a plot
    fig, ax = plt.subplots()

    # Plot the battery levels
    ax.plot(timestamps, battery_left, marker='o', linestyle='-', color='blue', label='Battery Level')

    # Highlight charging and discharging phases
    for event in charging_events:
        start_time = datetime.fromtimestamp(event[0])
        end_time = datetime.fromtimestamp(event[1])
        phase = event[2]

        if phase == 'charging':
            ax.axvspan(start_time, end_time, color='green', alpha=0.3,
                       label='Charging Phase' if 'Charging Phase' not in [text.get_text() for text in ax.texts] else "")
        elif phase == 'discharging':
            ax.axvspan(start_time, end_time, color='red', alpha=0.3,
                       label='Discharging Phase' if 'Discharging Phase' not in [text.get_text() for text in
                                                                                ax.texts] else "")
    # Set plot labels and legend
    ax.set_xlabel('Time')
    ax.set_ylabel('Battery Level (%)')
    ax.set_title('Battery Level Over Time')
    ax.legend()

    # Format x-axis to show readable date and time
    fig.autofmt_xdate()

    # Show plot
    plt.show()




if __name__ == "__main__":
    battery_records = (get_battery_records('test004', "2024-07-20 00:00:00", "2024-07-20 05:00:00"))
    print(battery_records)

