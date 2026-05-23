from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableRetry
from loguru import logger

from src.backend.core.config import settings

T = TypeVar("T", bound=BaseModel)

class LLMFactory:
    """
    Factory for instantiating local LLMs using Ollama.
    Configured via central settings with built-in resilience.
    """
    
    @staticmethod
    def get_llm(model_name: Optional[str] = None, temperature: Optional[float] = None, **kwargs: Any) -> ChatOllama:
        """
        Returns a ChatOllama instance connected to the configured base URL.
        """
        name = model_name or settings.llm_model
        temp = temperature if temperature is not None else settings.llm_temperature
        
        logger.info(f"Instantiating local LLM: {name} with temperature {temp} at {settings.ollama_base_url}")
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=name,
            temperature=temp,
            **kwargs
        )
    
    @staticmethod
    def get_structured_llm(
        pydantic_schema: Type[T],
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None
    ):
        """
        Creates an LLM chain that enforces strict JSON schema outputs using Pydantic constraint validation.
        Includes built-in retry mechanisms for resilience against transient model failures.
        """
        llm = LLMFactory.get_llm(model_name=model_name, temperature=temperature, format="json")
        parser = PydanticOutputParser(pydantic_object=pydantic_schema)
        
        # Default system prompt if none provided
        if not system_prompt:
            system_prompt = (
                "You are a helpful AI assistant. "
                "You must output ONLY valid JSON that strictly adheres to the provided schema.\n"
                "{format_instructions}"
            )
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{user_input}")
        ])
        
        prompt = prompt.partial(format_instructions=parser.get_format_instructions())
        
        logger.debug(f"Created structured LLM chain for schema: {pydantic_schema.__name__}")
        
        # Combine into a runnable chain and add retry wrapper
        chain = prompt | llm | parser
        
        # Add resilience: Retry up to 3 times with exponential backoff if output parsing fails
        resilient_chain = chain.with_retry(
            stop_after_attempt=3,
            wait_exponential_jitter=True
        )
        return resilient_chain

