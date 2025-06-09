#!/usr/bin/env python3
"""
Client to send WAV file to NVIDIA Pipecat server for transcription.
Uses protobuf format compatible with ACE Transport.
"""

import asyncio
import websockets
import wave
import struct
import json
import sys
import argparse
from pathlib import Path
import uuid
import sounddevice as sd
import numpy as np
from pipecat.frames.frames import OutputAudioRawFrame, StartFrame, SystemFrame, EndFrame
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.clocks.system_clock import SystemClock
from pipecat.utils.asyncio import TaskManager


class WAVClient:
    def __init__(self, server_url: str = "ws://localhost:8100/ws"):
        self.server_url = server_url
        self.websocket = None
        self.stream_id = str(uuid.uuid4())
        self.serializer = ProtobufFrameSerializer()
        self.clock = SystemClock()
        self.task_manager = TaskManager()
        self.SAMPLE_RATE = 16000
        self.NUM_CHANNELS = 1
        self.audio_queue = asyncio.Queue()
        self.is_playing = False

    async def connect(self):
        """Connect to the WebSocket server with proper ACE headers"""
        try:
            # Headers that ACE transport might expect
            headers = {
                "Origin": "http://localhost:8100",
                "User-Agent": "ACE-Client/1.0",
                "Sec-WebSocket-Protocol": "ace-transport",
            }

            # Use stream_id in the URL path
            websocket_url = f"{self.server_url}/{self.stream_id}"
            print(f"Attempting to connect to {websocket_url} with headers: {headers}")

            self.websocket = await websockets.connect(
                websocket_url,
                extra_headers=headers,
                subprotocols=["ace-transport"],
                ping_interval=20,
                ping_timeout=10,
                max_size=None,
                max_queue=None,
            )
            print(f"Successfully connected to {websocket_url}")

            # Send system frame
            system_frame = SystemFrame()
            print("Creating system frame...")
            await self.serializer.setup(system_frame)
            payload = await self.serializer.serialize(system_frame)
            if payload:
                print(f"Sending system frame of size {len(payload)} bytes")
                await self.websocket.send(payload)
                print("System frame sent successfully")
            else:
                print("Failed to serialize system frame")

        except Exception as e:
            print(f"Failed to connect to {websocket_url}: {e}")
            print("Trying without subprotocol...")

            try:
                # Try without subprotocol
                headers = {"Origin": "http://localhost:8100", "User-Agent": "ACE-Client/1.0"}

                self.websocket = await websockets.connect(
                    websocket_url, extra_headers=headers, ping_interval=20, ping_timeout=10
                )
                print(f"Connected to {websocket_url} (without subprotocol)")

                # Send system frame
                system_frame = SystemFrame()
                await self.serializer.setup(system_frame)
                payload = await self.serializer.serialize(system_frame)
                if payload:
                    await self.websocket.send(payload)
                    print("System frame sent successfully")
                else:
                    print("Failed to serialize system frame")

            except Exception as e2:
                print(f"Connection failed: {e2}")
                raise

    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            print("Disconnected from server")

    def read_wav_file(self, file_path: str):
        """Read and validate WAV file"""
        if not Path(file_path).exists():
            raise FileNotFoundError(f"WAV file not found: {file_path}")

        try:
            with wave.open(file_path, "rb") as wav_file:
                # Get WAV file properties
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()

                print(f"WAV file info:")
                print(f"  Sample rate: {sample_rate} Hz")
                print(f"  Channels: {channels}")
                print(f"  Sample width: {sample_width} bytes")
                print(f"  Duration: {frames / sample_rate:.2f} seconds")

                # Read all audio data
                audio_data = wav_file.readframes(frames)

                return {
                    "audio_data": audio_data,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "sample_width": sample_width,
                    "duration": frames / sample_rate,
                }
        except Exception as e:
            raise Exception(f"Error reading WAV file: {e}")

    def resample_if_needed(self, audio_info):
        """Resample audio to 16kHz if needed (simple approach)"""
        if audio_info["sample_rate"] != self.SAMPLE_RATE:
            print(f"Warning: Server expects {self.SAMPLE_RATE}Hz, but file is {audio_info['sample_rate']}Hz")
            print("Consider resampling your audio file to 16kHz for better results")
            # Note: For production use, implement proper resampling with librosa or scipy
        return audio_info

    async def send_audio_chunks(self, audio_data: bytes, chunk_size: int = 1024):
        """Send audio data in chunks using protobuf format"""
        total_chunks = len(audio_data) // chunk_size
        print(f"\n🎵 Starting audio streaming...")
        print(f"📊 Total chunks to send: {total_chunks}")
        print(f"📦 Chunk size: {chunk_size} bytes")
        print(f"📈 Total data size: {len(audio_data)} bytes")

        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i : i + chunk_size]
            current_chunk = i // chunk_size + 1

            # Calculate and display progress
            progress = (current_chunk / total_chunks) * 100
            print(f"\r🔄 Progress: {progress:.1f}% ({current_chunk}/{total_chunks})", end="")

            # Create audio frame
            audio_frame = OutputAudioRawFrame(audio=chunk, sample_rate=self.SAMPLE_RATE, num_channels=self.NUM_CHANNELS)

            # Serialize and send with retry mechanism
            max_retries = 3
            for retry in range(max_retries):
                try:
                    await self.serializer.setup(audio_frame)
                    payload = await self.serializer.serialize(audio_frame)

                    if payload:
                        await self.websocket.send(payload)
                        break  # Success, exit retry loop
                    else:
                        print(f"\n⚠️ Failed to serialize chunk {current_chunk}, attempt {retry + 1}/{max_retries}")
                        if retry == max_retries - 1:
                            print(f"❌ Failed to send chunk {current_chunk} after {max_retries} attempts")
                except Exception as e:
                    print(f"\n⚠️ Error sending chunk {current_chunk}, attempt {retry + 1}/{max_retries}: {e}")
                    if retry == max_retries - 1:
                        print(f"❌ Failed to send chunk {current_chunk} after {max_retries} attempts")
                    await asyncio.sleep(0.1)  # Small delay before retry

            # Adaptive delay based on chunk size
            delay = min(0.05, chunk_size / (self.SAMPLE_RATE * self.NUM_CHANNELS * 2))
            await asyncio.sleep(delay)

        print("\n✅ Audio streaming completed")

    async def play_audio(self, audio_data: bytes):
        """Play audio data using sounddevice"""
        try:
            print(f"\n🔊 Playing audio of size: {len(audio_data)} bytes")
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            print(f"   Converted to numpy array of shape: {audio_array.shape}")
            # Normalize to float32
            audio_float = audio_array.astype(np.float32) / 32768.0
            print(f"   Normalized to float32 array of shape: {audio_float.shape}")

            # Play audio
            print("   Starting playback...")
            sd.play(audio_float, self.SAMPLE_RATE)
            sd.wait()  # Wait until audio is finished playing
            print("   Playback completed")
        except Exception as e:
            print(f"\n⚠️ Error playing audio: {e}")
            print(f"   Audio data type: {type(audio_data)}")
            print(f"   Audio data length: {len(audio_data)}")

    async def audio_player_task(self):
        """Background task to play audio from queue"""
        while True:
            try:
                audio_data = await self.audio_queue.get()
                if audio_data is None:  # Shutdown signal
                    break
                await self.play_audio(audio_data)
                self.audio_queue.task_done()
            except Exception as e:
                print(f"\n⚠️ Error in audio player task: {e}")

    async def listen_for_responses(self):
        """Listen for server responses (transcriptions)"""
        try:
            print("\n🎧 Waiting for transcription results...")
            response_count = 0
            async for message in self.websocket:
                if isinstance(message, bytes):
                    try:
                        print(f"\n📦 Received binary message of size: {len(message)} bytes")
                        frame = await self.serializer.deserialize(message)
                        if frame:
                            frame_type = frame.__class__.__name__
                            response_count += 1

                            # Handle different frame types with detailed logging
                            if frame_type == "TranscriptionFrame":
                                print(f"\n🎯 Transcription #{response_count}:")
                                print(f"   Text: {frame.text}")
                                if hasattr(frame, "confidence"):
                                    print(f"   Confidence: {frame.confidence:.2f}")
                            elif frame_type == "TextFrame":
                                print(f"\n📄 Text Message #{response_count}:")
                                print(f"   Content: {frame.text}")
                            elif frame_type == "OutputAudioRawFrame":
                                print(f"\n🔊 Audio Response #{response_count}:")
                                print(f"   Size: {len(frame.audio)} bytes")
                                print(f"   Sample Rate: {frame.sample_rate} Hz")
                                print(f"   Channels: {frame.num_channels}")
                                print(f"   Audio data type: {type(frame.audio)}")
                                # Add audio to playback queue
                                await self.audio_queue.put(frame.audio)
                            else:
                                print(f"\n📝 Other Frame #{response_count}:")
                                print(f"   Type: {frame_type}")
                                print(f"   Attributes: {dir(frame)}")

                    except Exception as e:
                        print(f"\n⚠️ Error processing response: {e}")
                        print(f"   Message type: {type(message)}")
                        print(f"   Message length: {len(message)}")
                else:
                    print(f"\n📨 Text Message: {message}")

        except websockets.exceptions.ConnectionClosed:
            print("\n🔌 Connection closed by server")
        except Exception as e:
            print(f"\n❌ Error receiving responses: {e}")

    async def process_wav_file(self, file_path: str):
        """Main method to process WAV file"""
        try:
            # Read WAV file
            print(f"Reading WAV file: {file_path}")
            audio_info = self.read_wav_file(file_path)

            # Check and resample if needed
            audio_info = self.resample_if_needed(audio_info)

            # Connect to server
            await self.connect()

            # Start audio player task
            audio_player = asyncio.create_task(self.audio_player_task())

            # Start listening for responses in background
            listen_task = asyncio.create_task(self.listen_for_responses())

            # Send audio data
            print("Sending audio data to server...")
            await self.send_audio_chunks(audio_info["audio_data"])

            # Wait a bit for final responses
            print("Waiting for final responses...")
            await asyncio.sleep(2)

            # Signal audio player to stop
            await self.audio_queue.put(None)

            # Cancel tasks
            listen_task.cancel()
            audio_player.cancel()

        except Exception as e:
            print(f"Error processing WAV file: {e}")
        finally:
            await self.disconnect()


async def main():
    parser = argparse.ArgumentParser(description="Send WAV file to NVIDIA Pipecat server")
    parser.add_argument("wav_file", help="Path to WAV file")
    parser.add_argument(
        "--server", default="ws://localhost:8100/ws", help="WebSocket server URL (default: ws://localhost:8100/ws)"
    )

    args = parser.parse_args()

    if not args.wav_file:
        print("Usage: python wav_client.py <wav_file_path>")
        sys.exit(1)

    client = WAVClient(args.server)
    await client.process_wav_file(args.wav_file)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
