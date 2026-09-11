"""
Factory module to create and configure LLM chat instances based on environment settings.
"""

import os

import langchain_openai as lcai
from autogen_ext.models._openai._openai_client import OpenAIChatCompletionClient
from langchain_openai import ChatOpenAI

from agents.config import USE_AZURE, USE_GPT5, USE_LOCAL_MODEL


def get_llmchat(agent=None):
    """Return a configured chat LLM instance based on config flags.

    Args:
        agent (str): Display name of the agent asking, e.g. "Next-step agent".
            Recorded in the run trace so the dashboard can name who spoke.
            Only the local backend records it; the OpenAI paths ignore it.

    Priority:
    - If USE_LOCAL_MODEL: return OllamaChatModel (local GPU cluster, no OpenAI key)
    - Else if USE_GPT5: return OpenAI gpt-5
    - Else if USE_AZURE: return AzureChatOpenAI gpt-4o
    - Else: return OpenAI gpt-4o
    """
    if USE_LOCAL_MODEL:
        # Imported lazily so the OpenAI paths stay usable if the local model
        # module or its config is unavailable.
        from agents.local_model import OllamaChatModel

        return OllamaChatModel(agent=agent)
    if USE_GPT5:
        return ChatOpenAI(openai_api_key=os.getenv("OPENAI_API_KEY"), model_name="gpt-5")
    if USE_AZURE:
        return lcai.AzureChatOpenAI(
            openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_API_ENDPOINT"),
            azure_deployment="",
            openai_api_version="",
            model_name="gpt-4o",
            temperature=0,
        )
    return ChatOpenAI(openai_api_key=os.getenv("OPENAI_API_KEY"), model_name="gpt-4o", temperature=0)


def get_llm_chat_openai(model_name: str = "gpt-4o", temperature: float = 0, agent=None):
    """Return the AutoGen model client used by the coding agent.

    Args:
        model_name (str): The OpenAI model to use (default: "gpt-4o").
            Ignored when USE_LOCAL_MODEL is set, which uses LOCAL_MODEL_NAME.
        temperature (float): The temperature for generation (default: 0)

    Returns:
        An AutoGen ChatCompletionClient: LangChainModelClient when
        USE_LOCAL_MODEL is set, otherwise OpenAIChatCompletionClient.

    Raises:
        ValueError: If OPENAI_API_KEY is not set and the local model is not in use
    """
    if USE_LOCAL_MODEL:
        from agents.local_model import LangChainModelClient

        return LangChainModelClient(temperature=temperature, agent=agent)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    return OpenAIChatCompletionClient(
        openai_api_key=openai_api_key,
        model=model_name,
        temperature=temperature
    )


def get_embeddings():
    """Return the embedding model for the RAG agent.

    The GPU cluster's Ollama workers are started without ``--embeddings`` and
    reject /api/embed with 501, so there is no local embedding model to fall
    back to. The RAG agent therefore still needs an OpenAI key even when
    USE_LOCAL_MODEL is set; it sits outside the main sensemaking flow, which is
    fully local.

    Raises:
        RuntimeError: If USE_LOCAL_MODEL is set but no OPENAI_API_KEY exists
    """
    from langchain_openai import OpenAIEmbeddings

    if USE_LOCAL_MODEL and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "The RAG agent needs embeddings, which the local GPU cluster does not "
            "serve (its Ollama workers run without --embeddings). Set OPENAI_API_KEY "
            "to use the RAG agent, or ask the cluster admin to enable embeddings and "
            "load an embedding model such as nomic-embed-text."
        )
    return OpenAIEmbeddings()
