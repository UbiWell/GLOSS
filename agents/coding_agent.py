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

# Repo root, resolved from this file so it needs no per-machine editing.
# Override with GLOSS_REPO_ROOT if the repo is mounted elsewhere.
REPO_ROOT = os.getenv(
    "GLOSS_REPO_ROOT",
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
)

# Path the HOST docker daemon resolves when bind-mounting the repo into the
# code-execution container. Identical to REPO_ROOT normally, and must stay so
# when GLOSS itself runs inside a container talking to the host's daemon: the
# daemon resolves this path in its own filesystem, not ours, so a container-only
# path would silently mount an empty directory and generated code would find no
# data. Separable via GLOSS_BIND_ROOT if the two ever legitimately differ.
BIND_ROOT = os.getenv("GLOSS_BIND_ROOT", REPO_ROOT)

logger = logging.getLogger(EVENT_LOGGER_NAME)
logger.addHandler(ConsoleLogHandler())
logger.setLevel(logging.INFO)



async def coding_agent(user_query, system_prompt) -> TaskResult:
    # Local Ollama client or OpenAI client, depending on USE_LOCAL_MODEL
    client = get_llm_chat_openai()

    # Path to this repo, mounted into the container that runs generated code
    # auto_remove/stop_container are on so each run cleans up after itself.
    # Left off, every query leaves a stopped autogen-code-exec-* container
    # behind, which fills the disk on a shared host running many instances.
    # timeout defaults to 60s, which generated code that loads a few hundred
    # thousand CSV rows can exceed once several containers compete for CPU.
    # A timeout there surfaces as an apparent code bug, so give it room.
    async with DockerCommandLineCodeExecutor(work_dir=REPO_ROOT,
                                             bind_dir=BIND_ROOT,
                                             image=DOCKER_NAME, auto_remove=True,
                                             stop_container=True,
                                             timeout=int(os.getenv("GLOSS_EXEC_TIMEOUT", "300"))) as code_executor:
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
