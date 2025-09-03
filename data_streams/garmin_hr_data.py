import sys
import os
from datetime import datetime
import matplotlib.pyplot as plt
import pytz
import agents.heartrate_summarizer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import GARMIN_HR, time_zone_dict
import numpy as np
from datetime import datetime, timedelta
from agents.coding_agent import run_coding_agent

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

functions = {
    "GARMINHR1": {
        "name": "get_garmin_hr",
        "description": "Fetches heart rate records from Garmin for a specified user and time range. Retrieves heart rate (HR) records every 30 seconds for a given user based on the specified start and end times.",
        "function_call_instructions": "call this only when the time range between start_time and end_time is less than 3 hours",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str",
                    "description": "The user ID for which the heart rate data is to be fetched."},
            "start_time": {"type": "str", "description": "The start time of the desired data range."},
            "end_time": {"type": "str", "description": "The end time of the desired data range."}
        },
        "returns": "A list of heart rate records between the specified timestamps for the given user.",
        "example": "[{'timestamp': '2024-07-19 17:36:23', 'heart_rate': 87.0, 'uid': 'test004', 'status': 'locked'}, {'timestamp': '2024-07-19 17:36:53', 'heart_rate': 79.0, 'uid': 'test004', 'status': 'locked'}]"
    },
    "GARMINHR2": {
        "name": "get_hr_summary",
        "description": "Generates a heart rate summary for a specified user within a given time range. It summarizes hourly data based on instructions and combines the hourly summaries.",
        "function_call_instructions": "call this only when the time range between start_time and end_time is less than 24 hours",
        "usecase": [""],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier of the user."},
            "start_time": {"type": "str",
                           "description": "The start time of the period for which the heart rate summary is required, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str",
                         "description": "The end time of the period for which the heart rate summary is required, in the format '%Y-%m-%d %H:%M:%S'."},
            "instructions": {"type": "str",
                             "description": "Instructions or requests that need to be considered while generating the summary."}
        },
        "returns": "The combined heart rate summary for the specified time range based on instructions."
    },
    "GARMINHR3": {
        "name": "get_hr_stats",
        "description": "Calculates and returns the mean and standard deviation of heart rate records for a specified user within a given time range.",
        "usecase": ["code_generation", "function_calling"],
        "params": {
            "uid": {"type": "str", "description": "The unique identifier of the user."},
            "start_time": {"type": "str",
                           "description": "The start time of the period for which the heart rate statistics are required, in the format '%Y-%m-%d %H:%M:%S'."},
            "end_time": {"type": "str",
                         "description": "The end time of the period for which the heart rate statistics are required, in the format '%Y-%m-%d %H:%M:%S'."}
        },
        "returns": {
            "mean": {"type": "float", "description": "The mean of the heart rate records."},
            "std_dev": {"type": "float", "description": "The standard deviation of the heart rate records."}
        }
    },

}


