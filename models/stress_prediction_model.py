# module for accessing the mongo database
from data_processing.db_config import DbConfig

# module for loading the stress detection model
from ubiwell_stress_detection.load_model import *
from ubiwell_stress_detection.calculate_features import generate_stat_features, window_walk
from ubiwell_stress_detection.preprocess import *
from data_streams.constants import time_zone_dict

from data_streams.garmin_ibi_data import get_garmin_ibi
from datetime import datetime
import pytz
import sys
import os
import numpy as np
from agents.coding_agent import run_coding_agent
import matplotlib.pyplot as plt

import pandas as pd

functions = {
    "STRESS1": {
        "name": "get_stress_predictions",
        "description": "Fetches stress predictions probabilities for a specified user and time range. Computes stress levels based on Garmin IBI records and trained model predictions.  Stress predictions are generated for 15-seconds intervals and are between 0 an 1. Closer to 1 means higher stress levels.",
        "function_call_instructions": "call this function only when the time range between start_time and end_time is less than 3 hours",
        "usecase": ["code_generation", "function_calling", "code_generation"],
        "params": {
            "uid": {
                "type": "str",
                "description": "The user ID for which the stress predictions are to be fetched."
            },
            "start_time": {
                "type": "str",
                "description": "The start time of the desired prediction range."
            },
            "end_time": {
                "type": "str",
                "description": "The end time of the desired prediction range."
            }
        },
        "returns": "A list of stress predictions between the specified timestamps for the given user.",
        "example": "[{'timestamp': '2024-07-19 17:36:22', 'stress_probability': 0.06017066289008985}, {'timestamp': '2024-07-19 17:36:37', 'stress_probability': 0.06129758735219936}]"
    },

    "STRESS3": {
        "name": "get_stress_aggregation",
        "description": "Aggregates stress predictions over a specified time range into intervals of a given granularity and calculates average stress levels and standard deviations for each interval. Stress predictions are generated for 15-seconds intervals and are between 0 an 1. Closer to 1 means higher stress levels.",
        "function_call_instructions": "Call this function when stress prediction data needs to be aggregated into specific time intervals for analysis.",
        "usecase": ["function_calling", "code_generation"],
        "params": {
            "uid": {
                "type": "str",
                "description": "The user ID for which stress predictions are to be aggregated."
            },
            "start_time": {
                "type": "str",
                "description": "The start time of the range for which stress predictions are to be aggregated."
            },
            "end_time": {
                "type": "str",
                "description": "The end time of the range for which stress predictions are to be aggregated."
            },
            "granularity": {
                "type": "int",
                "description": "The granularity in minutes to aggregate stress data. Defaults to 1 minute."
            }
        },
        "returns": {
            "aggregated_data": {
                "type": "list",
                "description": "A list of dictionaries containing aggregated stress data with time and average stress probability for each interval."
            },
            "mean_stress": {
                "type": "float",
                "description": "The overall mean stress probability across all intervals."
            },
            "std_dev_stress": {
                "type": "float",
                "description": "The standard deviation of stress probabilities across all intervals."
            }
        },
        "example": {
            "aggregated_data": [
                {"time": "2024-07-19 17:36:00", "stress_probability": 0.85},
                {"time": "2024-07-19 17:37:00", "stress_probability": 0.72}
            ],
            "mean_stress": 0.79,
            "std_dev_stress": 0.065
        }
    }
}


