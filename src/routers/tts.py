"""Streaming TTS WebSocket Router - Real-time character-by-character TTS."""

import os
import json
from typing import Optional
import logging

import dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from nvidia_pipecat.services.riva_speech import RivaTTSService, TTSAudioRawFrame

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

# Create router
router = APIRouter()


class StreamingTTSHandler:
    def __init__(self):
        self.tts_service = None
        self.buffer = ""  # 累積的文字緩衝區
        self.last_sent_length = 0  # 已經轉換的文字長度
        self.sentence_endings = {".", "!", "?", "。", "！", "？"}  # 句子結束標點
        self.pause_chars = {",", ";", "，", "；", "\n"}  # 需要暫停的標點
        self.min_chunk_length = 3  # 最小處理塊長度（字符數）

    async def get_tts_service(self) -> RivaTTSService:
        """Get or create TTS service."""
        nvidia_api_key = os.getenv("NVIDIA_API_KEY", "local")
        if self.tts_service is None:
            if nvidia_api_key == "local":
                logger.info("🏠 Using local NVIDIA TTS service")
                self.tts_service = RivaTTSService(
                    server=os.getenv("RIVA_TTS_SERVER"),
                    api_key=nvidia_api_key,
                    language="en-US",
                    sample_rate=16000,
                )
            else:
                logger.info("☁️ Using cloud NVIDIA TTS service")
                self.tts_service = RivaTTSService(
                    server="grpc.nvcf.nvidia.com:443",
                    api_key=nvidia_api_key,
                    language="en-US",
                    sample_rate=16000,
                    metadata=[
                        ("function-id", "0149dedb-2be8-4195-b9a0-e57e0e14f972"),
                        ("authorization", f"Bearer {nvidia_api_key}"),
                    ],
                )
        return self.tts_service

    def should_process_chunk(self, text: str) -> bool:
        """判斷是否應該處理當前文字塊."""
        # 如果遇到句子結束標點，立即處理
        if any(char in self.sentence_endings for char in text):
            return True

        # 如果遇到暫停標點且長度足夠，處理
        if any(char in self.pause_chars for char in text) and len(text) >= self.min_chunk_length:
            return True

        # 如果累積的文字長度達到最小處理長度
        return len(text) >= self.min_chunk_length * 2

    def extract_processable_text(self) -> Optional[str]:
        """從緩衝區提取可處理的文字."""
        if len(self.buffer) <= self.last_sent_length:
            return None

        # 獲取新增的文字
        new_text = self.buffer[self.last_sent_length :]

        # 檢查是否應該處理
        if not self.should_process_chunk(new_text):
            return None

        # 找到最佳切割點
        cut_point = len(new_text)

        # 如果包含句子結束標點，在標點後切割
        for i, char in enumerate(new_text):
            if char in self.sentence_endings:
                cut_point = i + 1
                break

        # 如果包含暫停標點，在適當位置切割
        if cut_point == len(new_text):
            for i, char in enumerate(new_text):
                if char in self.pause_chars and i >= self.min_chunk_length:
                    cut_point = i + 1
                    break

        # 提取要處理的文字
        text_to_process = new_text[:cut_point].strip()

        if text_to_process:
            self.last_sent_length += cut_point
            return text_to_process

        return None

    async def process_streaming_text(self, new_text: str, websocket: WebSocket) -> None:
        """處理流式文字輸入."""
        # 添加新文字到緩衝區
        self.buffer += new_text
        logger.debug(f"📝 Buffer updated: '{self.buffer}' (length: {len(self.buffer)})")

        # 提取可處理的文字
        text_to_process = self.extract_processable_text()

        if text_to_process:
            logger.info(f"🔊 Processing TTS for: '{text_to_process}'")

            try:
                # 生成語音
                tts_service = await self.get_tts_service()
                audio_generator = tts_service.run_tts(text=text_to_process)

                chunk_count = 0
                async for chunk in audio_generator:
                    if isinstance(chunk, TTSAudioRawFrame):
                        # 立即發送音頻塊
                        await websocket.send_bytes(chunk.audio)
                        chunk_count += 1

                # 發送處理完成通知
                await websocket.send_text(
                    json.dumps({
                        "type": "chunk_complete",
                        "text": text_to_process,
                        "chunks": chunk_count,
                        "buffer_length": len(self.buffer),
                        "processed_length": self.last_sent_length,
                    })
                )

                logger.info(f"✅ Sent {chunk_count} audio chunks for: '{text_to_process}'")

            except Exception as e:
                logger.error(f"❌ TTS processing error: {e}")
                await websocket.send_text(
                    json.dumps({"type": "error", "error": str(e), "text": text_to_process})
                )

    async def flush_remaining_text(self, websocket: WebSocket) -> None:
        """處理緩衝區中剩餘的文字."""
        if len(self.buffer) > self.last_sent_length:
            remaining_text = self.buffer[self.last_sent_length :].strip()
            if remaining_text:
                logger.info(f"🔄 Flushing remaining text: '{remaining_text}'")

                try:
                    tts_service = await self.get_tts_service()
                    audio_generator = tts_service.run_tts(text=remaining_text)

                    chunk_count = 0
                    async for chunk in audio_generator:
                        if isinstance(chunk, TTSAudioRawFrame):
                            await websocket.send_bytes(chunk.audio)
                            chunk_count += 1

                    await websocket.send_text(
                        json.dumps({
                            "type": "flush_complete",
                            "text": remaining_text,
                            "chunks": chunk_count,
                        })
                    )

                    self.last_sent_length = len(self.buffer)

                except Exception as e:
                    logger.error(f"❌ Error flushing text: {e}")
                    await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))

    def reset(self) -> None:
        """重置處理器狀態."""
        self.buffer = ""
        self.last_sent_length = 0
        logger.info("🔄 TTS handler reset")


