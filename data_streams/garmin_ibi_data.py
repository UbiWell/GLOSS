import sys
import os
from datetime import datetime
import matplotlib.pyplot as plt
import pytz
import agents.heartrate_summarizer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import GARMIN_IBI, time_zone_dict
import numpy as np
from datetime import datetime, timedelta
from agents.coding_agent import run_coding_agent

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

def get_garmin_ibi(uid, start_time, end_time):
    user_timezone = time_zone_dict.get(uid, "est")
    timezone = pytz.timezone("America/New_York") if user_timezone == "est" else pytz.timezone(user_timezone)

    if (not isinstance(start_time, float)):
        if (isinstance(start_time, str)):
            start_time = timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
            end_time = timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")).astimezone(pytz.UTC)
        start_time = start_time.timestamp()
        end_time = end_time.timestamp()
    ibi_records = fetch_documents_between_timestamps(uid, start_time, end_time, GARMIN_IBI)
    return ibi_records


if __name__ == "__main__":
    start_datetime = "2024-07-19 15:15:00"
    end_datetime = "2024-07-19 19:15:00"

    print(get_garmin_ibi("test004", start_datetime, end_datetime))