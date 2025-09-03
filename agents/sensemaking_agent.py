"""
This module defines a SenseMakingAgent that performs global and local sensemaking steps.
"""
import os
import sys

import langchain_openai as lcai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import StrOutputParser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from pydantic import BaseModel, Field
from agents.data_driver import all_functions

from agents.data_driver import run_function_from_dict, json_to_dict, get_function_description
from agents.llm_factory import get_llmchat

llmchat = get_llmchat()


class Output(BaseModel):
    understanding: str = Field(description="UNDERSTANDING is the current understanding to answer the user query")


class OutputLocal(BaseModel):
    summary: str = Field(description="result is the summarization of the result")


class SenseMakingAgent:
    def __init__(self):
        self.sensemaking_chain = self.sensemaking_agent()
        self.global_sensemaking_chain = self.global_sensemaking_agent()

    def invoke_local_sense(self, input_params):
        prompt = self.generate_prompt_local_sense_making(input_params['results'], input_params['data_type'],
                                                         input_params['user_query'])
        info_chain = self.sensemaking_chain.invoke({"prompt": prompt, "user_query": input_params['user_query']})

        return info_chain

    def invoke_global_sense(self, input_params):
        info_chain = self.global_sensemaking_chain.invoke({'user_query': input_params['user_query'],
                                                           'understanding': input_params['understanding'],
                                                           'memory': input_params['memory'],
                                                           'action_plan': input_params['action_plan']})

        return info_chain

    def generate_prompt_local_sense_making(self, results, data_type, question):
        p = f"Your role is to make sense and summarize the {data_type} data based on user's query \n"
        p += f"User Query: {question} \n\n"
        for r in results:
            function_name = r['func']['name']
            p += f"The results are depicted below for function {r['func']} \n\n"

            p += f"Information about function:\n {get_function_description(all_functions, function_name)} \n\n"

            p += f"Results:\n {r['result']} \n\n"

        p += """
        Instructions:
        1) Use the information in the results to summarize the data based on user's question.
        2) Be clear on what data was used to ger the results.
        3) Return the summarization of result as JSON with key "summary" and value as the summarization.
        
        """
        return p

    def sensemaking_agent(self):
        prompt = \
            """
            {prompt}
            """

        parser = JsonOutputParser(pydantic_object=OutputLocal)

        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = (prompt | llmchat | parser)

        return chain

    def global_sensemaking_agent(self):
        prompt = \
            """
            USER QUERY: 
            {user_query}
            
            ACTION PLAN:
            {action_plan}
             
            MEMORY: 
            {memory}
            
            UNDERSTANDING: 
            {understanding}
            
            USER QUERY is the question asked by the user.
            
            ACTION PLAN is the possible action plan generated to answer the USER QUERY

            UNDERSTANDING is the current answer the USER QUERY
            
            MEMORY is all the data gathered so far
            
            
            Your role is to rewrite the UNDERSTANDING such that it answers USER QUERY based on the information in MEMORY, current UNDERSTANDING and ACTION PLAN.
            If the more data is needed to answer the query which is not available in MEMORY yet, then include the kind of data needed in the UNDERSTANDING.
            
            
            UNDERSTANDING should include ALL the important information from Memory that can be needed later to answer the USER QUERY. 
            Include any important information in Memory revelant to the USER QUERY. Do not lose information.
            Do not suggest additional data if current data sufficiently answers the USER QUERY.
        
            
            
            Instructions:
            1) Update the understanding based on the information in Memory and User Query if required.
            2) Use common sense to create an understanding.
            3) Just return updated understanding in Format {{"understanding": "updated understanding"}}
            4) Do not have ```json or ```python in your answer
            5) The understanding should be in natural language and dates in understanding should be in "%Y-%m-%d %H:%M:%S" format.
            6) if memory has CODE-999 include that in understanding
            7) You should resynthesize UNDERSTANDING such that it answers the USER QUERY best based on current data and also contains information on additional data needed.
            8) if some data was tried fetching from memory and was not found, include that in understanding.
            """

        parser = JsonOutputParser(pydantic_object=Output)

        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = (prompt | llmchat | parser)

        return chain


if __name__ == "__main__":
   pass
