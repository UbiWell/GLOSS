"""
Garmin Heart Rate Database - Garmin watch heart rate data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original garmin_hr_data.py
from data_streams.garmin_hr_data import functions

# Import all the actual function implementations from garmin_hr_data.py
from data_streams.garmin_hr_data import (
    get_garmin_hr,
    get_hr_summary,
    get_hr_stats
)

# Database metadata for registry
database_info = {
    "name": "garmin hr database",
    "info": "Contains heart rate data (per 30 seconds) and functions for summarizing heart rate data recorded from the Garmin smartwatch.",
    "device": "Garmin Smartwatch",
    "additional_instructions": "The garmin heart rate database provides detailed heart rate measurements every 30 seconds. This data can be used to understand user physiological responses and activity levels."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_garmin_hr": get_garmin_hr,
    "get_hr_stats": get_hr_stats
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
        import_path="\nUse following import for garmin hr database functions (GARMINHR)\nfrom data_streams.garmin_hr_data import function_name"
    )
