"""
This file defines a coding agent that can execute code based on user queries and
system prompts in docker container.
"""

import asyncio
import logging
from autogen_agentchat import EVENT_LOGGER_NAME
from autogen_agentchat.agents import CodeExecutorAgent, CodingAssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.logging import ConsoleLogHandler
from autogen_agentchat.teams import RoundRobinGroupChat, StopMessageTermination
from autogen_ext.code_executor.docker_executor import DockerCommandLineCodeExecutor

import sys
import os

from agents.llm_factory import get_llm_chat_openai

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.agent_utils import generate_code_generation_prompt
from agents.config import DOCKER_NAME

logger = logging.getLogger(EVENT_LOGGER_NAME)
logger.addHandler(ConsoleLogHandler())
logger.setLevel(logging.INFO)



async def coding_agent(user_query, system_prompt) -> TaskResult:
    from autogen_ext.models import AzureOpenAIChatCompletionClient
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    # Create the token provider
    client = get_llm_chat_openai()

    async with DockerCommandLineCodeExecutor(work_dir="/Users/akshat/Desktop/Akshat/research/repos/llm-sensemaking/",
                                             image="sensemaking-code", auto_remove=False,
                                             stop_container=False) as code_executor:
        code_executor_agent = CodeExecutorAgent("code_executor", code_executor=code_executor)
        coding_assistant_agent = CodingAssistantAgent(
            "coding_assistant", model_client=client, system_message=system_prompt
        )
        group_chat = RoundRobinGroupChat([coding_assistant_agent, code_executor_agent])

        # Run task and store result in a variable
        result = await group_chat.run(
            task=user_query,
            termination_condition=StopMessageTermination(),
        )

    return result  # Return result of async call

def run_coding_agent(user_query, database, functions, include_statements, function_imports):
    system_prompt = generate_code_generation_prompt(req_databases=database, functions=functions, include_statements=include_statements, function_imports=function_imports)
    results = asyncio.run(coding_agent(user_query, system_prompt))
    return results
