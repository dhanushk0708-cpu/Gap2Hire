import base64
from datetime import datetime
import json
import logging
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.roles import UserRole
from app.core.security import decode_access_token
from app.db.session import async_session_factory
from app.models.interview import InterviewMessage, InterviewQuestion, InterviewSession
from app.models.user import User
from app.schemas.interview_avatar import AvatarState
from app.schemas.interview_integrity import WSIntegrityEvent, WSIntegrityEventAck
from app.schemas.interview_voice import (
    WSCandidateAudioEvent,
)
from app.schemas.interview_ws import WSCandidateMessageEvent
from app.services.interview import (
    InvalidSessionStateError,
    InterviewSessionNotFoundError,
    generate_next_question_for_session,
    get_tenant_interview_session,
    process_live_candidate_message,
)
from app.services.interview_integrity import (
    IntegritySessionAccessDeniedError,
    IntegritySessionNotFoundError,
    InvalidIntegrityEventTypeError,
    record_integrity_event,
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
    UserRole.CANDIDATE.value,
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

    # 3. Verify tenant isolation, candidate authorization & session state
    async with async_session_factory() as db_session:
        from app.models.application import Application
        from app.models.candidate import Candidate
        from app.models.job import Job

        stmt = (
            select(InterviewSession)
            .join(Application, Application.id == InterviewSession.application_id)
            .join(Job, Job.id == Application.job_id)
            .options(
                selectinload(InterviewSession.application).selectinload(Application.candidate),
            )
            .where(
                InterviewSession.id == session_id,
                Job.organization_id == user.organization_id,
            )
        )
        interview_session = await db_session.scalar(stmt)
        if interview_session is None:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Interview session not found",
            )
            return

        # If user is a CANDIDATE, verify they own this session
        if user.role == UserRole.CANDIDATE.value:
            if (
                not interview_session.application
                or not interview_session.application.candidate
                or interview_session.application.candidate.email.strip().lower() != user.email.strip().lower()
            ):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Candidate is not authorized for this interview session",
                )
                return

        # Auto-start session if in CREATED or SCHEDULED state
        if interview_session.status in ("CREATED", "SCHEDULED"):
            interview_session.status = "IN_PROGRESS"
            interview_session.started_at = datetime.utcnow()
            interview_session.updated_at = datetime.utcnow()
            msg_count_stmt = select(func.count(InterviewMessage.id)).where(InterviewMessage.session_id == session_id)
            has_msgs = ((await db_session.scalar(msg_count_stmt)) or 0) > 0
            if not has_msgs:
                sys_msg = InterviewMessage(
                    session_id=interview_session.id,
                    role="SYSTEM",
                    content="Interview session started.",
                    sequence_number=1,
                )
                db_session.add(sys_msg)
            await db_session.commit()
            logger.info(f"[WS AUTO-START] Transitioned session {session_id} from {interview_session.status} to IN_PROGRESS")

        elif interview_session.status != "IN_PROGRESS":
            logger.warning(f"[WS STATUS REJECT] Session {session_id} in status '{interview_session.status}'")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Interview session is in '{interview_session.status}' status",
            )
            return

    # 4. Connection Manager (supports multiple / reconnecting sockets)
    is_candidate = (user.role == UserRole.CANDIDATE.value)
    if is_candidate and connection_manager.has_candidate(session_id):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Candidate connection already active for this session",
        )
        return

    await connection_manager.connect(session_id, websocket, is_candidate=is_candidate)
    logger.info(f"[WS CONNECT] session_id={session_id}, user={user.id}, role={user.role}")

    # 5. Send initial system connection confirmation
    await connection_manager.send_json(
        session_id,
        {
            "type": "system",
            "event": "connected",
            "content": "Connected to real-time live interview session.",
        },
    )

    # 6. Immediately verify or generate the active interview question
    async with async_session_factory() as db_session:
        q_stmt = (
            select(InterviewQuestion)
            .where(InterviewQuestion.session_id == session_id)
            .order_by(InterviewQuestion.sequence_number.desc())
        )
        existing_q = await db_session.scalar(q_stmt)

        current_question_text = None
        target_cap_name = "General"

        if isinstance(existing_q, InterviewQuestion):
            current_question_text = existing_q.question
            target_cap_name = existing_q.concept or "General"
            logger.info(f"[WS QUESTION RESUMED] session_id={session_id}, seq={existing_q.sequence_number}")
        else:
            try:
                new_q = await generate_next_question_for_session(
                    session=db_session,
                    session_id=session_id,
                    organization_id=user.organization_id,
                )
                current_question_text = new_q.question
                target_cap_name = new_q.concept or "General"
                logger.info(f"[WS QUESTION GENERATED] session_id={session_id}, seq={new_q.sequence_number}")
            except Exception as q_err:
                logger.error(f"[WS QUESTION ERROR] Could not generate initial question: {q_err}", exc_info=True)

        if current_question_text:
            # Avatar transitions to SPEAKING state
            await connection_manager.send_json(
                session_id,
                build_avatar_state_event(AvatarState.SPEAKING),
            )
            # Send AI question message
            await connection_manager.send_json(
                session_id,
                {
                    "type": "ai_message",
                    "content": current_question_text,
                    "target_capability": target_cap_name,
                },
            )
            # Avatar transitions to LISTENING state so candidate can answer
            await connection_manager.send_json(
                session_id,
                build_avatar_state_event(AvatarState.LISTENING),
            )
        else:
            await connection_manager.send_json(
                session_id,
                build_avatar_state_event(AvatarState.IDLE),
            )

    # 7. Message Loop
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
            # C. Client Integrity Signal: Observable Session Events
            # -------------------------------------------------------------
            elif event_type == "integrity_event":
                try:
                    integrity_event_payload = WSIntegrityEvent.model_validate(data)
                except Exception as exc:
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": f"Malformed integrity event: {exc}",
                        },
                    )
                    continue

                try:
                    async with async_session_factory() as db_session:
                        metadata = dict(integrity_event_payload.metadata or {})
                        evidence_img_b64 = data.get("evidence_image")
                        event_id = uuid4()
                        if evidence_img_b64:
                            if "," in evidence_img_b64:
                                evidence_img_b64 = evidence_img_b64.split(",", 1)[1]
                            try:
                                from app.services.vision_service import vision_service
                                raw_img = base64.b64decode(evidence_img_b64)
                                ref = await vision_service.save_evidence_frame(session_id, event_id, raw_img)
                                metadata["evidence_reference"] = ref
                                metadata["evidence_url"] = f"/api/v1/interviews/{session_id}/integrity-evidence/{event_id}"
                            except Exception as save_err:
                                logger.warning(f"Could not save client evidence frame: {save_err}")

                        recorded_event = await record_integrity_event(
                            session=db_session,
                            session_id=session_id,
                            event_type=integrity_event_payload.event_type,
                            user=user,
                            occurred_at=integrity_event_payload.occurred_at,
                            metadata=metadata,
                        )

                    ack_event = WSIntegrityEventAck(
                        event_type=integrity_event_payload.event_type,
                        event_id=str(recorded_event.id),
                        occurred_at=recorded_event.occurred_at.isoformat(),
                    )
                    await connection_manager.send_json(
                        session_id,
                        ack_event.model_dump(),
                    )

                    # If vision detection observation, broadcast red alert to candidate & HR observers
                    if integrity_event_payload.event_type.value in ("PHONE_DETECTED", "MULTIPLE_PERSONS_DETECTED"):
                        alert_msg = (
                            "Mobile phone detected — Evidence frame captured"
                            if integrity_event_payload.event_type.value == "PHONE_DETECTED"
                            else "Multiple people detected — Evidence frame captured"
                        )
                        meta_dict = recorded_event.metadata_json or {}
                        await connection_manager.send_json(
                            session_id,
                            {
                                "type": "integrity_observation",
                                "event_type": integrity_event_payload.event_type.value,
                                "alert_title": "🔴 INTEGRITY OBSERVATION",
                                "alert_message": alert_msg,
                                "event_id": str(recorded_event.id),
                                "evidence_reference": meta_dict.get("evidence_reference"),
                                "evidence_url": meta_dict.get("evidence_url"),
                                "confidence": meta_dict.get("confidence", 0.9),
                                "occurred_at": recorded_event.occurred_at.isoformat(),
                                "metadata": meta_dict,
                            },
                        )

                except (IntegritySessionNotFoundError, IntegritySessionAccessDeniedError, InvalidIntegrityEventTypeError, ValueError) as exc:
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": str(exc),
                        },
                    )
                except Exception as exc:
                    logger.error(f"Unexpected error recording integrity event for session {session_id}: {exc}")
                    await connection_manager.send_json(
                        session_id,
                        {
                            "type": "system",
                            "event": "error",
                            "content": "An internal error occurred persisting the integrity event.",
                        },
                    )

            # -------------------------------------------------------------
            # D. Client Sampled Camera Frame for Vision Monitoring
            # -------------------------------------------------------------
            elif event_type == "vision_frame":
                image_b64 = data.get("image")
                if image_b64:
                    if "," in image_b64:
                        image_b64 = image_b64.split(",", 1)[1]
                    try:
                        raw_bytes = base64.b64decode(image_b64)
                        from app.services.vision_service import vision_service
                        await vision_service.process_sampled_frame(
                            session_id=session_id,
                            image_bytes=raw_bytes,
                            user=user,
                        )
                    except Exception as frame_err:
                        logger.debug(f"[WS VISION FRAME ERROR] session {session_id}: {frame_err}")

            # -------------------------------------------------------------
            # D. Unsupported Event Type
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
        connection_manager.disconnect(session_id, websocket)
        logger.info(f"[WS DISCONNECT] session_id={session_id}")
    except RuntimeError as exc:
        err_msg = str(exc).lower()
        if "accept" in err_msg or "disconnect" in err_msg:
            connection_manager.disconnect(session_id, websocket)
            logger.info(f"[WS DISCONNECT (early)] session_id={session_id}")
        else:
            logger.error(f"[WS LOOP ERROR] WebSocket loop exception for session {session_id}: {exc}")
            connection_manager.disconnect(session_id, websocket)
    except Exception as exc:
        logger.error(f"[WS LOOP ERROR] WebSocket loop exception for session {session_id}: {exc}")
        connection_manager.disconnect(session_id, websocket)
