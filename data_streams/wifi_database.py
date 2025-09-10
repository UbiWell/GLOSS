"""
WiFi Database - Phone WiFi connection data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original wifi_data.py
from data_streams.wifi_data import functions

# Import all the actual function implementations from wifi_data.py
from data_streams.wifi_data import (
    get_wifi_blocks,
    get_wifi_usage_summary,
    generate_wifi_total_duration,
    get_wifi_records,
    get_wifi_at_a_time
)

# Database metadata for registry
database_info = {
    "name": "wifi database",
    "info": "Contains data whether phone is connected to wifi or not. It also contains the wifi name to which phone is connected.",
    "device": "Phone",
    "additional_instructions": "The wifi database tracks WiFi connection status and network names. This can indicate user location patterns and network preferences."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_wifi_blocks": get_wifi_blocks,
    "get_wifi_usage_summary": get_wifi_usage_summary,
    "generate_wifi_total_duration": generate_wifi_total_duration,
    "get_wifi_records": get_wifi_records,
    "get_wifi_at_a_time": get_wifi_at_a_time
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
        import_path="\nUse following import for wifi database functions (WIFI)\nfrom data_streams.wifi_data import function_name"
    )
