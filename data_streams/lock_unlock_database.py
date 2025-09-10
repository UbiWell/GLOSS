"""
Lock Unlock Database - Phone lock/unlock data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original lock_unlock_data.py
from data_streams.lock_unlock_data import functions

# Import all the actual function implementations from lock_unlock_data.py
from data_streams.lock_unlock_data import (
    get_lock_unlock_blocks,
    get_total_lock_unlock_duration,
    get_lock_unlock_summary,
    get_lock_unlock_state_at_given_time,
    get_lock_unlock_records
)

# Database metadata for registry
database_info = {
    "name": "lock unlock database",
    "info": "Contains records of phone lock and unlock times, with functions to extract this information.",
    "device": "Phone",
    "additional_instructions": "The lock unlock database tracks when the phone screen is locked or unlocked. This can indicate user interaction patterns and phone usage behavior."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_lock_unlock_blocks": get_lock_unlock_blocks,
    "get_total_lock_unlock_duration": get_total_lock_unlock_duration,
    "get_lock_unlock_summary": get_lock_unlock_summary,
    "get_lock_unlock_state_at_given_time": get_lock_unlock_state_at_given_time,
    "get_lock_unlock_records": get_lock_unlock_records
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
        import_path="\nUse following import for lock unlock database functions (UL)\nfrom data_streams.lock_unlock_data import function_name"
    )
