import sys
import os
from termios import VERASE
import pytz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))

from datetime import datetime, timedelta
import agents.generic_summarizer
from data_processing.data_processing_utils import fetch_documents_between_timestamps
from data_streams.constants import GARMIN_STEPS, time_zone_dict
from agents.coding_agent import run_coding_agent
from agents.config import VERBOSE


coding_functions = {
    "CODING1": {
        "name": "get_results_through_data_computation",
        "description": "This function can programatically generates a python code and answer the user query using data from databases.",
        "coding_instructions": "Call this function to do perform calculation and computation. Also call this function to combine data from multiple databases.",
        "usecase": ["function_calling"],
        "function_call_instructions": "Call this function to do perform calculation and computation on wifi data.",
        "params": {
            "user_query": {"type": "str",
                           "description": "query to perform a coding and calculation task. Please include user_id (uid) in the query"},
        },
        "returns": "Provides answer to the query by performing computations data in the your database"
    }
}


class GenericCodingFunctions:
    def __init__(self, functions, req_databases):
        self.functions = functions
        self.databases = req_databases
        database_names = ', '.join(req_databases)
        self.coding_functions = {
            "CODING1": {
                "name": "get_results_through_data_computation",
                "description": f"This function can programatically generates a python code and answer the user query using data from {database_names}",
                "usecase": ["function_calling"],
                "function_call_instructions": "Call this function to do perform calculation and computation. Ask this functions to do aggregation and computation on data from multiple databases.",
                "params": {
                    "user_query": {"type": "str",
                                   "description": "the query user asked. Please include user_id in the query"},
                },
                "returns": "Provides answer to the query by performing computations data in the your database"
            }
        }

    def get_results_through_data_computation(self, user_query):
        if VERBOSE:
            print(f"\n{'🔹' * 20} CODE GENERATION {'🔹' * 20}")

        include_statements = """
        import sys
        import os
        
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))
        
        
        from datetime import datetime
        from datetime import timedelta
    
        import numpy as np
        import pandas as pd
        from math import sin, cos, sqrt, atan2, radians
        
        from geopy.distance import great_circle
        from scipy import spatial
        from geopy import distance
        from shapely.geometry import MultiPoint
        from sklearn.cluster import DBSCAN
        from data_processing.data_processing_utils import fetch_documents_between_timestamps
        from data_streams.constants import *
        import folium
        from geopy.geocoders import Nominatim
        from geopy.geocoders import GoogleV3
        from agents.coding_agent import run_coding_agent 
        """
        function_imports = ""
        for database in self.databases:
            # Get complete import statement from database registry
            from agents.database_registry import get_import_path_for_database
            import_statement = get_import_path_for_database(database)
            
            if import_statement:
                function_imports += import_statement

        results = run_coding_agent(user_query=user_query, database=self.databases, functions=self.functions,
                                   include_statements=include_statements, function_imports=function_imports)
        if (not results.messages):
            return "The code generation couldn't answer this query. Please try again later."
        else:
            return results.messages[-2].content + "\n" + results.messages[-1].content.replace("TERMINATE", "")


