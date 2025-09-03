import os
import sys
import json

import langchain_openai as lcai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from data_streams.generic_coding_functions import GenericCodingFunctions


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.data_driver import run_function_from_dict, json_to_dict, extract_data_multiple_type
from agent_utils import generate_function_calling_prompt
from agents.llm_factory import get_llmchat
from agents.database_registry import get_all_databases, get_functions_for_database, get_database
from agents.config import ONLY_CODE_FUNCTIONS

llmchat = get_llmchat()

'''This module defines a generic database manager agent that take a information request and requried databases. 
It then passes all helper functions to the Coding Agent to generate the code that can answer the question.'''

class GenericDatabaseManager:
    def __init__(self):
        self.database_chain = self.database_agent()
        self.function_call_history = []
        self.coding_function = None

    def invoke(self, input_params):
        req_databases = input_params["databases"]
        
        # Normalize database names (add " database" suffix if missing)
        normalized_databases = []
        for database in req_databases:
            if " database" not in database:
                normalized_databases.append(database + " database")
            else:
                normalized_databases.append(database)

        print(f"Databases requested: {normalized_databases}")
        
        # Get function metadata for LLM prompts
        calling_functions = {}
        
        for database_name in normalized_databases:
            db_functions = get_functions_for_database(database_name)

            
            if db_functions:
                calling_functions.update(db_functions)
            else:
                print(f"Warning: No functions found for database '{database_name}'")
        
        if not calling_functions:
            return {"NOT POSSIBLE": "No functions available for the requested databases"}

        # Get database information for prompt
        database_info = ""
        for database_name in normalized_databases:
            db = get_database(database_name)
            if db:
                database_info += f"{database_name}: {db.info}\n"
                if db.additional_instructions:
                    database_info += f"Additional instructions: {db.additional_instructions}\n"
            else:
                print(f"Warning: Database '{database_name}' not found in registry")

        coding_functions_obj = GenericCodingFunctions(calling_functions, req_databases)
        if ONLY_CODE_FUNCTIONS:
            cfs = coding_functions_obj.coding_functions
        else:
            cfs = calling_functions

        self.coding_function = coding_functions_obj.get_results_through_data_computation

        # Create prompt with database and function information
        input_instructions = f"""You are manager for following databases: \n{database_info}
        The users will request you for data. You have following functions that you can call to fulfil the request of the user:"""

        output_instructions = '''
        Your task is to return the dict of function calls with input params needed to answer the question asked by the user. 
        Do not call the functions with exact same parameters if they have been already called in the previous function calls

        Output Format: {function ID1: {"name": function name, "params" : {param1: value1, param2: value2}},
                       function ID2: {"name": function name, "params" :{param1: value1, param2: value2}}}
                       
        Example: {"CODING1": {"name": "get_results_through_data_computation", "params": {"user_id": 1234, "start_time": "2024-07-09 00:00:00", "end_time": "2024-07-09 23:59:59"}}}}

        Instructions:
        1) Just return the dict {} of function calls with input params in the required order. do not return anything else in the output including ```json or ```python.
        2) return {"NOT POSSIBLE" : reason} if the question cannot be answered with the existing functions or you have already called all the functions that could have answered the query.
        3) Do not write any additional code, just the list of function calls with input params
        4) The dates in params should be in "%Y-%m-%d %H:%M:%S" format
        5) Only add function calls when you know exact values of the parameters for the function call. do not add placeholders as parameters.  
        6) Do not assume that you do not have data in the databases for requested days unless you have already tried fetching the data. It has nothing to do with your training data.
        '''

        prompt = generate_function_calling_prompt(input_instructions, cfs, output_instructions)
        info_chain = self.database_chain.invoke(
            {'user_query': input_params['user_query'], 'function_call_history': self.function_call_history,
             'prompt': prompt})

        return info_chain

    def extract_data_step(self, chain_output):
        calls = json.loads(chain_output.content)
        if ("NOT POSSIBLE" in calls or "TERMINATE" in calls):
            return calls
        return extract_data_multiple_type(chain_output, self.coding_function)

    def database_agent(self):
        prompt = """{prompt}"""

        template = ChatPromptTemplate.from_messages(
            [
                ("system", prompt),
                ("user", "User Query: {user_query}\n\n Previous Function Calls: {function_call_history}")
            ]
        )

        chain = (template | llmchat | self.extract_data_step)
        return chain


if __name__ == "__main__":
    manager = GenericDatabaseManager()
    
    # List all available databases
    all_dbs = get_all_databases()
    print("Available databases:")
    for name, db in all_dbs.items():
        print(f"  - {name}: {db.info}")
    
    # Test with a sample query
    question = "most frequent location for test004 on 07/09/2024 using code."
    response = manager.invoke({'user_query': question, 'databases': ["location database"]})
    print(f"Response: {response}")
