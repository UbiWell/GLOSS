"""
Sensing Database - daily passive sensing feature aggregates
Follows the database registry system used by the other data streams.
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original sensing_data.py
from data_streams.sensing_data import functions

# Import all the actual function implementations from sensing_data.py
from data_streams.sensing_data import (
    list_sensing_features,
    find_sensing_feature,
    get_sensing_daily,
    get_sensing_by_epoch,
    get_sensing_hourly
)

# Database metadata for registry
database_info = {
    "name": "sensing database",
    "info": "Contains daily passive sensing feature aggregates covering physical activity, ambient audio and conversation, calls, screen and app use, and related signals. Each feature is available as a daily total, split into three time-of-day epochs, and broken down by hour.",
    "device": "Phone",
    "additional_instructions": "This database is aggregated per day, not per event, so it cannot answer questions needing a precise moment; the finest granularity is one hour. Call find_sensing_feature first to turn the question into the correct feature name, and use the name it ranks highest; list_sensing_features is for browsing everything. Do not pick a feature by substring-matching names or descriptions, because features for the same place or sensor share wording and the first match is usually the wrong measure. Epochs are 00:00-09:00, 09:00-18:00 and 18:00-24:00; the whole_day value is the daily total rather than a fourth epoch, so never add it to the epochs. Units differ by feature family: act_* and audio_* durations are in SECONDS, while the daily-only loc_*_dur place features are in HOURS, so never sum or compare the two without converting. A value of None means the sensor reported nothing for that day or hour, which is not the same as zero."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "list_sensing_features": list_sensing_features,
    "find_sensing_feature": find_sensing_feature,
    "get_sensing_daily": get_sensing_daily,
    "get_sensing_by_epoch": get_sensing_by_epoch,
    "get_sensing_hourly": get_sensing_hourly
}


# Optional: Custom registration function
def register_database(registry):
    """Register this database with the registry"""
    from agents.database_registry import DatabaseRegistry
    registry.register_database(
        name=database_info["name"],
        info=database_info["info"],
        device=database_info["device"],
        additional_instructions=database_info["additional_instructions"],
        functions=functions,  # Function metadata/definitions for LLMs
        function_refs=function_refs,  # Actual function references
        import_path="\nUse following import for sensing database functions (SENSE)\nfrom data_streams.sensing_data import function_name"
    )
