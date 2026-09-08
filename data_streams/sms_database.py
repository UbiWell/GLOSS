"""
SMS Database - Text message metadata
Follows the database registry system used by the other data streams.
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original sms_data.py
from data_streams.sms_data import functions

# Import all the actual function implementations from sms_data.py
from data_streams.sms_data import (
    get_sms_records,
    get_sms_stats,
    get_sms_contact_breakdown
)

# Database metadata for registry
database_info = {
    "name": "sms database",
    "info": "Contains text message metadata, including timestamps, message direction (incoming, outgoing, missed), message length in characters, read status, and an anonymized contact identifier.",
    "device": "Phone",
    "additional_instructions": "The sms database tracks text messaging activity and can indicate communication patterns and social interaction frequency. Message contents are NOT stored: only the length in characters is available, so questions about what was said cannot be answered. Contacts are anonymized hashes, so a contact can be counted and compared but never named."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_sms_records": get_sms_records,
    "get_sms_stats": get_sms_stats,
    "get_sms_contact_breakdown": get_sms_contact_breakdown
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
        import_path="\nUse following import for sms database functions (SMS)\nfrom data_streams.sms_data import function_name"
    )
