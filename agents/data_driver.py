"""
Contains functions to run data extraction functions based on a given dictionary input.
"""

import os
import sys

import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))

import data_streams.activity_data as activity_data
import data_streams.location_data as location_data
import data_streams.phone_steps_data as phone_steps_data
import data_streams.garmin_hr_data as heart_rate_data
import data_streams.lock_unlock_data as lock_unlock_data
import data_streams.garmin_steps_data as garmin_steps_data
import data_streams.wifi_data as wifi_data
import data_streams.app_usage_data as app_usage_data
import data_streams.battery_data as battery_data
import data_streams.call_log as call_log
import models.stress_prediction_model as stress

all_functions = {**activity_data.functions, **location_data.functions, **phone_steps_data.functions,
                 **heart_rate_data.functions, **lock_unlock_data.functions, **garmin_steps_data.functions,
                 **wifi_data.functions, **app_usage_data.functions, **battery_data.functions, **call_log.functions,
                 **stress.functions}


def run_function_from_dict(function_name, params, type):
    try:
        # Access the function from the module's namespace
        if type == 'activity':
            func = getattr(activity_data, function_name)
        if type == 'location':
            func = getattr(location_data, function_name)
        if type == 'phone_steps':
            func = getattr(phone_steps_data, function_name)
        if type == 'heart_rate':
            func = getattr(heart_rate_data, function_name)
        if type == 'lock_unlock':
            func = getattr(lock_unlock_data, function_name)
        if type == 'garmin_steps':
            func = getattr(garmin_steps_data, function_name)
        if type == 'wifi':
            func = getattr(wifi_data, function_name)
        if type == 'app_usage':
            func = getattr(app_usage_data, function_name)
        if type == 'phone_battery':
            func = getattr(battery_data, function_name)
        if type == 'call_log':
            func = getattr(call_log, function_name)
        if type == 'stress':
            func = getattr(stress, function_name)

        output = func(**params)
        return output

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
    for d in dict_output:
        func_name = dict_output[d]['name']
        function_id = d
        data_type = ""
        if "STRESS" in function_id:
            data_type = 'stress'
        if "LOC" in function_id:
            data_type = 'location'
        if "ACT" in function_id:
            data_type = 'activity'
        if "PHONE" in function_id:
            data_type = 'phone_steps'
        if "GARMINHR" in function_id:
            data_type = 'heart_rate'
        if "UL" in function_id:
            data_type = 'lock_unlock'
        if "WIFI" in function_id:
            data_type = 'wifi'
        if "GARMINSTEP" in function_id:
            data_type = 'garmin_steps'
        if "APP" in function_id:
            data_type = 'app_usage'
        if "BATTERY" in function_id:
            data_type = 'phone_battery'
        if "CALLLOG" in function_id:
            data_type = 'call_log'
        if "BRIGHTNESS" in function_id:
            data_type = 'brightness'
        if "CODING" in function_id:
            if coding_function:
                params = dict_output[d]['params']
                query = params['user_query']
                final_results.append({"func": dict_output[d], "result": coding_function(query), "func_id": d})
                continue

        res = run_function_from_dict(func_name, dict_output[d]['params'], data_type)
        final_results.append({"func": dict_output[d], "result": res, "func_id": d})
    return final_results


if __name__ == "__main__":
    json_string = '''
   {
    "get_location_trace": {
        "uid": "test004",
        "start_time": "2024-07-07 15:15:00",
        "end_time": "2024-07-07 15:30:00"
    }
}
    '''

    input_dict = {
        "generate_total_activity": {
            "uid": "test004",
            "start_time": datetime(2024, 7, 10, 0, 0, 0),
            "end_time": datetime(2024, 7, 11, 14, 40, 59),
        }
    }
    run_function_from_dict(input_dict)

    print(json_to_dict(json_string))
