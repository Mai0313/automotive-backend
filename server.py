"""Speech-to-speech conversation bot with weather and time functions."""

import os
import argparse

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI
from routers import tts
import uvicorn
from pydantic import BaseModel
from src.llm.prompt import SYSTEM_PROMPT_TEMPLATE
from src.llm.tools.fan import get_fan_speed, set_fan_speed_tool
from fastapi.staticfiles import StaticFiles
from pipecat.services.nim import NimLLMService
from pipecat.frames.frames import LLMMessagesFrame
from pipecat.pipeline.task import PipelineTask, PipelineParams
from src.llm.tools.handler import handle_function
from pipecat.services.openai import OpenAILLMContext
from pipecat.audio.vad.silero import SileroVADAnalyzer
from src.llm.tools.google_map import google_map_tool
from pipecat.pipeline.pipeline import Pipeline
from src.llm.tools.temperature import get_temp, set_temp_tool
from nvidia_pipecat.utils.logging import setup_default_ace_logging

# from src.llm.tools.time import get_current_time
# from src.llm.tools.weather import get_current_weather
from src.llm.tools.front_windshield import front_defrost_on_tool, get_front_defrost_status

# from nvidia_pipecat.services.nvidia_llm import NvidiaLLMService
from nvidia_pipecat.services.riva_speech import RivaASRService, RivaTTSService
from nvidia_pipecat.pipeline.ace_pipeline_runner import PipelineMetadata, ACEPipelineRunner
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

# Uncomment the below lines enable speculative speech processing
# from nvidia_pipecat.processors.nvidia_context_aggregator import (
#     NvidiaTTSResponseCacher,
#     create_nvidia_context_aggregator,
# )
from nvidia_pipecat.processors.transcript_synchronization import UserTranscriptSynchronization
from nvidia_pipecat.transports.network.ace_fastapi_websocket import (
    ACETransport,
    ACETransportParams,
)
from nvidia_pipecat.transports.services.ace_controller.routers.websocket_router import (
    router as websocket_router,
)

setup_default_ace_logging(level="DEBUG")


class EventMessage(BaseModel):
    message: str


active_tasks = {}


