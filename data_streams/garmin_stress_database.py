"""
Garmin Stress Database - Garmin watch stress data
Converted to use the new database registry system
"""

import sys
import os
from typing import Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

# Import function metadata from the original stress_prediction_model.py
from models.stress_prediction_model import functions

# Import all the actual function implementations from stress_prediction_model.py
from models.stress_prediction_model import (
    get_stress_predictions,
    get_stress_aggregation,
    get_stress_stats
)

# Database metadata for registry
database_info = {
    "name": "garmin stress database",
    "info": "Contains physiological stress predictions from ibi data recorded from the Garmin smartwatch. physiological stress might not always be same as psychological stress. The predictions are stress probabilities with near to 1 being more stressed.",
    "device": "Garmin Smartwatch",
    "additional_instructions": "The garmin stress database provides physiological stress predictions based on heart rate variability data. Note that physiological stress may differ from psychological stress."
}

# Create function references mapping (function name -> actual function)
function_refs = {
    "get_stress_predictions": get_stress_predictions,
    "get_stress_aggregation": get_stress_aggregation,
    "get_stress_stats": get_stress_stats,
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
        import_path="\nUse following import for garmin stress database functions (STRESS)\nfrom models.stress_prediction_model import function_name"
    )
