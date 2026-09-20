import base64
import json
import logging
from uuid import UUID

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.config import settings
from app.core.roles import UserRole
from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.user import User
from app.schemas.interview_avatar import AvatarState
from app.schemas.interview_voice import (
    WSCandidateAudioEvent,
)
from app.schemas.interview_ws import WSCandidateMessageEvent
from app.services.interview import (
    InvalidSessionStateError,
    InterviewSessionNotFoundError,
    get_tenant_interview_session,
    process_live_candidate_message,
)
from app.services.interview_avatar import (
    build_avatar_state_event,
)
from app.services.interview_ws_manager import (
    DuplicateConnectionError,
    connection_manager,
)
from app.services.speech_to_text import (
    AudioTooLargeError,
    SpeechToTextError,
    SpeechToTextProviderUnavailableError,
    UnsupportedAudioFormatError,
    get_stt_service,
)
from app.services.text_to_speech import (
    get_tts_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/interviews",
    tags=["Interviews WebSocket"],
)

ALLOWED_ROLES = {
    UserRole.COMPANY_ADMIN.value,
    UserRole.RECRUITER.value,
    UserRole.HIRING_MANAGER.value,
}


async def authenticate_ws_user(
    websocket: WebSocket,
    token: str | None,
) -> User | None:
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        logger.warning("WebSocket connection attempt missing JWT token")
        return None

    try:
        user_id_str = decode_access_token(token)
        user_uuid = UUID(user_id_str)
    except (jwt.PyJWTError, ValueError) as exc:
        logger.warning(f"WebSocket JWT authentication failed: {exc}")
        return None

    async with async_session_factory() as db_session:
        user = await db_session.scalar(select(User).where(User.id == user_uuid))
        if user is None or not user.is_active:
            return None
        return user