async def create_pipeline_task(pipeline_metadata: PipelineMetadata):
    """Create and configure the speech-to-speech pipeline.

    Args:
        pipeline_metadata: Contains websocket and stream configuration

    Returns:
        PipelineTask: Configured pipeline for audio processing
    """
    print(f"🚀 Creating pipeline for stream: {pipeline_metadata.stream_id}")

    # Setup WebSocket transport with VAD
    transport = ACETransport(
        websocket=pipeline_metadata.websocket,
        params=ACETransportParams(
            vad_enabled=True, vad_analyzer=SileroVADAnalyzer(), vad_audio_passthrough=True
        ),
    )
    print("✅ WebSocket transport configured")

    NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

    # Configure services based on API key (local vs cloud)
    if NVIDIA_API_KEY == "local":
        print("🏠 Using local NVIDIA services")
        stt = RivaASRService(
            server=os.getenv("RIVA_ASR_SERVER"),
            api_key=NVIDIA_API_KEY,
            model="parakeet-0.6b-en-US-asr-streaming-throughput-asr-bls-ensemble",
            language="en-US",
            sample_rate=24000,
        )
        tts = RivaTTSService(
            server=os.getenv("RIVA_TTS_SERVER"),
            api_key=NVIDIA_API_KEY,
            language="en-US",
            sample_rate=24000,
        )
        llm = NimLLMService(
            api_key=NVIDIA_API_KEY,
            base_url=os.getenv("VLLM_BASE_URL"),
            model="meta-llama/Llama-3.1-8B-Instruct",
            max_tokens=4096,
        )
    else:
        print("☁️  Using cloud NVIDIA services")
        stt = RivaASRService(
            server="grpc.nvcf.nvidia.com:443",
            api_key=NVIDIA_API_KEY,
            language="en-US",
            sample_rate=24000,
            metadata=[
                ("function-id", "d8dd4e9b-fbf5-4fb0-9dba-8cf436c8d965"),
                ("authorization", f"Bearer {NVIDIA_API_KEY}"),
            ],
        )
        tts = RivaTTSService(
            server="grpc.nvcf.nvidia.com:443",
            api_key=NVIDIA_API_KEY,
            language="en-US",
            sample_rate=24000,
            metadata=[
                ("function-id", "0149dedb-2be8-4195-b9a0-e57e0e14f972"),
                ("authorization", f"Bearer {NVIDIA_API_KEY}"),
            ],
        )
        llm = NimLLMService(api_key=NVIDIA_API_KEY, model="meta/llama-3.1-8b-instruct")

    llm.register_function(None, handle_function)
    print("🤖 LLM configured with function calling")

    # Setup transcript synchronization
    stt_transcript_synchronization = UserTranscriptSynchronization()
    print("📝 Transcript sync enabled")

    # Setup LLM context with system prompt
    SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(
        current_temp=get_temp(),
        current_fan_speed=get_fan_speed(),
        current_front_defrost=get_front_defrost_status(),
    )
    print("System Prompt =\n", SYSTEM_PROMPT)

    # Define available tools for LLM
    # tools = [get_current_weather, get_current_time]
    tools = [front_defrost_on_tool, set_temp_tool, set_fan_speed_tool, google_map_tool]
    print("🔧 Tools registered:", [tool["function"]["name"] for tool in tools])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    context = OpenAILLMContext(messages, tools)
    context_aggregator = llm.create_context_aggregator(context)
    print("💬 LLM context initialized")

    # Build the processing pipeline
    pipeline = Pipeline([
        transport.input(),  # WebSocket input
        stt,  # Speech-to-text
        stt_transcript_synchronization,  # User transcript sync
        context_aggregator.user(),  # User context processing
        llm,  # LLM processing
        tts,  # Text-to-speech
        transport.output(),  # WebSocket output
        context_aggregator.assistant(),  # Assistant context processing
    ])
    print("🔄 Pipeline constructed")

    # Create pipeline task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=False,
            enable_usage_metrics=False,
            send_initial_empty_metrics=False,
            report_only_initial_ttfb=False,
            start_metadata={"stream_id": pipeline_metadata.stream_id},
        ),
    )

    # Register the task with the transport
    active_tasks[pipeline_metadata.stream_id] = task

    # Handle client connections
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        """Initialize conversation when client connects."""
        print("👋 Client connected - starting conversation")
        messages.append({
            "role": "system",
            "content": '''Always Greet with: "Hello, how can I help you today?"''',
        })
        await task.queue_frames([LLMMessagesFrame(messages)])

    # Handle client disconnections
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        """Clean up when client disconnects."""
        print("👋 Client disconnected")
        if pipeline_metadata.stream_id in active_tasks:
            del active_tasks[pipeline_metadata.stream_id]

    print("✨ Pipeline task ready")
    return task


# Initialize FastAPI app
app = FastAPI()
app.include_router(websocket_router)
app.include_router(tts.router)
runner = ACEPipelineRunner(pipeline_callback=create_pipeline_task)

# Serve static files
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
    name="static",
)


# Event API to broadcast messages to all active streams
@app.post("/api/event/broadcast")
async def broadcast_message(event: EventMessage):
    """Broadcast a message to all active streams."""
    if not active_tasks:
        return {"status": "no_active_streams"}

    # Iterate through all active tasks and send the message
    for stream_id, task in active_tasks.items():
        try:
            messages = [
                {
                    "role": "system",
                    "content": f"Please inform the user: {event.message} without any other redundant descriptions.",
                }
            ]
            await task.queue_frames([LLMMessagesFrame(messages)])
        except Exception as e:
            print(f"❌ Error sending to stream {stream_id}: {e}")

    return {"status": "success", "sent_to": len(active_tasks)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the Speech-to-Speech Bot server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the server on.")
    parser.add_argument("--port", type=int, default=8100, help="Port to run the server on.")

    args = parser.parse_args()

    print(f"🎙️  Starting Speech-to-Speech Bot on http://{args.host}:{args.port}")
    print(f"📡 Event API: POST http://{args.host}:{args.port}/api/event/broadcast")
    uvicorn.run(app, host=args.host, port=args.port)
