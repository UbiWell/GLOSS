"""
This file contains code for Information Seeking Agent
"""

import os, sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from agents.llm_factory import get_llmchat
from agents.database_registry import get_all_databases

llmchat = get_llmchat()


class Output(BaseModel):
    database: str = Field(description="databases needed separated by comma")
    request: str = Field(description="data request made to the databases")


class InformationSeekingAgent:
    def __init__(self):
        self.information_chain = self.information_agent()

    def invoke(self, input_params):
        # Get databases from registry
        databases = get_all_databases()

        databases_section = "\n".join(
            f"    {idx + 1}. {db_name}  \n"
            f"       - Info: {db_info.info}  \n"
            f"       - Device: {db_info.device}  \n"
            for idx, (db_name, db_info) in enumerate(databases.items())
        )

        info_chain = self.information_chain.invoke({'understanding': input_params['understanding'],
                                                    'user_query': input_params['user_query'],
                                                    'action_plan': input_params['action_plan'],
                                                    'memory': input_params['memory'],
                                                    'databases_section': databases_section})

        return info_chain

    def information_agent(self):
        prompt = """
    Task: Your role is to create a very specific information request to the databases to answer the QUESTION based on the UNDERSTANDING and ACTION PLAN and MEMORY. 
    UNDERSTANDING might contain partial answer to user query and might have information on what additional data is needed. ACTION PLAN can also help in deciding what data is needed. MEMORY contains all the data already fetched from the databases. 
    
    \Your information request should include any aggregation, comparisons, computation and data processing you need to do to answer the question.
    
    if you are asking for data for more than one day ask aggregated data rather than just raw data.

    Never ask for more than three databases in a single request.
    
    Always mention user_id in your request. You can get user_id from user_query

    
        "QUESTION": 
          {user_query}
          
          "ACTION PLAN":
          {action_plan}
          
          "MEMORY": 
          {memory}
      
          "UNDERSTANDING": 
          {understanding}
    
        
   {databases_section}
   
   output format: {{"database": "databases needed", "request": request made to the databases}}
   example: {{"database": "database1, database2", "request": "summarize data for user_id 1234"}}
   
   database name should be taken from information above
   
   your request should be specific having specific time, date, user_id, and other details:
   for example:
    not specific: summarize call log for test007 on 07/09/2024 around the times when the missed calls occurred is not specific as it doesn't mention how much time before and after the missed calls.
    specific: summarize call log for test007 on 07/09/2024 30 mins before and after  when the missed calls occurred
    You can make your request specific by selecting appropriate time frame
    ---      
        
        Instructions:
        1. use the "QUESTION", "ACTION PLAN", "MEMORY" and "UNDERSTANDING" to make the request.
        
        2. UNDERSTANDING usually contains information about what kind of data is needed next to answer the question
        
        3. Have date and time in your requests in "%Y-%m-%d %H:%M:%S" format
        
        4. make the request to the database in the natural language from which you need information the most. return request in json format. {{"database name": request}}
        
        5. if you are asking for data for more than one day ask aggregated data rather than just raw data.
                        
        6. Do not ask any questions for which the answer is already present in the UNDERSTANDING.
        
        7. You want all data processing to be done by the database manager, including any filter, aggregation, or transformation, and just want the summarized final result
        
        8. You can return {{"NOT POSSIBLE":""}} as the response if databases don't contain kind of information asked.
        
        9. Make your request in natural language and not in SQL queries. 
        
        10. Make you request in lowercase. Do not capitalize any words in your request.     
        11. If understanding says it does not contain a particular kind of data trust it.          
        """
        parser = JsonOutputParser(pydantic_object=Output)

        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | llmchat | parser

        return chain


if __name__ == "__main__":
    question = "summarize day of test004 on 07/09/2024?"
    understanding = ""
    memory = ""
    response = InformationSeekingAgent().invoke(
        {'understanding': understanding, 'user_query': question, 'action_plan': "", 'memory': memory})
    print(response)