@router.websocket("/{session_id}/ws")
async def interview_websocket_endpoint(
    websocket: WebSocket,
    session_id: UUID,
    token: str | None = Query(default=None),
):
    # 1. Authenticate user
    user = await authenticate_ws_user(websocket, token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # 2. Check authorization role
    if user.role not in ALLOWED_ROLES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Forbidden")
        return

    # 3. Verify tenant isolation & session state
    async with async_session_factory() as db_session:
        interview_session = await get_tenant_interview_session(
            session=db_session,
            session_id=session_id,
            organization_id=user.organization_id,
        )
        if interview_session is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Interview session not found",
            )
            return

        if interview_session.status != "IN_PROGRESS":
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Interview session is in '{interview_session.status}' status",
            )
            return

    # 4. Connection Manager (reject duplicate connection per session)
    try:
        await connection_manager.connect(session_id, websocket)
    except DuplicateConnectionError:
        logger.warning(f"Duplicate connection rejected for session {session_id}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Another active connection exists for this session",
        )
        return

    # 5. Send initial system connection confirmation & initial IDLE avatar state
    await connection_manager.send_json(
        session_id,
        {
            "type": "system",
            "event": "connected",
            "content": "Connected to real-time live interview session.",
        },
    )
    await connection_manager.send_json(
        session_id,
        build_avatar_state_event(AvatarState.IDLE),
    )

    # 6. Message Loop
    try:
        while True:
            raw_text = await websocket.receive_text()

            # Check per-connection rate limit
            if not connection_manager.rate_limiter.check_rate_limit(session_id):
                await connection_manager.send_json(
                    session_id,
                    {
                        "type": "system",
                        "event": "rate_limit_exceeded",
                        "content": "Message rate limit exceeded. Please wait.",
                    },
                )
                continue

            # Parse JSON payload
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                await connection_manager.send_json(
                    session_id,
                    {
                        "type": "system",
                        "event": "error",
                        "content": "Malformed event: Invalid JSON string.",
                    },
                )
                continue

            event_type = data.get("type")

            # -------------------------------------------------------------
            # A. Text Mode: Candidate Message
            # -------------------------------------------------------------
            if event_type == "candidate_message":
                try:
                    candidate_event = WSCandidateMessageEvent.model_validate(data)
                    clean_content = candidate_event.content.strip()
                    if not clean_content:
                        raise ValueError("Content cannot be empty")
                except (ValueError, Exception):
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "Candidate message content cannot be empty.",
                        },
                    )
                    continue

                # Avatar transitions to THINKING state
                await connection_manager.send_json(
                    session_id,
                    build_avatar_state_event(AvatarState.THINKING),
                )

                # Process candidate text message and obtain AI response
                try:
                    async with async_session_factory() as db_session:
                        ai_response = await process_live_candidate_message(
                            session=db_session,
                            session_id=session_id,
                            candidate_text=clean_content,
                            organization_id=user.organization_id,
                        )

                    # Avatar transitions to SPEAKING state
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.SPEAKING),
                    )

                    # Send AI text response
                    await connection_manager.send_json(
                        session_id,
                        ai_response.model_dump(),
                    )

                    # Avatar returns to IDLE state
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                except (InterviewSessionNotFoundError, InvalidSessionStateError, ValueError) as exc:
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": str(exc),
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                except Exception as exc:
                    logger.error(f"Unexpected error in live interview text processing: {exc}")
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "An internal error occurred processing your message.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )

            # -------------------------------------------------------------
            # B. Voice Mode: Candidate Audio
            # -------------------------------------------------------------
            elif event_type == "candidate_audio":
                try:
                    audio_event = WSCandidateAudioEvent.model_validate(data)
                except Exception:
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "Invalid candidate audio payload structure.",
                        },
                    )
                    continue

                # Avatar transitions to LISTENING state
                await connection_manager.send_json(
                    session_id,
                    build_avatar_state_event(AvatarState.LISTENING),
                )

                # Decode base64 audio
                try:
                    audio_bytes = base64.b64decode(audio_event.audio, validate=True)
                except Exception:
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "Invalid base64 encoded audio data.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue

                # Size check
                if len(audio_bytes) > settings.max_voice_message_size_bytes:
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": f"Audio payload exceeds limit of {settings.max_voice_message_size_bytes} bytes.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue

                # Speech-to-Text Step
                stt_service = get_stt_service()
                try:
                    transcript_text = await stt_service.transcribe(
                        audio_bytes=audio_bytes,
                        content_type=audio_event.content_type,
                    )
                    clean_transcript = transcript_text.strip() if transcript_text else ""
                    if not clean_transcript:
                        raise SpeechToTextError("Speech transcription produced empty text.")
                except (SpeechToTextError, UnsupportedAudioFormatError, AudioTooLargeError, SpeechToTextProviderUnavailableError) as exc:
                    logger.warning(f"STT failure for session {session_id}: {exc}")
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "Speech transcription failed. Please try again.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue
                except Exception as exc:
                    logger.error(f"Unexpected STT exception for session {session_id}: {exc}")
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "Speech transcription failed. Please try again.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue

                # Send candidate transcript event
                await connection_manager.send_json(
                    session_id,
                    {
                        "type": "transcript",
                        "role": "candidate",
                        "content": clean_transcript,
                    },
                )

                # Avatar transitions to THINKING state
                await connection_manager.send_json(
                    session_id,
                    build_avatar_state_event(AvatarState.THINKING),
                )

                # Process transcript through existing interview engine
                try:
                    async with async_session_factory() as db_session:
                        ai_response = await process_live_candidate_message(
                            session=db_session,
                            session_id=session_id,
                            candidate_text=clean_transcript,
                            organization_id=user.organization_id,
                        )

                    # Avatar transitions to SPEAKING state
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.SPEAKING),
                    )

                    # Send AI text response
                    await connection_manager.send_json(
                        session_id,
                        ai_response.model_dump(),
                    )
                except (InterviewSessionNotFoundError, InvalidSessionStateError, ValueError) as exc:
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": str(exc),
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue
                except Exception as exc:
                    logger.error(f"Unexpected error in live interview engine: {exc}")
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.ERROR),
                    )
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "An internal error occurred processing your message.",
                        },
                    )
                    await connection_manager.send_json(
                        session_id,
                        build_avatar_state_event(AvatarState.IDLE),
                    )
                    continue

                # Text-to-Speech Step for AI Response
                tts_service = get_tts_service()
                try:
                    synthesized_audio = await tts_service.synthesize(ai_response.content)
                    b64_audio = base64.b64encode(synthesized_audio).decode("utf-8")
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "ai_audio",
                            "audio": b64_audio,
                            "content_type": "audio/mpeg",
                        },
                    )
                except Exception as exc:
                    logger.warning(f"TTS synthesis failure for session {session_id}: {exc}")
                    # Deliver fallback notification without failing interview
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "tts_unavailable",
                            "content": "Voice playback is temporarily unavailable.",
                        },
                    )

                # Avatar returns to IDLE state
                await connection_manager.send_json(
                    session_id,
                    build_avatar_state_event(AvatarState.IDLE),
                )

            # -------------------------------------------------------------
            # C. Unsupported Event Type
            # -------------------------------------------------------------
            else:
                await connection_manager.send_json(
                    session_id,
                    {
                        "type": "system",
                        "event": "error",
                        "content": f"Unsupported event type '{event_type}'.",
                    },
                )
                continue

    except WebSocketDisconnect:
        connection_manager.disconnect(session_id)
    except Exception as exc:
        logger.error(f"WebSocket loop exception for session {session_id}: {exc}")
        connection_manager.disconnect(session_id)
