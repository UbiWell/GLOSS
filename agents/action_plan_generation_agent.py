"""
This file contains code for Action Plan Generation Agent
"""

import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.llm_factory import get_llmchat
from agents.database_registry import get_all_databases, get_database

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

from langchain_core.prompts import PromptTemplate

from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser

llmchat = get_llmchat()


class Output(BaseModel):
    action_plan: str = Field(description="action plan")


class ActionPlanGenerationAgent:
    def __init__(self):
        self.plan_chain = self.action_plan_agent()

    def generate_prompt(self, user_query):
        """
        Generates a formatted prompt string for the task based on the given user query and databases.

        Parameters:
        - user_query (str): The user query.
        - databases (dict): A dictionary where each key is a database name and each value is a dictionary with 'info' and 'device'.

        Returns:
        - str: The formatted prompt.
        """

        # Formatting the databases section
        databases = get_all_databases()
        database_info = ""
        for database_name in databases:
            db = get_database(database_name)
            if db:
                database_info += f"{database_name}: {db.info}\n"
                database_info += f"Device: {db.device}\n"
                if db.additional_instructions:
                    database_info += f"Additional instructions: {db.additional_instructions}\n\n"

            else:
                print(f"Warning: Database '{database_name}' not found in registry")

        # Defining the prompt template
        prompt_template = f"""
    Task: Given the available databases and the user's query, generate up to an action plan on how the user's question can be answered using the available databases. 
    You can use multiple databases in your action plan. Your action plan should try to answer all parts of the user query.

        ---
        User Query:
        {user_query}

        Databases Available:

        {database_info}

        ---
Instructions:

    1. Based on the user's query, generate up an action plan on how the query might be answered using the available databases.

    2. Your action plan should assume that all the processing happens by database functions. 

    2. If the answer cannot be directly determined, your action plan should provide approximations where possible.

    3. The action plan should reference the database(s) and describe how the information can be used to answer the query.

    4. Ensure the output is formatted in JSON, with natural language used for action plan. All the steps of action plan should be included in same string and return a JSON {{"action_plan": your plan}}.

    5. Return the any date and time in the format "%Y-%m-%d %H:%M:%S". If ambiguous, assume date in query is in %Y-%m-%d %H:%M:%S" format and mention this in your action plan.

    6. Use Common Sense and your world knowledge to generate the action plan.

    8. If the question cannot be answered with the given data. The action plan should just say that "The query cannot be answered with given datasets".

    9. You can use multiple databases in your action plan only when needed. If you can answer the query with single database, you should use only that database.
        """

        return prompt_template.strip()

    def invoke(self, input_params):
        prompt = self.generate_prompt(input_params['user_query'])

        info_chain = self.plan_chain.invoke({'user_query': input_params['user_query'], 'prompt': prompt})

        return info_chain

    def action_plan_agent(self):
        prompt = """ {prompt}"""

        parser = JsonOutputParser(pydantic_object=Output)
        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | llmchat | parser

        return chain


if __name__ == "__main__":
    question = "what are most visited location for test004 on 07/09/2024?"
    response = ActionPlanGenerationAgent().invoke({'user_query': question})
    print(response['action_plan'])
