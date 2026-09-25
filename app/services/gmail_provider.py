import base64
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr
import html
import json
import logging
import os
import re
from typing import Any
import urllib.parse

import httpx

from app.schemas.email_integration import EmailAttachment, NormalizedEmail
from app.services.email_provider import EmailProvider

logger = logging.getLogger(__name__)

GOOGLE_OAUTH_PATH = os.path.join(os.getcwd(), "credentials", "google-oauth.json")
DEFAULT_REDIRECT_URI = "http://localhost:8000/api/v1/email-connections/oauth/callback"


def decode_mime_header(header_value: str | None) -> str:
    """Safely decodes an RFC 2047 encoded email header (e.g. =?UTF-8?B?...?=) into a valid string."""
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                enc = encoding or "utf-8"
                try:
                    result.append(part.decode(enc, errors="replace"))
                except Exception:
                    result.append(part.decode("utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)
    except Exception:
        return str(header_value)


def safe_b64url_decode(raw_data: str | None) -> bytes | None:
    """Safely decodes base64url data from Gmail API, ensuring correct padding and error recovery."""
    if not raw_data:
        return None
    try:
        padded = raw_data + "=" * ((4 - len(raw_data) % 4) % 4)
        return base64.urlsafe_b64decode(padded)
    except Exception as exc:
        try:
            padded = raw_data + "=" * ((4 - len(raw_data) % 4) % 4)
            return base64.b64decode(padded)
        except Exception:
            logger.warning(f"Could not b64-decode Gmail data: {exc}")
            return None


def get_part_charset(part: dict[str, Any]) -> str:
    """Extracts the character encoding from part headers, default to utf-8."""
    for h in part.get("headers", []):
        if h.get("name", "").lower() == "content-type":
            val = h.get("value", "")
            match = re.search(r'charset=["\']?([^"\';\s]+)', val, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return "utf-8"


def decode_text_bytes(raw_bytes: bytes, charset: str = "utf-8") -> str:
    """Decodes raw text bytes using the specified charset with multi-level safe fallback."""
    if not raw_bytes:
        return ""
    if charset:
        try:
            return raw_bytes.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            pass
    try:
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        return raw_bytes.decode("latin-1", errors="replace")
    except Exception:
        return ""


def clean_html_to_text(html_content: str) -> str:
    """Converts HTML email body into clean readable plain text."""
    if not html_content:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return text.strip()


def get_google_redirect_uri(cfg: dict[str, Any] | None = None) -> str:
    """Returns the canonical Google OAuth redirect URI."""
    if os.getenv("GOOGLE_REDIRECT_URI"):
        return os.getenv("GOOGLE_REDIRECT_URI", DEFAULT_REDIRECT_URI)

    if cfg and "redirect_uris" in cfg and isinstance(cfg["redirect_uris"], list) and cfg["redirect_uris"]:
        uri = cfg["redirect_uris"][0]
        if "/api/v1/email/oauth/callback" in uri:
            return uri.replace("/api/v1/email/oauth/callback", "/api/v1/email-connections/oauth/callback")
        return uri

    return DEFAULT_REDIRECT_URI


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
        "redirect_uris": [DEFAULT_REDIRECT_URI],
    }


def get_google_auth_url(state: str = "") -> str:
    """Constructs the Google OAuth authorization consent URL."""
    cfg = load_google_oauth_config()
    client_id = cfg.get("client_id", "")
    redirect_uri = get_google_redirect_uri(cfg)
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
    redirect_uri = get_google_redirect_uri(cfg)

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
            from_raw = headers_dict.get("from", "")
            from_decoded = decode_mime_header(from_raw)
            sender_name, sender_email = parseaddr(from_decoded)
            if not sender_email:
                sender_email = from_decoded.strip()
            if not sender_name:
                sender_name = sender_email

            subject_raw = headers_dict.get("subject", "(No Subject)")
            subject = decode_mime_header(subject_raw)

            to_raw = headers_dict.get("to", self.account_email)
            to_decoded = decode_mime_header(to_raw)
            recipient_emails = [parseaddr(e.strip())[1] or e.strip() for e in to_decoded.split(",") if e.strip()]

            # Date
            internal_date_ms = int(msg.get("internalDate", "0"))
            if internal_date_ms:
                received_at = datetime.fromtimestamp(internal_date_ms / 1000.0, tz=timezone.utc)
            else:
                received_at = datetime.now(tz=timezone.utc)

            # Traverse body and attachments
            plain_texts: list[str] = []
            html_texts: list[str] = []
            attachments: list[EmailAttachment] = []

            def _traverse_parts(part: dict[str, Any]):
                mime_type = part.get("mimeType", "").lower()
                filename_raw = part.get("filename", "")
                filename = decode_mime_header(filename_raw)
                body = part.get("body", {})
                att_id = body.get("attachmentId")
                raw_data = body.get("data")

                if filename or att_id or (mime_type and not mime_type.startswith("text/") and not mime_type.startswith("multipart/")):
                    # It's an attachment
                    attachment_id = att_id or f"att-{len(attachments)}"
                    size = body.get("size", 0)
                    content_bytes = safe_b64url_decode(raw_data) if raw_data else None

                    attachments.append(
                        EmailAttachment(
                            filename=filename or f"attachment-{len(attachments)+1}",
                            content_type=mime_type or "application/octet-stream",
                            size=size or (len(content_bytes) if content_bytes else 0),
                            provider_attachment_id=attachment_id,
                            content=content_bytes,
                        )
                    )
                elif mime_type == "text/plain" and raw_data:
                    charset = get_part_charset(part)
                    data_bytes = safe_b64url_decode(raw_data)
                    if data_bytes:
                        decoded_text = decode_text_bytes(data_bytes, charset)
                        if decoded_text:
                            plain_texts.append(decoded_text)
                elif mime_type == "text/html" and raw_data:
                    charset = get_part_charset(part)
                    data_bytes = safe_b64url_decode(raw_data)
                    if data_bytes:
                        decoded_html = decode_text_bytes(data_bytes, charset)
                        if decoded_html:
                            html_texts.append(clean_html_to_text(decoded_html))

                for sub in part.get("parts", []):
                    _traverse_parts(sub)

            _traverse_parts(payload)

            # Combine body text (prefer plain text, fallback to HTML text)
            if plain_texts:
                body_text = "\n\n".join(plain_texts).strip()
            elif html_texts:
                body_text = "\n\n".join(html_texts).strip()
            else:
                body_text = ""

            # Fetch any external attachment bodies missing content
            for att in attachments:
                if att.content is None and att.provider_attachment_id and not att.provider_attachment_id.startswith("att-"):
                    try:
                        att.content = await self.get_attachment(external_id, att.provider_attachment_id)
                        if att.content and not att.size:
                            att.size = len(att.content)
                    except Exception as e:
                        logger.warning(f"Error fetching attachment {att.filename}: {e}")

            return NormalizedEmail(
                external_id=external_id,
                provider="GMAIL",
                sender_email=sender_email,
                sender_name=sender_name or sender_email,
                recipient_emails=recipient_emails,
                subject=subject,
                body_text=body_text,
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
                return safe_b64url_decode(raw_b64)
            return None

