import logging
import time
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class DuplicateConnectionError(Exception):
    pass


class RateLimitExceededError(Exception):
    pass


class RateLimiter:
    """Lightweight in-memory per-connection rate limiter (e.g. max 5 messages per 3s)."""

    def __init__(self, max_messages: int = 5, window_seconds: float = 3.0):
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        self.timestamps: dict[UUID, list[float]] = {}

    def check_rate_limit(self, session_id: UUID) -> bool:
        now = time.time()
        history = self.timestamps.get(session_id, [])
        # Filter timestamps within window
        valid_history = [t for t in history if now - t < self.window_seconds]
        if len(valid_history) >= self.max_messages:
            return False
        valid_history.append(now)
        self.timestamps[session_id] = valid_history
        return True

    def remove(self, session_id: UUID):
        self.timestamps.pop(session_id, None)


class InterviewConnectionManager:
    def __init__(self):
        self.active_connections: dict[UUID, WebSocket] = {}
        self.rate_limiter = RateLimiter(max_messages=5, window_seconds=3.0)

    async def connect(self, session_id: UUID, websocket: WebSocket):
        if session_id in self.active_connections:
            raise DuplicateConnectionError(
                f"An active connection already exists for session {session_id}"
            )
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: UUID):
        if session_id in self.active_connections:
            self.active_connections.pop(session_id, None)
            self.rate_limiter.remove(session_id)
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: UUID, data: dict):
        websocket = self.active_connections.get(session_id)
        if websocket:
            await websocket.send_json(data)


connection_manager = InterviewConnectionManager()
