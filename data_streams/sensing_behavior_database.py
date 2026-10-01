"""
Sensing behaviour database - registration.  >>> TUTORIAL DEMO <<<

Everything this database needs already exists in ``sensing_behavior_data.py``:
working functions, and the ``functions`` metadata that tells the agent what
they do. What is missing is the registration below, so GLOSS does not know the
database is there. Ask it about sleep right now and it will tell you it cannot
answer.

Left unregistered on purpose. Uncommenting the block at the bottom is walked
through live during the tutorial -- see TUTORIAL.md -- so the before and after
can be shown with one query. Restoring this state afterwards is just
``git checkout`` on this file.

How registration works:

    1. database_info   -- what this database is, in the words the agent reads
                          when it decides where to look
    2. function_refs   -- name -> the actual Python function
    3. register_database() -- hand both to the registry

The registry imports every file in data_streams/ whose name ends in
``_database.py``, so this file is already being loaded. It just has nothing to
offer yet. There is no central list of databases to edit.

Note it is not enough to uncomment only register_database(): a module exposing
both ``functions`` and ``database_info`` gets registered automatically even
without it. That is why ``database_info`` is commented out too -- otherwise the
exercise would already be done.

See ``sensing_mobility_database.py`` for the finished version of this file.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_streams.sensing_behavior_data import (
    functions,
    list_behavior_features,
    find_behavior_feature,
    get_behavior_daily,
    get_behavior_by_epoch,
    get_behavior_hourly,
)


# Listed in the dashboard as a database that exists but is not loaded yet, so
# the gap is visible rather than silent. Delete this once you uncomment the
# block below -- a registered database does not need announcing as pending.
pending_registration = {
    "name": "sensing behavior database",
    "info": "Sleep, phone use, ambient sound and light, and the study's own daily "
            "call and message aggregates. Written but not registered -- "
            "registering it is demonstrated during the tutorial.",
}

# ---------------------------------------------------------------------------
# UNCOMMENT EVERYTHING BELOW TO REGISTER THIS DATABASE
# ---------------------------------------------------------------------------

# database_info = {
#     "name": "sensing behavior database",
#     "info": "Contains daily passive sensing features describing what the phone and its surroundings recorded: hours slept and when, how often and how long the phone was unlocked, ambient sound level and detected conversations, ambient light, and daily call and message aggregates.",
#     "device": "Phone",
#     "additional_instructions": (
#         "Feature names are terse and easy to confuse, so call find_behavior_feature "
#         "first and use the name it ranks first rather than guessing. The sleep "
#         "features are recorded once per day and have no epoch or hourly breakdown. "
#         "The call_* and sms_* features here are the study's own aggregates and do "
#         "not reconcile with the call log and sms databases, which should be "
#         "preferred for counting calls and messages. This database covers sleep, "
#         "phone use, sound, light and communication only -- location and activity "
#         "features are in the sensing mobility database."
#     ),
# }
#
# function_refs = {
#     "list_behavior_features": list_behavior_features,
#     "find_behavior_feature": find_behavior_feature,
#     "get_behavior_daily": get_behavior_daily,
#     "get_behavior_by_epoch": get_behavior_by_epoch,
#     "get_behavior_hourly": get_behavior_hourly,
# }
#
#
# def register_database(registry):
#     """Register this database with the registry."""
#     registry.register_database(
#         name=database_info["name"],
#         info=database_info["info"],
#         device=database_info["device"],
#         additional_instructions=database_info["additional_instructions"],
#         functions=functions,              # metadata the LLM reads
#         function_refs=function_refs,      # the callables themselves
#         import_path=(
#             "\nUse following import for sensing behavior database functions (BEHAVIOR)\n"
#             "from data_streams.sensing_behavior_data import function_name"
#         ),
#     )
