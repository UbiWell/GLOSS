"""
Utility functions for processing time-series data and generating narratives for RAG based Agent.
"""
from data_streams.activity_data import get_activity_records
from data_streams.battery_data import get_battery_records
from data_streams.call_log import get_call_log_blocks
from data_streams.wifi_data import get_wifi_blocks
from data_streams.lock_unlock_data import get_lock_unlock_records
from data_streams.phone_steps_data import get_phone_steps_records
from data_streams.location_data import get_location_records
from data_streams.garmin_steps_data import get_garmin_steps_records
from data_streams.garmin_hr_data import get_garmin_hr
from data_streams.app_usage_data import get_app_usage_blocks
from models.stress_prediction_model import get_stress_predictions
import re
from datetime import datetime


def process_time_series_data(data, label, interval):
    if not data:
        return [], []

    # Sort the data by timestamp to ensure order (if not already sorted)
    for d in data:
        d['timestamp'] = datetime.strptime(d['timestamp'], '%Y-%m-%d %H:%M:%S').timestamp()

    data.sort(key=lambda x: x['timestamp'])

    regular_intervals = []
    irregular_data = []

    # Initialize tracking variables
    current_group = None
    last_timestamp = None

    for item in data:
        if current_group is None:
            # Start a new group
            current_group = {
                'start_timestamp': item['timestamp'],
                'end_timestamp': item['timestamp'],
                label: [item[label]]
            }
            last_timestamp = item['timestamp']
        else:
            # Check if the current item is 30 seconds from the last one
            if (item['timestamp'] - last_timestamp) == interval:
                current_group['end_timestamp'] = item['timestamp']
                current_group[label].append(item[label])
                last_timestamp = item['timestamp']
            else:
                # Save the current group if it has more than one element
                if len(current_group[label]) > 1:
                    regular_intervals.append(current_group)
                else:
                    irregular_data.append({
                        'timestamp': current_group['start_timestamp'],
                        label: current_group[label][0]
                    })

                # Start a new group with the current item
                current_group = {
                    'start_timestamp': item['timestamp'],
                    'end_timestamp': item['timestamp'],
                    label: [item[label]]
                }
                last_timestamp = item['timestamp']

    # Final group check
    if current_group and len(current_group[label]) > 1:
        regular_intervals.append(current_group)
    elif current_group:
        irregular_data.append({
            'timestamp': current_group['start_timestamp'],
            label: current_group[label][0]
        })
    return regular_intervals, irregular_data


def timestamp_to_datetime(timestamp):
    # Convert Unix timestamp to datetime object
    local_datetime = datetime.fromtimestamp(timestamp)

    # Convert datetime object to a readable string
    readable_datetime = local_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return readable_datetime


def count_tokens(text):
    return len(re.findall(r'\b\w+\b|\S', text))


def convert_to_timestamp(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').timestamp()


def get_data_to_narrative(user_id, start_timestamp, end_timestamp, databases):
    event_with_timestamp = []

    if "activity database" in databases:
        activity_data = get_activity_records(user_id, start_timestamp, end_timestamp)
        for event in activity_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                         'event': f"The phone sensors recognized that the {user_id} is {' and '.join(event['activity'])} at {event['timestamp']}"})

    if "phone battery database" in databases:
        battery_data = get_battery_records(user_id, start_timestamp, end_timestamp)
        for event in battery_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                         'event': f"The battery left of the {user_id}'s phone is {float(event['battery_left'])}% at {event['timestamp']}."})

    if "call log database" in databases:
        call_log_data = get_call_log_blocks(user_id, start_timestamp, end_timestamp)
        for event in call_log_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['call_time']),
                                         'event': f"The {user_id} made a {event['call_type']} call for {event['call_duration']} seconds at {event['call_time']}."})

    if "wifi database" in databases:
        wifi_data = get_wifi_blocks(user_id, start_timestamp, end_timestamp)
        for event in wifi_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['start_time']),
                                         'event': f"The {user_id}'s phone is connected to a wifi named {event['wifi_name']} from {event['start_time']} to {event['end_time']}."})

    if "lock unlock database" in databases:
        phone_lock_unlock_data = get_lock_unlock_records(user_id, start_timestamp, end_timestamp)
        for event in phone_lock_unlock_data:
            if event['lock_state'] == 1:
                event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                             'event': f"The {user_id} locked their phone at {event['timestamp']}."})
            if event['lock_state'] == 0:
                event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                             'event': f"The {user_id} unlocked their phone at {event['timestamp']}."})

    if "phone steps database" in databases:
        phone_steps_data = get_phone_steps_records(user_id, start_timestamp, end_timestamp)
        for event in phone_steps_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['start_timestamp']),
                                         'event': f"The {user_id} walked {event['steps']} steps, covered a distance of {event['distance']}m, climbed {event['floors_ascended']} floors, descended {event['floors_descended']} floors between {event['start_timestamp']} and {event['end_timestamp']}."})

    if "location database" in databases:
        location_data = get_location_records(user_id, start_timestamp, end_timestamp)
        for event in location_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                         'event': f"The {user_id} was at latitude {event['latitude']}, longitude {event['longitude']} at {event['timestamp']}."})

    if "garmin steps database" in databases:
        garmin_steps = get_garmin_steps_records(user_id, start_timestamp, end_timestamp)
        for event in garmin_steps:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['start_timestamp']),
                                         'event': f"The {user_id} walked {event['steps']} steps between {event['start_timestamp']} and {event['steps_timestamp']}."})

    if "garmin hr database" in databases:
        garmin_hr_data = get_garmin_hr(user_id, start_timestamp, end_timestamp)
        hr = []
        for event in garmin_hr_data:
            if 'heart_rate' in event.keys():
                if float(event['heart_rate']) != -99 and float(event['heart_rate']) != 0:
                    hr.append(event)
        regular, irregular = process_time_series_data(hr, 'heart_rate', 30)
        if regular:
            for dict in regular:
                event_with_timestamp.append({'timestamp': dict['start_timestamp'],
                                             'event': f"The {user_id}'s heartrate from {timestamp_to_datetime(float(dict['start_timestamp']))} to {timestamp_to_datetime(float(dict['end_timestamp']))} (30 seconds interval) is {dict['heart_rate']}."})
        if irregular:
            for dict in irregular:
                event_with_timestamp.append({'timestamp': dict['timestamp'],
                                             'event': f"The {user_id}'s heartrate is {dict['heart_rate']} at {timestamp_to_datetime(float(dict['timestamp']))}. "})

    if "garmin stress database" in databases:
        stress_data = get_stress_predictions(user_id, start_timestamp, end_timestamp)
        for event in stress_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['timestamp']),
                                         'event': f"The {user_id} is stressed with probability {event['stress_probability']} at {event['timestamp']}."})
    if "app usage database" in databases:
        app_usage_data = get_app_usage_blocks(user_id, start_timestamp, end_timestamp)
        for event in app_usage_data:
            event_with_timestamp.append({'timestamp': convert_to_timestamp(event['open']),
                                         'event': f"The {user_id} used {event['app']} for {event['duration']} seconds between {event['open']} and {event['close']}."})

    sorted_list = sorted(event_with_timestamp, key=lambda x: x['timestamp'])
    final_data = ""
    for event in sorted_list:
        final_data = final_data + event['event'] + "\n"

    print("tokens:")
    print(count_tokens(final_data))
    if final_data == "":
        return "No data found"
    return final_data
