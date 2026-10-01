"""
Sensing mobility database - registration.

The pattern every GLOSS database follows, and the one the sensing behaviour
database asks you to complete:

    1. database_info  -- what this database is, in the words the agent reads
       when it decides where to look
    2. function_refs  -- name -> the actual Python function
    3. register_database() -- hand both to the registry

The registry discovers this file by its name: anything in data_streams/ ending
in ``_database.py`` is imported at start-up. Nothing else needs editing -- there
is no central list of databases.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_streams.sensing_mobility_data import (
    functions,
    list_mobility_features,
    find_mobility_feature,
    get_mobility_daily,
    get_mobility_by_epoch,
    get_mobility_hourly,
)

database_info = {
    "name": "sensing mobility database",
    "info": "Contains daily passive sensing features describing where the participant was and how they moved: distance travelled, number of places visited, hours spent at each kind of place (home, study, food, leisure, workout and others), and activity recognition such as time spent still, on foot or in a vehicle.",
    "device": "Phone",
    "additional_instructions": (
        "Feature names are terse and near-duplicates of each other, so call "
        "find_mobility_feature first and use the name it ranks first rather than "
        "guessing. Most per-place loc_* features are recorded once per day and have "
        "no epoch or hourly breakdown; get_mobility_daily works for all of them. "
        "This database covers location and activity only -- sleep, phone use, sound, "
        "light and communication features are in the sensing behavior database."
    ),
}

function_refs = {
    "list_mobility_features": list_mobility_features,
    "find_mobility_feature": find_mobility_feature,
    "get_mobility_daily": get_mobility_daily,
    "get_mobility_by_epoch": get_mobility_by_epoch,
    "get_mobility_hourly": get_mobility_hourly,
}


def register_database(registry):
    """Register this database with the registry."""
    registry.register_database(
        name=database_info["name"],
        info=database_info["info"],
        device=database_info["device"],
        additional_instructions=database_info["additional_instructions"],
        functions=functions,              # metadata the LLM reads
        function_refs=function_refs,      # the callables themselves
        import_path=(
            "\nUse following import for sensing mobility database functions (MOBILITY)\n"
            "from data_streams.sensing_mobility_data import function_name"
        ),
    )