# 為每個WebSocket連接創建獨立的處理器
active_handlers: dict[WebSocket, StreamingTTSHandler] = {}


@router.websocket("/tts")
async def websocket_streaming_tts(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming TTS service."""
    await websocket.accept()
    logger.info("👋 Client connected to Streaming TTS WebSocket")

    # 為這個連接創建處理器
    handler = StreamingTTSHandler()
    active_handlers[websocket] = handler

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"📨 Received: {data}")

            try:
                # 解析消息
                if data.startswith("{"):
                    message = json.loads(data)
                    message_type = message.get("type", "text")

                    if message_type == "text":
                        # 處理新的文字輸入
                        text = message.get("text", "")
                        if text:
                            await handler.process_streaming_text(text, websocket)

                    elif message_type == "flush":
                        # 強制處理剩餘文字
                        await handler.flush_remaining_text(websocket)

                    elif message_type == "reset":
                        # 重置處理器
                        handler.reset()
                        await websocket.send_text(json.dumps({"type": "reset_complete"}))

                    else:
                        await websocket.send_text(
                            json.dumps({
                                "type": "error",
                                "error": f"Unknown message type: {message_type}",
                            })
                        )

                else:
                    # 直接文字輸入
                    await handler.process_streaming_text(data, websocket)

            except json.JSONDecodeError as e:
                # 如果不是JSON，當作純文字處理
                await handler.process_streaming_text(data, websocket)
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}")
                await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))

    except WebSocketDisconnect:
        logger.info("👋 Client disconnected from Streaming TTS WebSocket")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
    finally:
        # 清理處理器
        active_handlers.pop(websocket, None)


@router.get("/tts/info")
async def streaming_tts_info():
    """Get streaming TTS service information."""
    return {
        "service": "NVIDIA Riva Streaming TTS",
        "websocket_endpoint": "/tts",
        "features": [
            "Real-time character-by-character TTS",
            "Intelligent text chunking",
            "Streaming audio output",
            "Buffer management",
        ],
        "message_types": {
            "text": {"type": "text", "text": "Your streaming text here"},
            "flush": {"type": "flush"},
            "reset": {"type": "reset"},
        },
        "usage_example": {
            "description": "Send streaming text chunks as they arrive from chat completion",
            "example": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": " world"},
                {"type": "text", "text": "!"},
                {"type": "flush"},
            ],
        },
    }
