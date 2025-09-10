"""
Brightness Database - Phone screen brightness data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original brightness.py
from data_streams.brightness import functions

# Import all the actual function implementations from brightness.py
from data_streams.brightness import (
    get_brightness_records,
    get_brightness_at_time
)

# Database metadata for registry
database_info = {
    "name": "brightness database",
    "info": "Contains phone screen brightness data, including brightness levels and changes over time.",
    "device": "Phone",
    "additional_instructions": "The brightness database tracks phone screen brightness levels. This can indicate user preferences and environmental lighting conditions."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_brightness_records": get_brightness_records,
    "get_brightness_at_time": get_brightness_at_time
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
        import_path="\nUse following import for brightness database functions (BRIGHTNESS)\nfrom data_streams.brightness_data import function_name"
    )