def get_garmin_hr(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()
    hr_records = fetch_documents_between_timestamps(uid, start_time, end_time, GARMIN_HR)
    return process_hr_records(hr_records)


from datetime import datetime
import pytz


def process_hr_records(hr_records):
    """
    Process the heart rate records to remove any invalid values.

    Parameters:
    - hr_records (list): A list of heart rate records.

    Returns:
    - list: A list of processed heart rate records.
    """
    processed_hr_records = []
    for record in hr_records:
        if record['heart_rate'] != -99 or record['heart_rate'] != 0:
            rec = {}
            uid_timezone = time_zone_dict.get(record['uid'], 'est')  # Get UID-specific timezone or default to EST
            timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
            if record['status'] == "locked":
                time = datetime.fromtimestamp(record['timestamp'], pytz.utc).astimezone(timezone)
                rec['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
                rec['heart_rate'] = record['heart_rate']
                rec['uid'] = record['uid']
                rec['status'] = record['status']
                processed_hr_records.append(rec)
    return processed_hr_records


def get_hr_summary(uid, start_time, end_time, instructions):
    start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')

    heartrate_summarizer = agents.heartrate_summarizer.HeartRateSummarizer()

    summaries = []

    current_time = start_time
    last_summary = ""
    while current_time < end_time:
        print("summarizing for ", current_time)
        next_time = current_time + timedelta(hours=1)
        hr_records, mean, std = heart_rate_aggregation(uid, current_time.timestamp(), next_time.timestamp())
        summary = heartrate_summarizer.invoke_granular(
            {'heart_rate_values': hr_records, 'mean': mean, 'std_dev': std, 'summary_n_1': last_summary,
             'instructions': instructions})
        summary = summary['summary']
        summaries.append(summary)
        last_summary = summary
        current_time = next_time

    if (len(summaries) > 1):
        summary = heartrate_summarizer.invoke_combination({'summaries': summaries, 'instructions': instructions})
        summary = summary['summary']

    return summary


def heart_rate_aggregation(uid, start_time, end_time, granularity=1):
    hr_records = get_garmin_hr(uid, start_time, end_time)

    if (hr_records == []):
        return [], -1, -1

    # Convert granularity from minutes to seconds
    granularity_seconds = granularity * 60

    # Sort records by timestamp
    hr_records.sort(key=lambda x: x['timestamp'])

    # List to store aggregated results
    aggregated_data = []

    # Initialize variables
    interval_start = None
    interval_end = None
    interval_hrs = []

    for record in hr_records:
        timestamp_ = record['timestamp']
        heart_rate = record['heart_rate']

        dt_object = datetime.strptime(timestamp_, '%Y-%m-%d %H:%M:%S')
        timestamp = dt_object.timestamp()
        formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')

        if interval_start is None:
            interval_start = timestamp

        if (timestamp - interval_start) < granularity_seconds:
            # Accumulate heart rate within the interval
            interval_hrs.append(heart_rate)
            interval_end = timestamp
        else:
            # Calculate aggregation metrics
            average_hr = round(np.mean(interval_hrs), 2)
            std_dev_hr = round(np.std(interval_hrs), 2)
            dt_object = datetime.fromtimestamp(interval_start)
            formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            # Store the aggregated data
            aggregated_data.append({
                'time': formatted_time,
                'heart_rate': average_hr,
            })

            # Reset for the next interval
            interval_start = timestamp
            interval_end = timestamp
            interval_hrs = [heart_rate]

    # Handle the last interval
    if interval_hrs:
        average_hr = round(np.mean(interval_hrs), 2)
        std_dev_hr = round(np.std(interval_hrs), 2)
        dt_object = datetime.fromtimestamp(interval_start)
        formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')
        aggregated_data.append({
            'time': formatted_time,
            'heart_rate': average_hr,
        })

    # print(aggregated_data)
    hr_rec = [a['heart_rate'] for a in aggregated_data]
    mean_hr = round(np.mean(hr_rec), 2)
    std_dev_hr = round(np.std(hr_rec), 2)

    return aggregated_data, mean_hr, std_dev_hr


def get_hr_stats(uid, start_time, end_time):
    hr_records = get_garmin_hr(uid, start_time, end_time)
    heart_rates = [entry['heart_rate'] for entry in hr_records]
    return np.mean(heart_rates), np.std(heart_rates)


def plot_ibi(ibi_records):
    timestamps = []
    ibi_values = []
    for entry in ibi_records:
        if entry['heart_rate'] != -99:
            timestamps.append(datetime.fromtimestamp(entry['timestamp']))
            ibi_values.append(entry['heart_rate'])

    # Plotting
    plt.figure(figsize=(10, 5))
    plt.plot(timestamps, ibi_values)
    plt.xlabel('Timestamp')
    plt.ylabel('heart_rate')
    plt.title('heart_rate vs Time')
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    start_datetime = "2024-07-19 15:15:00"
    end_datetime = "2024-07-19 19:15:00"

    print(heart_rate_aggregation("test004", start_datetime, end_datetime))

    # print(get_heartrate_through_data_computation("Get anomalous (> 2 standard deviations) heart rate data for user test004 between 2024-07-19 15:15:00 and 2024-07-19 19:15:00"))

    # plot_ibi(hr_records)
