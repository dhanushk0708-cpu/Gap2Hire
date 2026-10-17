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
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        self.candidate_connections: dict[UUID, WebSocket] = {}
        self.rate_limiter = RateLimiter(max_messages=15, window_seconds=3.0)

    def has_candidate(self, session_id: UUID) -> bool:
        return session_id in self.candidate_connections

    async def connect(self, session_id: UUID, websocket: WebSocket, is_candidate: bool = False):
        if is_candidate and session_id in self.candidate_connections:
            raise DuplicateConnectionError(
                f"An active connection already exists for session {session_id}"
            )
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        if websocket not in self.active_connections[session_id]:
            self.active_connections[session_id].append(websocket)
        if is_candidate:
            self.candidate_connections[session_id] = websocket
        logger.info(f"[WS CONNECT] WebSocket connected for session: {session_id} (active: {len(self.active_connections[session_id])})")

    def disconnect(self, session_id: UUID, websocket: WebSocket | None = None):
        if session_id in self.candidate_connections:
            if not websocket or self.candidate_connections[session_id] == websocket:
                self.candidate_connections.pop(session_id, None)

        if session_id in self.active_connections:
            if websocket and websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            elif not websocket:
                self.active_connections[session_id].clear()

            if not self.active_connections[session_id]:
                self.active_connections.pop(session_id, None)
                self.rate_limiter.remove(session_id)
            logger.info(f"[WS DISCONNECT] WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: UUID, data: dict):
        sockets = list(self.active_connections.get(session_id, []))
        dead_sockets = []
        for ws in sockets:
            try:
                await ws.send_json(data)
            except Exception as exc:
                logger.debug(f"[WS SEND ERROR] Failed to send to socket in session {session_id}: {exc}")
                dead_sockets.append(ws)

        for ws in dead_sockets:
            if session_id in self.active_connections and ws in self.active_connections[session_id]:
                self.active_connections[session_id].remove(ws)


connection_manager = InterviewConnectionManager()