def process_records(uid, records):
    processed_stress_records = []
    uid_timezone = time_zone_dict.get(uid, 'est')  # Get UID-specific timezone or default to EST
    timezone = pytz.timezone("America/New_York") if uid_timezone == "est" else pytz.utc
    for record in records:
        rec = {}
        time = datetime.fromtimestamp(record['timestamp'], pytz.utc).astimezone(timezone)
        rec['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        rec['stress_probability'] = record['prob_Stress']
        processed_stress_records.append(rec)
    return processed_stress_records


def get_stress_predictions(uid, start_time, end_time):
    ibi_records = get_garmin_ibi(uid, start_time, end_time)
    if (len(ibi_records) == 0):
        return []
    df = pd.DataFrame(ibi_records)
    df['RR'] = df['bbi'] / 1000
    df = preprocess_rr_df(df, rr_column='RR', mad_threshold=3)

    feats_windowed = window_walk(df, window=60, step=15)
    feats_windowed = pd.DataFrame(feats_windowed,
                                  columns=["timestamp", "mean_rri", "std_rri", "median_rri", "max_rri", "min_rri",
                                           "per_20_rri", "per_80_rri", "rMSSD"])
    x = feats_windowed.drop(columns=['timestamp'], inplace=False).to_numpy()

    model = load()
    predictions = model.predict_proba(x)

    result = pd.DataFrame(predictions, columns=['prob_Rest', 'prob_Stress'])
    result = result.drop(columns=['prob_Rest'])
    result['timestamp'] = feats_windowed['timestamp']
    result['uid'] = uid

    return process_records(uid, result.to_dict('records'))


def get_stress_aggregation(uid, start_time, end_time, granularity=1):
    stress_records = get_stress_predictions(uid, start_time, end_time)
    if stress_records == []:
        return [], -1, -1

    # Convert granularity from minutes to seconds
    granularity_seconds = granularity * 60

    # Sort records by timestamp
    stress_records.sort(key=lambda x: x['timestamp'])

    # List to store aggregated results
    aggregated_data = []

    # Initialize variables
    interval_start = None
    interval_end = None
    interval_stress = []

    for record in stress_records:
        timestamp_ = record['timestamp']
        stress_level = record['stress_probability']

        dt_object = datetime.strptime(timestamp_, '%Y-%m-%d %H:%M:%S')
        timestamp = dt_object.timestamp()
        formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')

        if interval_start is None:
            interval_start = timestamp

        if (timestamp - interval_start) < granularity_seconds:
            # Accumulate stress level within the interval
            interval_stress.append(stress_level)
            interval_end = timestamp
        else:
            # Calculate aggregation metrics
            average_stress = round(np.mean(interval_stress), 4)
            std_dev_stress = round(np.std(interval_stress), 4)
            dt_object = datetime.fromtimestamp(interval_start)
            formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')
            # Store the aggregated data
            aggregated_data.append({
                'time': formatted_time,
                'stress_probability': average_stress,
            })

            # Reset for the next interval
            interval_start = timestamp
            interval_end = timestamp
            interval_stress = [stress_level]

    # Handle the last interval
    if interval_stress:
        average_stress = round(np.mean(interval_stress), 4)
        std_dev_stress = round(np.std(interval_stress), 4)
        dt_object = datetime.fromtimestamp(interval_start)
        formatted_time = dt_object.strftime('%Y-%m-%d %H:%M:%S')
        aggregated_data.append({
            'time': formatted_time,
            'stress_probability': average_stress,
        })

    # Calculate overall statistics
    stress_rec = [a['stress_probability'] for a in aggregated_data]
    mean_stress = round(np.mean(stress_rec), 4)
    std_dev_stress = round(np.std(stress_rec), 4)

    return {"aggregated_data": aggregated_data, "mean_stress": mean_stress, "std_dev_stress": std_dev_stress}


def get_stress_stats(uid, start_time, end_time):
    stress_records = get_stress_predictions(uid, start_time, end_time)
    stress_levels = [entry['stress_probability'] for entry in stress_records]
    return np.mean(stress_levels), np.std(stress_levels)


def count_high_stress_intervals(uid, date):
    start_time = f"{date} 00:00:00"
    end_time = f"{date} 23:59:59"

    # Fetch stress predictions for the user on the specified date
    predictions = get_stress_predictions(uid, start_time, end_time)

    # Count intervals where stress level > 0.8
    high_stress_count = sum(1 for prediction in predictions if prediction['stress_probability'] > 0.7)

    return high_stress_count


if __name__ == "__main__":
    start_datetime = "2024-07-17 13:15:00"
    end_datetime = "2024-07-17 19:15:00"

    # print(get_stress_through_data_computation("average stress prediction for test004 2024-07-20?"))
    # import matplotlib.pyplot as plt
    data = (get_stress_predictions("test004", start_datetime, end_datetime))
    print(data)
    print(count_high_stress_intervals("test004", "2024-07-20"))

    timestamps = [datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S') for entry in data]
    stress_probabilities = [entry['stress_probability'] for entry in data]

    # Plot
    plt.figure(figsize=(8, 4))
    plt.plot(timestamps, stress_probabilities, linestyle='-', label="Stress Probability")
    plt.title("Stress Probability Over Time")
    plt.xlabel("Timestamp")
    plt.ylabel("Stress Probability")
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.show()
