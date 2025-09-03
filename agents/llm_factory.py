"""
Factory module to create and configure LLM chat instances based on environment settings.
"""

import os

import langchain_openai as lcai
from autogen_ext.models._openai._openai_client import OpenAIChatCompletionClient
from langchain_openai import ChatOpenAI

from agents.config import USE_AZURE, USE_GPT5


def get_llmchat():
    """Return a configured chat LLM instance based on config flags.

    Priority:
    - If USE_GPT_OSS: return GPTOSSChatModel
    - Else if USE_GPT5: return OpenAI gpt-5
    - Else if USE_AZURE: return AzureChatOpenAI gpt-4o
    - Else: return OpenAI gpt-4o
    """
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


def get_llm_chat_openai(model_name: str = "gpt-4o", temperature: float = 0):
    """Return a configured OpenAI chat LLM instance.
    
    Args:
        model_name (str): The OpenAI model to use (default: "gpt-4o")
        temperature (float): The temperature for generation (default: 0)
    
    Returns:
        ChatOpenAI: Configured OpenAI chat model instance
        
    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    return OpenAIChatCompletionClient(
        openai_api_key=openai_api_key,
        model=model_name,
        temperature=temperature
    )
