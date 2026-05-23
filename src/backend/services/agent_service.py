from typing import Annotated, Any, Dict, List, Sequence, TypedDict, Literal
import operator
from loguru import logger

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # Note: Use PostgresSaver for production
from langchain_core.tools import tool

from src.agents.base.llm_factory import LLMFactory
from src.backend.services.cache_service import cache_service

# --- 1. Define Autonomous Tools ---
@tool
async def search_knowledge_base(query: str) -> str:
    """Searches the vector database for relevant company or medical policies."""
    results = await cache_service.hybrid_search(query=query, top_k=3)
    if not results:
        return "No relevant context found."
    return "\n".join([f"- {r['content']}" for r in results])

# --- 2. Upgraded Nodes ---
async def rag_researcher_node(state: dict) -> Dict[str, Any]:
    """Autonomous RAG agent that actively decides how to use tools."""
    logger.info("RAG Researcher Agent activated")
    
    # Bind the tool to the LLM
    llm = LLMFactory.get_llm().bind_tools([search_knowledge_base])
    
    # Let the LLM decide if it needs to search, or just answer
    response = await llm.ainvoke(state["messages"])
    
    # If the LLM decided to call a tool, execute it
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "search_knowledge_base":
                tool_result = await search_knowledge_base.invoke(tool_call["args"])
                # Append tool result to state
                return {"messages": [response, ToolMessage(content=tool_result, tool_call_id=tool_call["id"])]}
                
    return {"messages": [response], "next_agent": "json_validator"}

# --- 3. Add Persistence to Graph ---
def build_agent_graph() -> StateGraph:
    # ... (Keep existing nodes and edges) ...
    
    # Add a checkpointer to persist state across WebSocket disconnects
    memory = MemorySaver() 
    compiled_graph = workflow.compile(checkpointer=memory)
    return compiled_graph

agent_graph = build_agent_graph()

# --- 4. Thread-Aware Invocation ---
async def invoke_agent_async(query: str, trace_id: str, thread_id: str) -> str:
    """Invokes graph with memory tracking via thread_id."""
    # We no longer pass initial state on every turn; we just append the new message
    config = {
        "configurable": {"thread_id": thread_id}, # Links this request to past memory
        "callbacks": [langfuse_handler] # Assumes Langfuse is configured
    }
    
    result = await agent_graph.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        config=config
    )
    
    # Extract the final string response for the TTS engine
    return result["messages"][-1].content