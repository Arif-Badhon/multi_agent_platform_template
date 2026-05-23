from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Centralized configuration management for the Voice AI Agent.
    Values can be overridden by environment variables or a .env file.
    """
    
    # API & App Settings
    api_title: str = "Voice AI Agent API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Settings
    cors_origins: list[str] = ["*"]
    
    # Qdrant Database
    qdrant_location: str = ":memory:" # Use ":memory:" for local testing or "http://qdrant:6333" for prod
    qdrant_collection: str = "voice_ai_docs"
    
    # LLM Settings
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    llm_temperature: float = 0.0
    
    # Redis/Caching (Optional for future scale)
    redis_url: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global settings instance
settings = Settings()
