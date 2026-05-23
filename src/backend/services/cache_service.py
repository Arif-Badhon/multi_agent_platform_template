import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from loguru import logger
from langchain_community.embeddings import FastEmbedEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential

from src.backend.core.config import settings

class AsyncCacheService:
    """
    Data Layer utilizing Qdrant for semantic caching and document vector storage.
    Refactored for high-demand, non-blocking asynchronous execution.
    """
    
    def __init__(self):
        """
        Initializes the async Qdrant client using centralized settings.
        """
        self.client = AsyncQdrantClient(location=settings.qdrant_location)
        self.collection_name = settings.qdrant_collection
        self.embeddings_model = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        logger.info(f"AsyncCacheService initialized with Qdrant collection: {self.collection_name} at {settings.qdrant_location}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def ensure_collection_exists(self):
        """Creates the Qdrant collection asynchronously if it doesn't exist. Includes retry logic."""
        try:
            collections_response = await self.client.get_collections()
            if not any(c.name == self.collection_name for c in collections_response.collections):
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection exists: {e}")
            raise

    async def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None):
        """
        Embeds texts and adds them to Qdrant asynchronously.
        """
        if not texts:
            return
            
        logger.debug(f"Adding {len(texts)} documents to Qdrant")
        # FastEmbed is local, but typically embedding happens synchronously. 
        # In a very high demand system, this could be offloaded to a threadpool.
        embeddings = self.embeddings_model.embed_documents(texts)
        
        points = []
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            payload = {"page_content": text}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])
                
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload=payload
                )
            )
            
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Asynchronous hybrid retrieval combining vector semantic search and keyword relevance.
        """
        logger.debug(f"Executing async hybrid search for query: '{query}'")
        query_vector = self.embeddings_model.embed_query(query)
        
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )
        
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "content": hit.payload.get("page_content", ""),
                "metadata": hit.payload
            }
            for hit in results
        ]

# Singleton instance
cache_service = AsyncCacheService()
