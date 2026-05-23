import uuid
import json
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from loguru import logger
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from src.backend.core.config import settings
from src.backend.services.agent_service import invoke_agent_async
from src.backend.services.cache_service import cache_service

app = FastAPI(title=settings.api_title, version=settings.api_version, debug=settings.debug)

# --- Metrics Definition ---
REQUEST_COUNT = Counter('request_count', 'Total Request Count', ['method', 'endpoint', 'http_status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency', ['method', 'endpoint'])
WS_CONNECTIONS = Counter('ws_connections', 'Total WebSocket connections', ['status'])

# --- Middlewares ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TraceAndMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        
        with REQUEST_LATENCY.labels(request.method, request.url.path).time():
            response = await call_next(request)
        
        REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
        response.headers["X-Trace-ID"] = trace_id
        return response

app.add_middleware(TraceAndMetricsMiddleware)

# --- Lifespan / Startup ---

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.api_title}...")
    await cache_service.ensure_collection_exists()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {settings.api_title}...")

# --- Endpoints ---

@app.get("/health", tags=["System"])
async def health_check():
    """Liveness probe endpoint."""
    return {"status": "ok", "version": settings.api_version}

@app.get("/metrics", tags=["System"])
async def metrics():
    """Exposes Prometheus metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.websocket("/ws/voice")
async def websocket_endpoint(websocket: WebSocket):
    """
    High-performance full-duplex WebSocket endpoint for voice & text agents.
    """
    trace_id = str(uuid.uuid4())
    await websocket.accept()
    WS_CONNECTIONS.labels("connected").inc()
    logger.info(f"[{trace_id}] WebSocket connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                user_text = message.get("text", "")
                
                if user_text:
                    logger.debug(f"[{trace_id}] Processing query: {user_text}")
                    # Offload to async agent orchestration
                    agent_response = await invoke_agent_async(user_text)
                    
                    response = {
                        "status": "success",
                        "trace_id": trace_id,
                        "agent_response": agent_response
                    }
                    await websocket.send_json(response)
                else:
                    await websocket.send_json({"error": "No text provided in JSON"})
                    
            except json.JSONDecodeError:
                logger.warning(f"[{trace_id}] Received non-JSON data")
                await websocket.send_text("Error: Expected JSON payload")

    except WebSocketDisconnect:
        WS_CONNECTIONS.labels("disconnected").inc()
        logger.info(f"[{trace_id}] WebSocket disconnected")
    except Exception as e:
        WS_CONNECTIONS.labels("error").inc()
        logger.error(f"[{trace_id}] Error in WebSocket connection: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

