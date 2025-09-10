"""
Phone Steps Database - Phone step counting data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original phone_steps_data.py
from data_streams.phone_steps_data import functions

# Import all the actual function implementations from phone_steps_data.py
from data_streams.phone_steps_data import (
    get_phone_steps_stats,
    get_phone_steps_summary,
    get_phone_steps_records
)

# Database metadata for registry
database_info = {
    "name": "phone steps database",
    "info": "Contains steps walked, floors ascended, floors descended, and distance covered between two intervals, calculated via the phone.",
    "device": "Phone",
    "additional_instructions": "The phone steps database provides step count data which might overlap with garmin steps database. Mention that you are using Phone to get step count data."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_phone_steps_stats": get_phone_steps_stats,
    "get_phone_steps_summary": get_phone_steps_summary,
    "get_phone_steps_records": get_phone_steps_records
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
        import_path="\nUse following import for phone steps database functions (PHONE)\nfrom data_streams.phone_steps_data import function_name"
    )
