"""
RAGBasedAgent: An agent that uses Retrieval-Augmented Generation (RAG) to answer user queries based on relevant data from multiple databases.
"""
import os
import sys

import langchain_openai as lcai
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from pydantic import BaseModel, Field
from langchain import hub
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from agents.agent_utils import invoke_with_retry
from agents.llm_factory import get_llmchat
from agents.database_registry import get_all_databases

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.rag_utils import get_data_to_narrative

llmchat = get_llmchat()
databases = get_all_databases()


class Output(BaseModel):
    uid: str = Field(description="user id")
    start_date: str = Field(description="start date and time of query")
    end_date: str = Field(description="end date and time of query")
    databases: str = Field(description="databases to query")


max_retries = 2

class RAGBasedAgent:
    def __init__(self):
        self.context = "blank"
        self.first_step_chain = self.first_step_agent()

    def generate_prompt(self, user_query, databases):
        """
        Generates a formatted prompt string for the task based on the given user query and databases.

        Parameters:
        - user_query (str): The user query.
        - databases (dict): A dictionary where each key is a database name and each value is a dictionary with 'info' and 'device'.

        Returns:
        - str: The formatted prompt.
        """

        # Formatting the databases section
        databases_section = "\n".join(
            f"    {idx + 1}. {db_name}  \n"
            f"       - Info: {db_info.info}  \n"
            f"       - Device: {db_info.device}  \n"
            for idx, (db_name, db_info) in enumerate(databases.items())
        )

        # Defining the prompt template
        prompt_template = f"""
        Task: Given the available databases and the user's query. You need to give me start time and endtime from user query and the databases that might be needed to answer the query.

        ---
        User Query:
        {user_query}

        Databases Available:

        {databases_section}


        Example:
        User Query: "How many steps did test007 took between 25th July 24  and 27th July 24?"
        {{uid: "test007"
        databases:"phone steps database"
        start_date:"2024-07-25 00:00:00"
        end_date:"2024-07-27 23:59:59"}}

        User Query: "How many phone apps did test004 open between 25th July 24 7am and 27th July 24 and what was the total phone lock duration?"
        {{uid: "test007"
        databases:"app usage, lock unlock database"
        start_date:"2024-07-25 07:00:00"
        end_date:"2024-07-27 23:59:59"}}


        ---

         Instructions:

        1. databases needed should be comma separated
        2. Any date and time in the format "%Y-%m-%d %H:%M:%S".
        3. Return the dict of {{user_id: user_id, start_date: start_date, end_date: end_date, databases: databases}}.
        4. Do not return anything else in the output including ```json or ```python.
        5. if user specifies on date for example "On 25th July 24 what was test007 steps?" then start_date should be start of the dayt and end_date should be end of the day.

        """

        return prompt_template.strip()

    def invoke_first_step_agent(self, input_params):
        prompt = self.generate_prompt(input_params['user_query'], databases)
        info_chain = self.first_step_chain.invoke({'user_query': input_params['user_query'], 'prompt': prompt})

        return info_chain

    def first_step_agent(self):
        prompt = """{prompt}"""

        parser = JsonOutputParser(pydantic_object=Output)

        # template = ChatPromptTemplate.from_messages(
        #     [
        #         ("system", prompt),
        #     ]
        # )
        prompt = PromptTemplate(
            template=prompt + '\n {format_instructions}',
            input_variables=[],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | llmchat | parser

        return chain

    # def rag_prompt_generator(self):
    #     prompt = """You are an assistant for question-answering tasks related to sensor data. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know.
    #                 Question: {{question}}
    #                 Context: {{context}}
    #                 Answer:"""
    #     return prompt

    def invoke_rag_agent(self, input_params):
        # response = invoke_with_retry(self.first_step_agent(), 'invoke_first_step_agent', {
        #     'user_query': input_params['user_query']})

        response = invoke_with_retry(self, 'invoke_first_step_agent', {
            'user_query': input_params['user_query']})

        if response == "FAILED":
            return "FAILED"

        databases = response['databases']
        start_date = response['start_date']
        end_date = response['end_date']

        if not databases:
            return "FAILED"

        self.context = get_data_to_narrative(response['uid'], start_date, end_date, databases)
        # print(self.context)

        rag_chain = self.rag_agent()
        retries = 0
        while retries <= max_retries:
            try:
                info_chain = rag_chain.invoke(input_params['user_query'])
                return info_chain
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    print(f"Failed after {max_retries + 1} attempts: {str(e)}")
                    return "FAILED"
        # info_chain = rag_chain.invoke(input_params['user_query'])
        return info_chain

    def rag_agent(self):
        docs = Document(page_content=self.context)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents([docs])
        vectorstore = Chroma("GLOSS_rag")
        vectorstore._client.delete_collection("GLOSS_rag")
        vectorstore = Chroma.from_documents(collection_name="GLOSS_rag", documents=splits, embedding=OpenAIEmbeddings())
        retriever = vectorstore.as_retriever()
        # prompt = hub.pull("rlm/rag-prompt")
        prompt_text = """
        You are an assistant for question-answering tasks for data from various sensors. Use the following pieces of retrieved context to answer the question. Try your besy to answer the questions. If you don't know the answer, just say that you don't know.
        if question is asking for specific information be clear and concise. If question requires answering in detail then provide detailed answer. 
        You can make estimations and intelligent guesses if the exact answer is not available.
        Question: {question} 
        Context: {context} 
        Answer:
        """
        prompt = PromptTemplate.from_template(prompt_text)

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llmchat
                | StrOutputParser()
        )
        return rag_chain


if __name__ == "__main__":
    question = "i wonder if test007 used any apps on 09/12/24"
    response = RAGBasedAgent().invoke_rag_agent({'user_query': question})
    print("----response----")
    print(response)

