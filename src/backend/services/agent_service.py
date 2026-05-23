from typing import Annotated, Any, Dict, List, Sequence, TypedDict, Literal
import operator
from loguru import logger

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from src.agents.base.llm_factory import LLMFactory
from src.backend.services.cache_service import cache_service

# --- State Definition ---

class AgentState(TypedDict):
    """Shared state for the LangGraph multi-agent system."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str
    intermediate_steps: Annotated[List[tuple], operator.add]
    final_response: Dict[str, Any]

# --- Schema Definitions ---

class RouterOutput(BaseModel):
    """Schema for the Supervisor to decide the next step."""
    next_agent: Literal["rag_researcher", "json_validator", "FINISH"] = Field(
        ..., description="The next agent to route to, or FINISH if the task is complete."
    )

class ValidatedResponse(BaseModel):
    """Schema for the final validated JSON output."""
    answer: str = Field(..., description="The answer to the user's query.")
    confidence: float = Field(..., description="Confidence score between 0 and 1.")
    sources: List[str] = Field(default_factory=list, description="Sources used to answer.")

# --- Nodes (Agents) ---

async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    The Supervisor determines the next step based on the current conversation state.
    It routes tasks to specialized agents asynchronously.
    """
    logger.info("Supervisor Agent activated")
    
    router_llm = LLMFactory.get_structured_llm(
        pydantic_schema=RouterOutput,
        system_prompt=(
            "You are a Supervisor routing a query. "
            "If the user asks a question requiring external knowledge, route to 'rag_researcher'. "
            "If the researcher has provided information, route to 'json_validator' to format the output. "
            "If the task is fully complete and formatted, output 'FINISH'.\n"
            "{format_instructions}"
        )
    )
    
    last_msg = state["messages"][-1].content
    try:
        # Use ainvoke for non-blocking IO
        decision: RouterOutput = await router_llm.ainvoke({"user_input": last_msg})
        logger.info(f"Supervisor decided to route to: {decision.next_agent}")
        return {"next_agent": decision.next_agent}
    except Exception as e:
        logger.error(f"Supervisor routing failed: {e}")
        return {"next_agent": "FINISH"}

async def rag_researcher_node(state: AgentState) -> Dict[str, Any]:
    """
    RAG Researcher Agent uses the AsyncCacheService (Qdrant) to retrieve context.
    """
    logger.info("RAG Researcher Agent activated")
    last_msg = state["messages"][-1].content
    
    # Perform asynchronous hybrid search
    results = await cache_service.hybrid_search(query=last_msg, top_k=3)
    
    if not results:
        context = "No relevant context found."
    else:
        context = "\n".join([f"- {r['content']}" for r in results])
        
    logger.debug(f"RAG context retrieved: {context}")
    
    response = AIMessage(content=f"Context retrieved:\n{context}")
    return {"messages": [response], "next_agent": "json_validator"}

async def json_validator_node(state: AgentState) -> Dict[str, Any]:
    """
    JSON Validator Agent formats the combined knowledge into a strict JSON schema
    asynchronously using Pydantic constraint validation.
    """
    logger.info("JSON Validator Agent activated")
    
    validator_llm = LLMFactory.get_structured_llm(
        pydantic_schema=ValidatedResponse,
        system_prompt=(
            "You are the Final JSON Validator. Format the conversation into the required schema. "
            "Use the retrieved context to answer the user's initial query.\n"
            "{format_instructions}"
        )
    )
    
    conversation_history = "\n".join([m.content for m in state["messages"]])
    
    try:
        # Use ainvoke for non-blocking IO
        final_output: ValidatedResponse = await validator_llm.ainvoke({"user_input": conversation_history})
        logger.info("JSON Validator successfully generated final structured response")
        return {
            "final_response": final_output.model_dump(),
            "messages": [AIMessage(content="Final response generated.")],
            "next_agent": "FINISH"
        }
    except Exception as e:
        logger.error(f"JSON Validator failed: {e}")
        return {
            "final_response": {"error": "Validation failed", "details": str(e)},
            "next_agent": "FINISH"
        }

# --- Graph Construction ---

def build_agent_graph() -> StateGraph:
    """Compiles the LangGraph StateGraph with async nodes."""
    logger.info("Building async multi-agent StateGraph")
    
    workflow = StateGraph(AgentState)
    
    # Add nodes (they are now async defs)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("rag_researcher", rag_researcher_node)
    workflow.add_node("json_validator", json_validator_node)
    
    # Define edges
    workflow.set_entry_point("supervisor")
    
    def router_condition(state: AgentState) -> str:
        if state["next_agent"] == "FINISH":
            return END
        return state["next_agent"]
        
    workflow.add_conditional_edges(
        "supervisor",
        router_condition,
        {
            "rag_researcher": "rag_researcher",
            "json_validator": "json_validator",
            END: END
        }
    )
    
    workflow.add_edge("rag_researcher", "json_validator")
    workflow.add_edge("json_validator", "supervisor")
    
    compiled_graph = workflow.compile()
    return compiled_graph

# Global instance
agent_graph = build_agent_graph()

async def invoke_agent_async(query: str) -> Dict[str, Any]:
    """Helper method to invoke the graph asynchronously from the API layer."""
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "next_agent": "supervisor",
        "intermediate_steps": [],
        "final_response": {}
    }
    
    result = await agent_graph.ainvoke(initial_state)
    return result.get("final_response", {})

