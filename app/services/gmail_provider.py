import base64
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any
import urllib.parse

import httpx

from app.schemas.email_integration import EmailAttachment, NormalizedEmail
from app.services.email_provider import EmailProvider

logger = logging.getLogger(__name__)

GOOGLE_OAUTH_PATH = os.path.join(os.getcwd(), "credentials", "google-oauth.json")


def load_google_oauth_config() -> dict[str, Any]:
    """Loads Google OAuth configuration from local credentials file or environment variables."""
    if os.path.exists(GOOGLE_OAUTH_PATH):
        try:
            with open(GOOGLE_OAUTH_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("web", data.get("installed", {}))
        except Exception as exc:
            logger.warning(f"Error loading google-oauth.json: {exc}")

    return {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/email/oauth/callback")],
    }


def get_google_auth_url(state: str = "") -> str:
    """Constructs the Google OAuth authorization consent URL."""
    cfg = load_google_oauth_config()
    client_id = cfg.get("client_id", "")
    redirect_uri = cfg.get("redirect_uris", ["http://localhost:8000/api/v1/email/oauth/callback"])[0]
    scope = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


async def exchange_google_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchanges an authorization code for Google access and refresh tokens."""
    cfg = load_google_oauth_config()
    token_uri = cfg.get("token_uri", "https://oauth2.googleapis.com/token")
    redirect_uri = cfg.get("redirect_uris", ["http://localhost:8000/api/v1/email/oauth/callback"])[0]

    data = {
        "code": code,
        "client_id": cfg.get("client_id"),
        "client_secret": cfg.get("client_secret"),
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(token_uri, data=data)
        resp.raise_for_status()
        token_data = resp.json()

        # Fetch account email from userinfo
        access_token = token_data.get("access_token")
        account_email = "connected-gmail@gap2hire.com"
        if access_token:
            try:
                userinfo_resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if userinfo_resp.is_success:
                    userinfo = userinfo_resp.json()
                    account_email = userinfo.get("email", account_email)
            except Exception as e:
                logger.warning(f"Error fetching userinfo from Google: {e}")

        token_data["account_email"] = account_email
        return token_data


class GmailProvider(EmailProvider):
    """Production-grade Gmail Provider communicating directly with the Google Gmail REST API."""

    def __init__(self, access_token: str = "", account_email: str = ""):
        self.access_token = access_token
        self.account_email = account_email
        self.base_url = "https://gmail.googleapis.com/gmail/v1/users/me"

    async def connect(self, connection_data: dict[str, Any]) -> bool:
        self.access_token = connection_data.get("access_token", self.access_token)
        self.account_email = connection_data.get("account_email", self.account_email)
        return bool(self.access_token)

    async def disconnect(self) -> bool:
        self.access_token = ""
        return True

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def fetch_emails(
        self,
        limit: int = 50,
        query: str | None = None,
    ) -> list[NormalizedEmail]:
        if not self.access_token:
            return []

        params: dict[str, Any] = {"maxResults": min(limit, 100)}
        if query:
            params["q"] = query

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/messages",
                headers=self._get_headers(),
                params=params,
            )
            if not resp.is_success:
                logger.warning(f"Gmail API list messages failed: {resp.status_code} {resp.text}")
                return []

            data = resp.json()
            messages_meta = data.get("messages", [])

            emails: list[NormalizedEmail] = []
            for meta in messages_meta[:limit]:
                msg_id = meta.get("id")
                if msg_id:
                    em = await self.get_email(msg_id)
                    if em:
                        emails.append(em)

            return emails

    async def get_email(self, external_id: str) -> NormalizedEmail | None:
        if not self.access_token:
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/messages/{external_id}?format=full",
                headers=self._get_headers(),
            )
            if not resp.is_success:
                logger.warning(f"Gmail API get message {external_id} failed: {resp.status_code}")
                return None

            msg = resp.json()
            payload = msg.get("payload", {})
            headers_list = payload.get("headers", [])
            headers_dict = {h.get("name", "").lower(): h.get("value", "") for h in headers_list}

            # Parse sender
            from_header = headers_dict.get("from", "")
            sender_name = from_header
            sender_email = from_header
            if "<" in from_header and ">" in from_header:
                parts = from_header.split("<")
                sender_name = parts[0].strip(' "')
                sender_email = parts[1].split(">")[0].strip()

            subject = headers_dict.get("subject", "(No Subject)")
            to_header = headers_dict.get("to", self.account_email)
            recipient_emails = [e.strip() for e in to_header.split(",") if e.strip()]

            # Date
            internal_date_ms = int(msg.get("internalDate", "0"))
            if internal_date_ms:
                received_at = datetime.fromtimestamp(internal_date_ms / 1000.0, tz=timezone.utc)
            else:
                received_at = datetime.now(tz=timezone.utc)

            # Traverse body and attachments
            body_text = ""
            attachments: list[EmailAttachment] = []

            def _traverse_parts(part: dict[str, Any]):
                nonlocal body_text
                mime_type = part.get("mimeType", "")
                filename = part.get("filename", "")
                body = part.get("body", {})

                if filename:
                    # It's an attachment
                    att_id = body.get("attachmentId") or f"att-{len(attachments)}"
                    size = body.get("size", 0)
                    raw_data = body.get("data")
                    content_bytes = None
                    if raw_data:
                        try:
                            content_bytes = base64.urlsafe_b64decode(raw_data + "==")
                        except Exception:
                            pass

                    attachments.append(
                        EmailAttachment(
                            filename=filename,
                            content_type=mime_type or "application/octet-stream",
                            size=size,
                            provider_attachment_id=att_id,
                            content=content_bytes,
                        )
                    )
                elif mime_type == "text/plain" and body.get("data"):
                    try:
                        decoded_body = base64.urlsafe_b64decode(body["data"] + "==").decode("utf-8", errors="replace")
                        body_text += decoded_body + "\n"
                    except Exception:
                        pass

                for sub in part.get("parts", []):
                    _traverse_parts(sub)

            _traverse_parts(payload)

            # Fetch any external attachment bodies missing content
            for att in attachments:
                if att.content is None and att.provider_attachment_id:
                    try:
                        att.content = await self.get_attachment(external_id, att.provider_attachment_id)
                    except Exception as e:
                        logger.warning(f"Error fetching attachment {att.filename}: {e}")

            return NormalizedEmail(
                external_id=external_id,
                provider="GMAIL",
                sender_email=sender_email,
                sender_name=sender_name or sender_email,
                recipient_emails=recipient_emails,
                subject=subject,
                body_text=body_text.strip(),
                received_at=received_at,
                attachments=attachments,
                metadata={"gmail_thread_id": msg.get("threadId")},
            )

    async def get_attachment(
        self,
        external_id: str,
        attachment_id: str,
    ) -> bytes | None:
        if not self.access_token:
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/messages/{external_id}/attachments/{attachment_id}",
                headers=self._get_headers(),
            )
            if not resp.is_success:
                return None

            data = resp.json()
            raw_b64 = data.get("data")
            if raw_b64:
                return base64.urlsafe_b64decode(raw_b64 + "==")
            return None
