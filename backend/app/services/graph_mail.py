"""Send email via Microsoft Graph API (OAuth2 client credentials).

Use when your tenant disables SMTP basic auth (error 5.7.139).
Requires an Azure app registration with application permission Mail.Send (admin consent).
"""

from __future__ import annotations

import time
from typing import Sequence

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger("app.email.graph")

_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{user}/sendMail"

_token_cache: dict[str, float | str | None] = {"access_token": None, "expires_at": 0.0}


def is_graph_configured() -> bool:
    return bool(
        settings.email_enabled
        and settings.azure_tenant_id
        and settings.azure_client_id
        and settings.azure_client_secret
        and _send_as_mailbox()
    )


def _send_as_mailbox() -> str:
    return (settings.graph_send_as or settings.mail_from or "").strip()


def _get_access_token() -> str:
    now = time.time()
    cached = _token_cache.get("access_token")
    expires = float(_token_cache.get("expires_at") or 0)
    if cached and now < expires - 120:
        return str(cached)

    tenant = settings.azure_tenant_id
    url = _TOKEN_URL.format(tenant=tenant)
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    logger.debug("Requesting Microsoft Graph access token")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, data=data)
        if resp.status_code != 200:
            logger.error("Graph token error %s: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        payload = resp.json()

    token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    _token_cache["access_token"] = token
    _token_cache["expires_at"] = now + expires_in
    return token


def send_via_graph(
    to: Sequence[str],
    subject: str,
    body_text: str,
    *,
    body_html: str | None = None,
    cc: Sequence[str] | None = None,
) -> None:
    if not is_graph_configured():
        raise RuntimeError(
            "Microsoft Graph email is not configured. Set EMAIL_PROVIDER=graph and "
            "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, GRAPH_SEND_AS in backend/.env"
        )

    send_as = _send_as_mailbox()
    if not send_as:
        raise RuntimeError("GRAPH_SEND_AS or MAIL_FROM must be set to the mailbox that sends mail")

    def recipients(addresses: Sequence[str]) -> list[dict]:
        return [{"emailAddress": {"address": a}} for a in addresses]

    message: dict = {
        "subject": subject,
        "body": {
            "contentType": "HTML" if body_html else "Text",
            "content": body_html if body_html else body_text,
        },
        "toRecipients": recipients(to),
    }
    if cc:
        message["ccRecipients"] = recipients(cc)

    url = _GRAPH_SEND_URL.format(user=send_as)
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"message": message, "saveToSentItems": True}

    logger.info("Graph sendMail from=%s to=%s subject=%s", send_as, list(to), subject[:80])
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=body, headers=headers)
        if resp.status_code not in (200, 202):
            logger.error("Graph sendMail failed %s: %s", resp.status_code, resp.text[:800])
            resp.raise_for_status()

    logger.info("Graph email sent to %s", list(to))
