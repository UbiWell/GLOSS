"""
Contains functions to run data extraction functions based on a given dictionary input.
"""

import os
import sys

import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))

import data_streams.lock_unlock_data as lock_unlock_data
import data_streams.app_usage_data as app_usage_data
import data_streams.call_log as call_log
import data_streams.sms_data as sms_data
import data_streams.sensing_data as sensing_data

# The module backing each data_type tag. Keys must match the values produced by
# _data_type_for() below.
_MODULES = {
    'lock_unlock': lock_unlock_data,
    'app_usage': app_usage_data,
    'call_log': call_log,
    'sms': sms_data,
    'sensing': sensing_data,
}

# Function-id prefix -> data_type. The LLM returns ids such as "SMS2" or
# "CALLLOG1"; these are matched as substrings. No live id contains more than one
# of these prefixes, so order is not load-bearing, but the longest are listed
# first to keep it that way if ids are ever added.
_ID_PREFIXES = (
    ('CALLLOG', 'call_log'),
    ('SENSE', 'sensing'),
    ('SMS', 'sms'),
    ('APP', 'app_usage'),
    ('UL', 'lock_unlock'),
)

all_functions = {**lock_unlock_data.functions, **app_usage_data.functions,
                 **call_log.functions, **sms_data.functions,
                 **sensing_data.functions}


def run_function_from_dict(function_name, params, type):
    """Call one data function by name, dispatching on its data_type tag."""
    module = _MODULES.get(type)
    if module is None:
        # A chain of `if`s here previously left `func` unbound for any
        # unrecognised type, which surfaced as an UnboundLocalError swallowed by
        # the bare except below and reported nothing useful.
        print(f"Unknown data type '{type}' for function {function_name}")
        return None

    try:
        func = getattr(module, function_name)
        return func(**params)

    except AttributeError as e:
        print(f"Function {function_name} not found in module: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def json_to_dict(json_string):
    # Convert JSON string to dictionary
    data_dict = json.loads(json_string)
    return data_dict


def get_function_description(functions, function_name):
    for key, function in functions.items():
        if function['name'] == function_name:
            return function['description']

    return "Function not found."


def _data_type_for(function_id):
    """Map an LLM-returned function id onto its data_type tag."""
    for prefix, data_type in _ID_PREFIXES:
        if prefix in function_id:
            return data_type
    return ""


def extract_data(chain_output, data_type):
    final_results = []
    chain_output = chain_output.content
    dict_output = json_to_dict(chain_output)
    for d in dict_output:
        func_name = dict_output[d]['name']
        res = run_function_from_dict(func_name, dict_output[d]['params'], data_type)
        final_results.append({"func": dict_output[d], "result": res, "func_id": d})
    return final_results


def extract_data_multiple_type(chain_output, coding_function=None):
    final_results = []
    chain_output = chain_output.content
    dict_output = json_to_dict(chain_output)
    for function_id in dict_output:
        call = dict_output[function_id]

        # Code generation goes to the coding agent, which runs the generated
        # code in a Docker container instead of calling a data function here.
        if "CODING" in function_id and coding_function:
            final_results.append({
                "func": call,
                "result": coding_function(call['params']['user_query']),
                "func_id": function_id,
            })
            continue

        res = run_function_from_dict(call['name'], call['params'],
                                     _data_type_for(function_id))
        final_results.append({"func": call, "result": res, "func_id": function_id})
    return final_results
