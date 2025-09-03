"""
This module uses LLM summarization without any code generation. It takes the last hour summary and current values
and generates a summary for the given hour.
"""

import os, sys
import langchain_openai as lcai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_processing')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_streams')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../agents')))

from pydantic import BaseModel, Field
from agents.llm_factory import get_llmchat

llmchat = get_llmchat()


class Output(BaseModel):
    summary: str = Field(description="summary for the given hour")


class Combination(BaseModel):
    summary: str = Field(description="summary for the combining hours")


def generate_combination_prompt_text(summaries, instructions, type, window):
    prompt = f"you need to combine {window} hourly {type} summaries for given {len(summaries)} hours into a single summary highlighting {instructions}. \n\n"

    for s in summaries:
        prompt += s
        prompt += "\n\n"

    prompt += "return answers in json format"

    return prompt


class GenericSummarizer:
    def __init__(self):
        self.hr_chain = self.hr_agent()
        self.combination_chain = self.combination_agent()

    def invoke_granular(self, input_params):
        hr_chain = self.hr_chain.invoke({'summary_n_1': input_params['summary_n_1'],
                                         'values': input_params['values'],
                                         'instructions': input_params['instructions'],
                                         'type': input_params['type'],
                                         'window': input_params['window']})
        return hr_chain

    def invoke_combination(self, input_params):
        prompt = generate_combination_prompt_text(input_params['summaries'], input_params['instructions'],
                                                  input_params['type'], input_params['window'])
        combination_chain = self.combination_chain.invoke({"prompt": prompt})
        return combination_chain

    def hr_agent(self):
        parser = JsonOutputParser(pydantic_object=Output)

        prompt_text = """
        You need to summarize {type} values seen for a person for the given {window} hour. 

        Summary from last {window} hour is also reported if present.

        Last hour summary: {summary_n_1}


        In your summary report {instructions}

        {values}

        if summary of last hour is not available do not include this information in final summary
        return answers in json format. Also include specific times in summary. Dont use relative time.

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
    values = ""

    response = GenericSummarizer().invoke_granular(
        {'summary_n_1': summary_n_1, 'values': values,
         'instructions': "location", 'type': "location"})
    print(response)
