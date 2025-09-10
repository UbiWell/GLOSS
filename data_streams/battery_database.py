"""
Battery Database - Phone battery data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original battery_data.py
from data_streams.battery_data import functions

# Import all the actual function implementations from battery_data.py
from data_streams.battery_data import (
    get_battery_records,
    get_battery_records_all,
    get_discharging_charging_events
)

# Database metadata for registry
database_info = {
    "name": "phone battery database",
    "info": "Contains battery data, including battery left percentage and charging/discharging events.",
    "device": "Phone",
    "additional_instructions": "The battery database tracks phone battery levels and charging events. This can indicate device usage patterns and charging behavior."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_battery_records": get_battery_records,
    "get_battery_records_all": get_battery_records_all,
    "get_discharging_charging_events": get_discharging_charging_events
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
        import_path="\nUse following import for phone battery database functions (BATTERY)\nfrom data_streams.battery_data import function_name"
    )
