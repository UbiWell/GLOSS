import os

import langchain_openai as lcai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough

from pydantic import BaseModel, Field
from agents.llm_factory import get_llmchat

llmchat = get_llmchat()


class Output(BaseModel):
    summary: str = Field(description="heart rate summary for the given hour")


class Combination(BaseModel):
    summary: str = Field(description="heart rate summary for the combining hours")


def generate_combination_prompt_text(summaries, instructions):
    prompt = f"you need to combine hourly summaries for given {len(summaries)} hours into a single summary highlighting {instructions}. \n\n"

    for s in summaries:
        prompt += s
        prompt += "\n\n"

    prompt += "return answers in json format"

    return prompt


class HeartRateSummarizer:
    def __init__(self):
        self.hr_chain = self.hr_agent()
        self.combination_chain = self.combination_agent()

    def invoke_granular(self, input_params):
        hr_chain = self.hr_chain.invoke({'summary_n_1': input_params['summary_n_1'],
                                         'mean': input_params['mean'],
                                         'std_dev': input_params['std_dev'],
                                         'heart_rate_values': input_params['heart_rate_values'],
                                         'instructions': input_params['instructions']})
        return hr_chain

    def invoke_combination(self, input_params):
        prompt = generate_combination_prompt_text(input_params['summaries'], input_params['instructions'])
        combination_chain = self.combination_chain.invoke({"prompt": prompt})
        return combination_chain

    def hr_agent(self):
        parser = JsonOutputParser(pydantic_object=Output)

        prompt_text = """
        You need to summarize heart rate values seen for a person for the given hour. 
        
        Summary from last hour is also reported if present.
        
        Last hour summary: {summary_n_1}
        
        
        In your summary report {instructions}
    
        {heart_rate_values}
        
        
        Statistical summary of heart rate for given hour:
        mean: {mean}
        std_dev: {std_dev}
        
        if summary of last hour is not available do not include this information in final summary
        return answers in json format 

        """
        prompt = PromptTemplate(
            template=prompt_text + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | llmchat | parser

        return chain

    def combination_agent(self):
        parser = JsonOutputParser(pydantic_object=Combination)

        prompt_text = """{prompt}"""
        prompt = PromptTemplate(
            template=prompt_text + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | llmchat | parser

        return chain


if __name__ == "__main__":
    summary_n_1 = "not available"
    heart_rate_values = \
        '''
[{'time': '2024-06-25 00:00:04', 'heart_rate': 96.67}, {'time': '2024-06-25 00:01:34', 'heart_rate': 95.33}, {'time': '2024-06-25 00:03:04', 'heart_rate': 85.67}, {'time': '2024-06-25 00:04:34', 'heart_rate': 90.0}, {'time': '2024-06-25 00:06:04', 'heart_rate': 90.33}, {'time': '2024-06-25 00:07:34', 'heart_rate': 89.33}, {'time': '2024-06-25 00:09:04', 'heart_rate': 80.0}, {'time': '2024-06-25 00:10:34', 'heart_rate': 77.33}, {'time': '2024-06-25 00:12:04', 'heart_rate': 80.67}, {'time': '2024-06-25 00:13:34', 'heart_rate': 79.33}, {'time': '2024-06-25 00:15:04', 'heart_rate': 81.33}, {'time': '2024-06-25 00:16:34', 'heart_rate': 83.33}, {'time': '2024-06-25 00:18:04', 'heart_rate': 77.67}, {'time': '2024-06-25 00:19:34', 'heart_rate': 86.67}, {'time': '2024-06-25 00:21:04', 'heart_rate': 79.0}, {'time': '2024-06-25 00:22:34', 'heart_rate': 80.0}, {'time': '2024-06-25 00:24:04', 'heart_rate': 82.67}, {'time': '2024-06-25 00:25:34', 'heart_rate': 79.33}, {'time': '2024-06-25 00:27:04', 'heart_rate': 78.67}, {'time': '2024-06-25 00:28:34', 'heart_rate': 75.0}, {'time': '2024-06-25 00:30:04', 'heart_rate': 78.33}, {'time': '2024-06-25 00:31:34', 'heart_rate': 82.33}, {'time': '2024-06-25 00:33:04', 'heart_rate': 86.33}, {'time': '2024-06-25 00:34:34', 'heart_rate': 81.67}, {'time': '2024-06-25 00:36:04', 'heart_rate': 84.67}, {'time': '2024-06-25 00:37:34', 'heart_rate': 82.33}, {'time': '2024-06-25 00:39:04', 'heart_rate': 78.33}, {'time': '2024-06-25 00:40:34', 'heart_rate': 89.33}, {'time': '2024-06-25 00:42:04', 'heart_rate': 87.33}, {'time': '2024-06-25 00:43:34', 'heart_rate': 84.33}, {'time': '2024-06-25 00:45:04', 'heart_rate': 80.33}, {'time': '2024-06-25 00:46:34', 'heart_rate': 79.67}, {'time': '2024-06-25 00:48:04', 'heart_rate': 79.33}, {'time': '2024-06-25 00:49:34', 'heart_rate': 79.33}, {'time': '2024-06-25 00:51:04', 'heart_rate': 81.0}, {'time': '2024-06-25 00:52:34', 'heart_rate': 79.0}, {'time': '2024-06-25 00:54:04', 'heart_rate': 77.33}, {'time': '2024-06-25 00:55:34', 'heart_rate': 80.67}, {'time': '2024-06-25 00:57:04', 'heart_rate': 80.0}, {'time': '2024-06-25 00:58:34', 'average_heart_rate': 81.33}]
    '''

    response = HeartRateSummarizer().invoke_granular(
        {'summary_n_1': summary_n_1, 'mean': 82.53, 'std_dev': 4.92, 'heart_rate_values': heart_rate_values,
         'instructions': "average heart rate and trends"})
    print(response)
