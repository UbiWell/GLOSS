"""
App Usage Database - Phone app usage data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original app_usage_data.py
from data_streams.app_usage_data import functions

# Import all the actual function implementations from app_usage_data.py
from data_streams.app_usage_data import (
    get_app_usage_blocks,
    get_most_recent_app,
    get_app_usage_summary,
    get_app_usage_records,
    get_total_app_usage
)

# Database metadata for registry
database_info = {
    "name": "app usage database",
    "info": "Contains app usage data, including app names, open and close times, and durations.",
    "device": "Phone",
    "additional_instructions": "The app usage database provides detailed information about which apps were used, when they were opened and closed, and for how long. This can be used to understand user behavior patterns and app preferences."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_app_usage_blocks": get_app_usage_blocks,
    "get_most_recent_app": get_most_recent_app,
    "get_app_usage_summary": get_app_usage_summary,
    "get_app_usage_records": get_app_usage_records,
    "get_total_app_usage": get_total_app_usage
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
        import_path="\nUse following import for app usage database functions (APP)\nfrom data_streams.app_usage_data import function_name"
    )
