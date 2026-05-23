import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.logging_config import get_logger
from app.models import DatabaseRecord, User
from app.schemas import JiraCommentRequest, JiraCommentResult, JiraStatusOut
from app.services import jira_client

logger = get_logger("app.jira.router")
router = APIRouter(prefix="/api/jira", tags=["jira"])


def _require_jira() -> None:
    if not jira_client.is_jira_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "JIRA is not configured. Set JIRA_ENABLED=true, JIRA_BASE_URL, JIRA_EMAIL, "
                "and JIRA_API_TOKEN in backend/.env (see README)."
            ),
        )


@router.get("/status", response_model=JiraStatusOut)
def jira_status(user: User = Depends(get_current_user)):
    from app.config import settings

    configured = jira_client.is_jira_configured()
    return JiraStatusOut(
        enabled=settings.jira_enabled,
        configured=configured,
        base_url=settings.jira_base_url.rstrip("/") if configured else None,
        hint=None
        if configured
        else "Create an API token at id.atlassian.com and set JIRA_* in backend/.env",
    )


@router.post("/issues/{issue_key}/comment", response_model=JiraCommentResult)
def comment_on_issue(
    issue_key: str,
    payload: JiraCommentRequest,
    user: User = Depends(get_current_user),
):
    _require_jira()
    try:
        key = jira_client.normalize_jira_key(issue_key)
        comment_id = jira_client.add_issue_comment(key, payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.exception("JIRA comment failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JiraCommentResult(
        issue_key=key,
        comment_id=comment_id,
        browse_url=jira_client.issue_browse_url(key),
        message=f"Comment added to {key}",
    )


@router.post("/databases/{record_id}/comment", response_model=JiraCommentResult)
def comment_on_database_record(
    record_id: int,
    payload: JiraCommentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_jira()
    record = db.query(DatabaseRecord).filter(DatabaseRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    key_raw = payload.jira_key or record.jira_key
    if not key_raw:
        raise HTTPException(
            status_code=400,
            detail="No JIRA issue key. Set jira_key on the record or pass jira_key in the request.",
        )

    try:
        key = jira_client.normalize_jira_key(key_raw)
        if payload.save_jira_key and record.jira_key != key:
            record.jira_key = key
            db.commit()
            db.refresh(record)
        body = jira_client.format_record_comment(payload.comment, record)
        comment_id = jira_client.add_issue_comment(key, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, httpx.HTTPError) as exc:
        logger.exception("JIRA comment on record %s failed", record_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JiraCommentResult(
        issue_key=key,
        comment_id=comment_id,
        browse_url=jira_client.issue_browse_url(key),
        message=f"Comment added to {key} for database {record.database_name}",
    )
