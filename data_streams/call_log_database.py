"""
Call Log Database - Phone call history data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original call_log.py
from data_streams.call_log import functions

# Import all the actual function implementations from call_log.py
from data_streams.call_log import (
    get_call_log_records,
    get_call_log_blocks,
    get_call_log_stats
)

# Database metadata for registry
database_info = {
    "name": "call log database",
    "info": "Contains call log records, including timestamps, call types (e.g., 'incoming,' 'outgoing'), call durations, and phone ringing durations.",
    "device": "Phone",
    "additional_instructions": "The call log database tracks phone call history including incoming, outgoing, and missed calls. This can indicate communication patterns and social interaction frequency."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_call_log_records": get_call_log_records,
    "get_call_log_blocks": get_call_log_blocks,
    "get_call_log_stats": get_call_log_stats
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
        import_path="\nUse following import for call log database functions (CALL)\nfrom data_streams.call_log import function_name"
    )
