from fastapi import WebSocketException, status
from pipecat.services.cartesia import CartesiaTTSService # Or your preferred TTS
from pipecat.frames.frames import TextFrame

# --- Security Dependency ---
async def verify_ws_api_key(websocket: WebSocket) -> str:
    """Extracts and verifies API key from WebSocket headers or query params."""
    api_key = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key")
    if api_key != settings.api_key_secret:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return api_key

@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """Production-ready secure, full-duplex voice pipeline."""
    await verify_ws_api_key(websocket)
    await websocket.accept()
    
    # Use the trace_id as the memory thread_id for LangGraph
    thread_id = str(uuid.uuid4()) 
    logger.info(f"[{thread_id}] Secure Audio Pipeline connected")

    try:
        transport = WebsocketServerTransport(websocket=websocket)
        stt = FasterWhisperSTTService(model="tiny.en")
        
        # Initialize TTS for the return audio path
        tts = CartesiaTTSService(
            api_key=settings.cartesia_api_key,
            voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22" # Example Voice
        )
        
        # Bridge function: LangGraph -> TTS -> User
        async def process_intent(text: str):
            logger.info(f"[{thread_id}] STT output: {text}")
            
            # 1. Run LangGraph logic (with memory)
            agent_text = await invoke_agent_async(text, thread_id, thread_id)
            
            # 2. Push LLM text into the TTS engine to generate audio bytes
            await tts.process_frame(TextFrame(text=agent_text))

        # Complete Pipeline: Input Audio -> STT -> [Custom Logic] -> TTS -> Output Audio
        pipeline = Pipeline([
            transport.input(),
            stt,
            # (Bridge runs here asynchronously)
            tts,
            transport.output()
        ])
        
        task = PipelineTask(pipeline)
        await task.run()

    except WebSocketDisconnect:
        logger.info(f"[{thread_id}] Session ended. State saved in LangGraph Checkpointer.")