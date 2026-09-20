import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class TextToSpeechError(Exception):
    """Base exception for TTS errors."""
    pass


class TextToSpeechProviderUnavailableError(TextToSpeechError):
    """Raised when the TTS provider is unreachable or unconfigured."""
    pass


class TextToSpeechService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text into audio bytes (e.g. mp3)."""
        pass


class OpenAITextToSpeechService(TextToSpeechService):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        voice: str | None = None,
    ):
        self.api_key = api_key or settings.tts_api_key
        self.model = model or settings.tts_model or "tts-1"
        self.voice = voice or settings.tts_voice or "alloy"
        self.endpoint = "https://api.openai.com/v1/audio/speech"

    async def synthesize(self, text: str) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise TextToSpeechError("Input text cannot be empty.")

        if not self.api_key or self.api_key.startswith("your_"):
            raise TextToSpeechProviderUnavailableError("TTS API key is unconfigured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": clean_text,
            "voice": self.voice,
            "response_format": "mp3",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error communicating with TTS provider: {exc}")
            raise TextToSpeechProviderUnavailableError("TTS provider connection failure.") from exc

        if response.status_code != 200:
            logger.error(f"TTS provider returned status {response.status_code}: {response.text}")
            raise TextToSpeechError(f"TTS provider error (status {response.status_code}).")

        audio_bytes = response.content
        if not audio_bytes:
            raise TextToSpeechError("TTS provider returned empty audio content.")

        return audio_bytes


def get_tts_service() -> TextToSpeechService:
    provider = settings.tts_provider.lower().strip()
    if provider in {"openai", "default"}:
        return OpenAITextToSpeechService()
    return OpenAITextToSpeechService()
