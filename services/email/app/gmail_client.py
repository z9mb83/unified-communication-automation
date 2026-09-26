"""Gmail token loading, validation, and sending."""

from __future__ import annotations

import base64
from email.message import EmailMessage

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app import credential_store
from app.config_loader import BrandConfig


def gmail_service(brand: BrandConfig, mailbox: str):
    credentials = credential_store.load_credentials(brand, mailbox)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        credential_store.persist_refresh(brand, mailbox, credentials)
    if not credentials.valid:
        raise RuntimeError(f"OAuth credentials are not valid for {mailbox}")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def profile_email(brand: BrandConfig, mailbox: str) -> str:
    profile = gmail_service(brand, mailbox).users().getProfile(userId="me").execute()
    return str(profile.get("emailAddress", "")).strip().lower()


def send_email(
    brand: BrandConfig,
    mailbox: str,
    recipient: str,
    cc_email: str,
    subject: str,
    body: str,
) -> str:
    if not subject.strip() or not body.strip():
        raise ValueError("Refusing to send a blank subject or body")
    message = EmailMessage()
    message.set_content(body)
    message["To"] = recipient
    if cc_email.strip():
        message["Cc"] = cc_email.strip()
    message["From"] = mailbox
    message["Subject"] = subject

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    result = (
        gmail_service(brand, mailbox)
        .users()
        .messages()
        .send(userId="me", body={"raw": encoded})
        .execute()
    )
    return str(result["id"])
