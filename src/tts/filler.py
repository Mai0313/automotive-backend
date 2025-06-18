import random
import time

from pipecat.frames.frames import TTSSpeakFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class FillerProcessor(FrameProcessor):
    """Processor that provides immediate acknowledgment responses to user speech."""

    def __init__(self):
        super().__init__()
        self._last_filler_time = 0
        self._min_filler_interval = 2.0  # Minimum seconds between fillers

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        # Only process transcription frames going downstream (from STT)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TranscriptionFrame):
            if frame.text and frame.text.strip():
                current_time = time.time()

                # Throttle fillers to avoid overwhelming the user
                if current_time - self._last_filler_time > self._min_filler_interval:
                    self._last_filler_time = current_time

                    # Generate contextual acknowledgment
                    acknowledgment = self._get_contextual_acknowledgment(frame.text)

                    # Send the filler immediately
                    await self.push_frame(TTSSpeakFrame(acknowledgment))

        # Always pass the original frame through
        await self.push_frame(frame, direction)

    def _get_contextual_acknowledgment(self, text: str) -> str:
        """Generate context-aware acknowledgment based on user input."""
        text_lower = text.lower()

        # Context-aware acknowledgments
        if any(
            word in text_lower
            for word in [
                "temperature",
                "temp",
                "hot",
                "cold",
                "climate",
                " ac ",
                "warmer",
                "cooler",
                "heat",
                "cool",
                "air conditioning",
                "a/c",
                "aircon",
                "air con",
            ]
        ):
            return random.choice([
                "Let me check the temperature.",
                "I'll look into the temperature settings.",
                "Just a second, checking temp.",
                "Let me adjust that for you.",
                "Hang tight, I'm on it.",
                "One moment, please.",
                "Let me take a quick look.",
                "Checking temperature now.",
                "Give me a moment.",
            ])
        elif any(
            word in text_lower
            for word in ["fan", "air", "blow", "blower", "windy", "breeze", "airflow"]
        ):
            return random.choice([
                "I'll adjust the fan for you.",
                "Let me help with the airflow.",
                "Adjusting the air now.",
                "One sec, working on it.",
                "Fan settings coming up.",
                "Making the air better.",
                "Got it, changing airflow.",
                "I'll get on that.",
            ])
        elif any(
            word in text_lower
            for word in ["defrost", "windshield", "window", "front", "glass", "ice"]
        ):
            return random.choice([
                "I'll check the defrost settings.",
                "Let me help with the windshield.",
                "I'll fix that for you.",
                "Just a second.",
                "Hang on, working on it.",
                "Let me take care of that.",
                "Working on the front glass.",
            ])
        elif any(word in text_lower for word in ["navigate", "directions", "map", "route"]):
            return random.choice([
                "I'll help you with navigation.",
                "Let me get those directions.",
                "Finding the best route.",
                "Hold on, checking the map.",
                "Let me plan that out.",
                "One sec, mapping now.",
                "Got it, setting your route.",
                "Loading directions.",
                "Hang tight, getting the map.",
                "I'll guide you there.",
            ])
        elif (
            (
                text_lower.strip()
                in [
                    "hey",
                    "uh",
                    "hmm",
                    "mmm",
                    "um",
                    "ah",
                    "well",
                    "thanks",
                    "hello",
                    "good",
                    "bye",
                    "goodbye",
                    "great",
                ]
            )
            or text_lower.isalpha()
            or any(
                word in text_lower
                for word in ["great thanks", "okay great thank you", "okay great"]
            )
        ):
            return ""
        else:
            # return random.choice([
            #     "Wait a sec.",
            #     "Hold on.",
            #     "Hang on a sec.",
            #     "One moment.",
            #     "Give me a second.",
            # ])

            return ""
