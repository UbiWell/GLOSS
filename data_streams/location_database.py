"""
Location Database - GPS location data from phone sensors
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original location_data.py
from data_streams.location_data import functions

# Import all the actual function implementations from location_data.py
from data_streams.location_data import (
    get_location_records,
    get_location_statistical_metrics,
    get_location_paths,
    get_address_from_coordinates,
    get_location_summary,
    get_location_at_given_time,
    get_total_run_time,
    get_time_spent_at_home,
    get_time_spent_at_location,
    get_address,
)

# Database metadata for registry
database_info = {
    "name": "location database",
    "info": "Contains GPS location data (latitude, longitude, altitude) recorded via the phone.",
    "device": "Phone",
    "additional_instructions": "The location database can be used to detect activity related to the location, such as home, work, entertainment, etc. It can also detect speed to identify activity like riding train, bus, cycling, ... The location database provides functions to calculate physical address but only call it when needed as it is computationally expensive. Do all calculation in latitude and longitude values and call this function only when you need to show the address to the user."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_location_records": get_location_records,
    "get_location_statistical_metrics": get_location_statistical_metrics,
    "get_location_paths": get_location_paths,
    "get_address_from_coordinates": get_address_from_coordinates,
    "get_location_summary": get_location_summary,
    "get_location_at_given_time": get_location_at_given_time,
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
        import_path="\nUse following import for location database functions (LOC)\nfrom data_streams.location_data import function_name"
    )
