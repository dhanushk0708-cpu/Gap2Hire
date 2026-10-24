from abc import ABC, abstractmethod
from typing import Optional
import secrets
import string


class MeetingLinkProvider(ABC):
    """
    Abstract Service Interface for Meeting Link Providers.
    Allows seamlessly swapping the Demonstration Provider with Google Meet, Zoom,
    or Microsoft Teams in production.
    """

    @abstractmethod
    def generate_meeting_link(
        self,
        interview_reference: str,
        interview_type: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Generates meeting conference details for an interview.
        Returns:
            (meeting_url, provider_meeting_id)
        """
        pass


class DemoMeetingLinkProvider(MeetingLinkProvider):
    """
    Demonstration Meeting Link Provider.
    Clearly marks and generates non-production virtual meeting links.
    In-person interviews strictly do not receive meeting links.
    """

    DEMO_DOMAIN = "https://demo.gap2hire.local/meet"

    def generate_meeting_link(
        self,
        interview_reference: str,
        interview_type: str,
    ) -> tuple[Optional[str], Optional[str]]:
        if interview_type.upper() == "IN_PERSON":
            return None, None

        # Clearly labelled demonstration URL
        meeting_url = f"{self.DEMO_DOMAIN}/{interview_reference}"
        provider_meeting_id = f"demo-meet-{interview_reference.lower()}"
        return meeting_url, provider_meeting_id


def generate_interview_reference(year: int = 2026) -> str:
    """
    Generates a unique, professional, human-readable interview reference.
    Example: INT-2026-7A4B
    """
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"INT-{year}-{suffix}"


# Default singleton provider instance
default_meeting_provider: MeetingLinkProvider = DemoMeetingLinkProvider()
