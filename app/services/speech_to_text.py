import io
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/flac",
}

EXTENSION_MAP = {
    "audio/webm": "audio.webm",
    "audio/wav": "audio.wav",
    "audio/wave": "audio.wav",
    "audio/x-wav": "audio.wav",
    "audio/mpeg": "audio.mp3",
    "audio/mp3": "audio.mp3",
    "audio/mp4": "audio.mp4",
    "audio/m4a": "audio.m4a",
    "audio/x-m4a": "audio.m4a",
    "audio/ogg": "audio.ogg",
    "audio/flac": "audio.flac",
}


class SpeechToTextError(Exception):
    """Base exception for STT errors."""
    pass


class UnsupportedAudioFormatError(SpeechToTextError):
    """Raised when audio content type or format is unsupported."""
    pass


class AudioTooLargeError(SpeechToTextError):
    """Raised when audio size exceeds maximum configured threshold."""
    pass


class SpeechToTextProviderUnavailableError(SpeechToTextError):
    """Raised when the STT provider is unreachable or misconfigured."""
    pass


def validate_audio_payload(audio_bytes: bytes, content_type: str, max_size_bytes: int) -> None:
    if not audio_bytes:
        raise SpeechToTextError("Audio content cannot be empty.")

    if len(audio_bytes) > max_size_bytes:
        raise AudioTooLargeError(
            f"Audio payload size ({len(audio_bytes)} bytes) exceeds maximum limit of {max_size_bytes} bytes."
        )

    clean_content_type = content_type.lower().split(";")[0].strip()
    if clean_content_type not in SUPPORTED_AUDIO_MIME_TYPES:
        raise UnsupportedAudioFormatError(
            f"Unsupported audio format '{content_type}'. Allowed formats: {', '.join(sorted(SUPPORTED_AUDIO_MIME_TYPES))}"
        )


class SpeechToTextService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        """Transcribe audio bytes to text string."""
        pass


class GroqSpeechToTextService(SpeechToTextService):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.stt_api_key or settings.groq_api_key
        self.model = model or settings.stt_model or "whisper-large-v3"
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        validate_audio_payload(audio_bytes, content_type, settings.max_voice_message_size_bytes)

        if not self.api_key or self.api_key.startswith("your_"):
            raise SpeechToTextProviderUnavailableError("STT API key is unconfigured.")

        clean_content_type = content_type.lower().split(";")[0].strip()
        filename = EXTENSION_MAP.get(clean_content_type, "audio.webm")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        files = {
            "file": (filename, io.BytesIO(audio_bytes), clean_content_type),
        }
        data = {
            "model": self.model,
            "response_format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    files=files,
                    data=data,
                )
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error communicating with STT provider: {exc}")
            raise SpeechToTextProviderUnavailableError("STT provider connection failure.") from exc

        if response.status_code != 200:
            logger.error(f"STT provider returned status {response.status_code}: {response.text}")
            raise SpeechToTextError(f"STT provider error (status {response.status_code}).")

        try:
            res_json = response.json()
            transcript = res_json.get("text", "").strip()
            return transcript
        except Exception as exc:
            logger.error(f"Failed to parse STT response JSON: {exc}")
            raise SpeechToTextError("Malformed response from STT provider.") from exc


def get_stt_service() -> SpeechToTextService:
    provider = settings.stt_provider.lower().strip()
    if provider in {"groq", "whisper", "default"}:
        return GroqSpeechToTextService()
    # Default fallback
    return GroqSpeechToTextService()
