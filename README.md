<center>

# Automotive Backend

[![python](https://img.shields.io/badge/-Python_3.10_%7C_3.11_%7C_3.12-blue?logo=python&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![tests](https://github.com/Mai0313/repo_template/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/repo_template/actions/workflows/test.yml)
[![code-quality](https://github.com/Mai0313/repo_template/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/repo_template/actions/workflows/code-quality-check.yml)
[![codecov](https://codecov.io/gh/Mai0313/repo_template/branch/master/graph/badge.svg)](https://codecov.io/gh/Mai0313/repo_template)
[![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/repo_template/tree/master?tab=License-1-ov-file)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/repo_template/pulls)
[![contributors](https://img.shields.io/github/contributors/Mai0313/repo_template.svg)](https://github.com/Mai0313/repo_template/graphs/contributors)

</center>

This demo showcases a speech-to-speech conversation system using NVIDIA's ACE Controller framework. The system supports real-time audio processing, speech recognition, and text-to-speech capabilities.

## Installation

Using `uv`

```bash
cd demo
uv sync
```

Using `conda`

```bash
cd demo
conda create -n poc0 python=3.12
conda activate poc0
conda install uv
uv sync
```

## Components

### Server (`server.py`)

- FastAPI-based WebSocket server
- Integrates with NVIDIA's Riva services for ASR and TTS
- Uses NVIDIA LLM service for conversation
- Supports real-time audio streaming and processing
- Implements VAD (Voice Activity Detection) using Silero

### Client (`client.py`)

- Python-based client for sending WAV files
- Supports WebSocket communication with the server
- Handles audio playback and streaming
- Implements retry mechanisms for reliable communication
- Provides detailed logging and progress tracking

### Web UI (`static/index.html`)

- Browser-based interface for real-time interaction
- Supports microphone input and audio playback
- Uses WebSocket for communication
- Implements Protobuf for data serialization

## Prerequisites

- Python 3.12.9
- NVIDIA API Key (Required if you adopt Nvidia cloud service)

## Setup

1. (Opt) Set up your environment variables in the .env file:

    ```
    NVIDIA_API_KEY=your_nvidia_api_key_here
    ```

2. Install required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Running the Server

```bash
python server.py
```

The server will start on `http://localhost:8100`

### Using the Web UI

1. Open `http://localhost:8100/static/index.html` in your browser
2. Click "Start Audio" to begin the conversation
3. Speak into your microphone
4. Click "Stop Audio" to end the session

### Using the Python Client

```bash
python client.py path/to/your/audio.wav
```
