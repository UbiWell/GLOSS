# """
# Template for creating new database modules.
#
# To add a new database:
# 1. Copy this template to a new file (e.g., my_new_database.py)
# 2. Fill in the database_info dictionary
# 3. Add your function metadata to the functions dictionary
# 4. Add your actual function implementations and references
# 5. Optionally implement register_database() for custom registration
# """
#
# from typing import Dict, Any, Callable
# from agents.database_registry import DatabaseRegistry
#
# # Database metadata - REQUIRED
# database_info = {
#     "name": "my_new_database",  # Unique name for your database
#     "info": "Description of what this database contains and how it works",
#     "device": "Device type (e.g., Phone, Watch, Sensor)",
#     "additional_instructions": "Any special instructions for using this database"
# }
#
# # Function metadata/definitions for LLMs - REQUIRED
# # This is what gets passed to LLMs to generate prompts
# functions = {
#     "FUNC1": {
#         "name": "get_my_data",
#         "description": "Retrieves data from your database for a specific user and time range.",
#         "function_call_instructions": "Call this function when you need to get raw data",
#         "usecase": ["code_generation", "function_calling"],
#         "params": {
#             "user_id": {"type": "str", "description": "The unique identifier for the user."},
#             "start_time": {"type": "str", "description": "The start timestamp for the time range."},
#             "end_time": {"type": "str", "description": "The end timestamp for the time range."}
#         },
#         "returns": "A list of data records for the specified time range.",
#         "example": "[{'timestamp': '2024-01-01 12:00:00', 'value': 42.5}]"
#     },
#     "FUNC2": {
#         "name": "analyze_my_data",
#         "description": "Analyzes data from your database and provides insights.",
#         "usecase": ["code_generation", "function_calling"],
#         "params": {
#             "data": {"type": "dict", "description": "The data to analyze"}
#         },
#         "returns": "Analysis results with insights and metrics.",
#         "example": "{'total_records': 100, 'average_value': 42.5, 'insights': 'Data shows normal patterns'}"
#     }
# }
#
# # Your actual function implementations
# def get_my_data_function(user_id: str, start_time: str, end_time: str) -> Dict[str, Any]:
#     """
#     Example function to get data from your database.
#
#     Args:
#         user_id: The user identifier
#         start_time: Start time in format "YYYY-MM-DD HH:MM:SS"
#         end_time: End time in format "YYYY-MM-DD HH:MM:SS"
#
#     Returns:
#         Dictionary containing the requested data
#     """
#     # Your implementation here
#     return {
#         "user_id": user_id,
#         "start_time": start_time,
#         "end_time": end_time,
#         "data": "Your actual data here"
#     }
#
# def analyze_my_data_function(data: Dict[str, Any]) -> Dict[str, Any]:
#     """
#     Example function to analyze data from your database.
#
#     Args:
#         data: The data to analyze
#
#     Returns:
#         Dictionary containing analysis results
#     """
#     # Your implementation here
#     return {
#         "analysis": "Your analysis results here"
#     }
#
# # Function references mapping (function name -> actual function) - REQUIRED
# function_refs = {
#     "get_my_data": get_my_data_function,
#     "analyze_my_data": analyze_my_data_function,
#     # Add more functions as needed
# }
#
# # Optional: Custom registration function
# def register_database(registry: DatabaseRegistry):
#     """
#     Custom registration function (optional).
#     Use this if you need custom logic during registration.
#
#     Args:
#         registry: The database registry instance
#     """
#     registry.register_database(
#         name=database_info["name"],
#         info=database_info["info"],
#         device=database_info["device"],
#         additional_instructions=database_info["additional_instructions"],
#         functions=functions,  # Function metadata/definitions for LLMs
#         function_refs=function_refs,  # Actual function references
#         import_path="\nUse following import for my new database functions (MYNEW)\nfrom data_streams.my_new_data import function_name"
#     )
#
# # Example usage in your code:
# if __name__ == "__main__":
#     # Test your functions
#     test_data = get_my_data_function("test_user", "2024-01-01 00:00:00", "2024-01-02 00:00:00")
#     print(test_data)
