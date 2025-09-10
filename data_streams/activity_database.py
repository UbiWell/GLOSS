"""
Activity Database - Phone activity detection data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original activity_data.py
from data_streams.activity_data import functions

# Import all the actual function implementations from activity_data.py
from data_streams.activity_data import (
    get_activity_records,
    get_activity_summary,
    get_activity_blocks,
    generate_total_activity,
    get_activity_at_given_time,
    get_activity_metrics
)

# Database metadata for registry
database_info = {
    "name": "activity database",
    "info": "Contains activity data (e.g., 'stationary,' 'automotive,' 'cycling,' 'walking,' 'running') recorded via accelerometer and gyroscope sensors in the phone. If the phone is not carried, the user is assumed inactive.",
    "device": "Phone",
    "additional_instructions": "The activity database provides detailed information about user activities detected through phone sensors. Activities include stationary, walking, running, cycling, and automotive. This data can be used to understand user movement patterns and daily activities."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_activity_records": get_activity_records,
    "get_activity_summary": get_activity_summary,
    "get_activity_blocks": get_activity_blocks,
    "generate_total_activity": generate_total_activity,
    "get_activity_at_given_time": get_activity_at_given_time,
    "get_activity_metrics": get_activity_metrics
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
        import_path="\nUse following import for activity database functions (ACT)\nfrom data_streams.activity_data import function_name"
    )
