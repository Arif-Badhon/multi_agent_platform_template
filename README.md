# Voice AI Agent

Real-time, offline, multi-agent voice AI architecture optimized for Apple Silicon.

## Architecture
- **Core Infrastructure**: FastAPI + WebSockets
- **Orchestration**: LangGraph StateGraph (Supervisor, RAG Researcher, JSON Validator)
- **LLM Engine**: Local ChatOllama (Llama 3.2 / Mistral 7B) with Pydantic validation
- **Data Layer**: Qdrant Vector Store with hybrid search
