"""JIRA Cloud REST API — add comments to issues."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.models import DatabaseRecord

logger = get_logger("app.jira")

_JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")


def is_jira_configured() -> bool:
    return bool(
        settings.jira_enabled
        and settings.jira_base_url.strip()
        and settings.jira_email.strip()
        and settings.jira_api_token.strip()
    )


def normalize_jira_key(raw: str) -> str:
    key = raw.strip().upper()
    if not key:
        raise ValueError("JIRA issue key is required (e.g. PROJ-123)")
    if not _JIRA_KEY_RE.match(key):
        raise ValueError(f"Invalid JIRA issue key: {key!r}. Expected format like PROJ-123")
    return key


def issue_browse_url(issue_key: str) -> str | None:
    if not settings.jira_base_url.strip():
        return None
    base = settings.jira_base_url.strip().rstrip("/")
    return f"{base}/browse/{normalize_jira_key(issue_key)}"


def _text_to_adf(text: str) -> dict:
    paragraphs = []
    for line in text.splitlines() or [text]:
        paragraphs.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line}] if line else [],
            }
        )
    if not paragraphs:
        paragraphs = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"type": "doc", "version": 1, "content": paragraphs}


def format_record_comment(comment: str, record: DatabaseRecord | None) -> str:
    if not record:
        return comment
    end = record.end_date.isoformat() if record.end_date else "—"
    header = (
        f"DB Allocation Utility — {record.database_name}\n"
        f"Type: {record.database_type or '—'} | Assignee: {record.assignee or '—'} | "
        f"End date: {end} | Status: {record.status or '—'}"
    )
    return f"{header}\n\n{comment.strip()}"


def add_issue_comment(issue_key: str, comment: str) -> str:
    if not is_jira_configured():
        raise RuntimeError(
            "JIRA is not configured. Set JIRA_ENABLED=true, JIRA_BASE_URL, JIRA_EMAIL, "
            "and JIRA_API_TOKEN in backend/.env (see README)."
        )

    key = normalize_jira_key(issue_key)
    base = settings.jira_base_url.strip().rstrip("/")
    url = f"{base}/rest/api/3/issue/{key}/comment"
    payload = {"body": _text_to_adf(comment)}

    logger.info("Adding JIRA comment issue=%s", key)
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            json=payload,
            auth=(settings.jira_email.strip(), settings.jira_api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if resp.status_code not in (200, 201):
            logger.error("JIRA comment failed %s: %s", resp.status_code, resp.text[:800])
            try:
                detail = resp.json()
                messages = detail.get("errorMessages") or []
                errors = detail.get("errors") or {}
                msg = "; ".join(messages) or str(errors) or resp.text[:300]
            except Exception:
                msg = resp.text[:300]
            raise RuntimeError(f"JIRA API error ({resp.status_code}): {msg}")
        data = resp.json()

    comment_id = data.get("id", "")
    logger.info("JIRA comment added issue=%s comment_id=%s", key, comment_id)
    return str(comment_id)
