"""
This file contains the NextStepAgent class, which is responsible for determining the next step in a sensemaking process
based on user queries and understanding.
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
from agents.llm_factory import get_llmchat

llmchat = get_llmchat()


class OutputNextStep(BaseModel):
    next_step: str = Field(description="returned next step")


class NextStepAgent:
    def __init__(self):
        self.next_step_chain = self.next_step_agent()

    def invoke_next_step(self, input_params):
        """Invoke the next step agent to determine the next step in the sensemaking process"""
        next_step_chain = self.next_step_chain.invoke({
            'user_query': input_params['user_query'],
            'memory': input_params['memory'],
            'understanding': input_params['understanding'],
            'action_plan': input_params['action_plan']
        })

        return next_step_chain

    def invoke(self, input_params):
        """Alias for invoke_next_step for backward compatibility"""
        return self.invoke_next_step(input_params)

    def next_step_agent(self):
        """Create the next step agent chain"""
        prompt = """
            Your task is to determine the next step based on the information provided in "understanding" and "User Query"
            
            ACTION PLAN:
            {action_plan}
        
            UNDERSTANDING:
            {understanding}
            
            USER QUERY:
            {user_query}
            
            
            Next Step Options:
            - INF: More data is needed to answer the "USER QUERY" based on "ACTION PLAN" and "UNDERSATNDING"
            - END: The the UNDERSTANDING fully answers the "USER QUERY" based on "ACTION PLAN"
            - END: If the "understanding" contains CODE-999.
        
             Do not return {{"next_step": "END"}} if the "UNDERSTANDING" does not have a satisfactory answer to the "USER QUERY"
            
            
            Instructions:
            1) Return {{"next_step": "INF"}} if the "UNDERSTANDING" indicates additional information is needed.
            2) Do not {{"next_step": "END"}} if "UNDERSTANDING" indicates that information from other databases can be used for additional verification.
            4) Return {{"next_step": "END"}} if the "understanding" fully answers the "USER QUERY" or contains CODE-999.
            5) return {{"next_step": "INF"}} or {{"next_step": "END"}}
            
            Example: 
            {{"next_step": "INF"}}  
            {{"next_step": "END"}}
            """

        parser = JsonOutputParser(pydantic_object=OutputNextStep)

        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = (prompt | llmchat | parser)

        return chain


if __name__ == "__main__":
    question = (
        "can you provide location of places where test004 was stationary based 07/09/2024 data")
    response = NextStepAgent().invoke(
        {'user_query': question, 'memory': '', 'understanding': "", "action_plan": ""})
    print(response)
