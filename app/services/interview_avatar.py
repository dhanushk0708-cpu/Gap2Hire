import logging

from app.schemas.interview_avatar import AvatarState, InterviewAvatarMetadata, WSAvatarStateEvent

logger = logging.getLogger(__name__)


def get_default_avatar_metadata() -> InterviewAvatarMetadata:
    """Return default presentation metadata for the AI interviewer avatar."""
    return InterviewAvatarMetadata(
        avatar_id="default-interviewer",
        name="Gap2Hire AI Interviewer",
        display_name="AI Interviewer",
        voice_enabled=True,
        avatar_enabled=True,
    )


def build_avatar_state_event(state: AvatarState) -> dict:
    """Construct a standardized dictionary payload for avatar state WebSocket events."""
    event = WSAvatarStateEvent(state=state)
    return event.model_dump()
