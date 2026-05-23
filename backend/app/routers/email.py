import smtplib
from datetime import date

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.logging_config import get_logger
from app.models import DatabaseRecord, User
from app.routers.databases import (
    KPI_CATEGORIES,
    KPI_TITLES,
    _apply_kpi_category_filter,
    _next_calendar_month,
)
from app.schemas import (
    EmailSendResult,
    EmailStatusOut,
    ExpiryDigestEmailRequest,
    NotifyRecordEmailRequest,
    SendEmailRequest,
)
from app.services import email as email_service

logger = get_logger("app.email.router")
router = APIRouter(prefix="/api/email", tags=["email"])


def _require_email_ready() -> None:
    if not email_service.is_email_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Email is not configured. Add SMTP settings for Microsoft Outlook / Office 365 "
                "to backend/.env (see README)."
            ),
        )


@router.get("/status", response_model=EmailStatusOut)
def email_status(user: User = Depends(get_current_user)):
    logger.debug("Email status check user_id=%s", user.id)
    configured = email_service.is_email_configured()
    provider = email_service.email_provider_label()
    hint = None
    if settings.email_enabled and not configured:
        if provider == "graph":
            hint = "Set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, GRAPH_SEND_AS"
        else:
            hint = "Set SMTP_USER, SMTP_PASSWORD, MAIL_FROM — or use EMAIL_PROVIDER=graph if SMTP basic auth is disabled"
    elif provider == "graph":
        hint = "Using Microsoft Graph API (OAuth2)"
    return EmailStatusOut(
        enabled=settings.email_enabled,
        configured=configured,
        provider=provider,
        smtp_host=settings.smtp_host if provider == "smtp" else None,
        mail_from=settings.mail_from or None,
        graph_send_as=(settings.graph_send_as or settings.mail_from or None) if provider == "graph" else None,
        hint=hint,
    )


@router.post("/send", response_model=EmailSendResult)
def send_custom_email(
    payload: SendEmailRequest,
    user: User = Depends(get_current_user),
):
    _require_email_ready()
    logger.info("Custom email from user_id=%s to=%s", user.id, payload.to)
    try:
        email_service.send_email(
            payload.to,
            payload.subject,
            payload.body,
            body_html=payload.body if payload.html else None,
            cc=payload.cc,
        )
    except (RuntimeError, ValueError, smtplib.SMTPException, httpx.HTTPError) as exc:
        logger.exception("Failed to send email")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmailSendResult(message=f"Email sent to {', '.join(payload.to)}")


@router.post("/records/{record_id}/notify", response_model=EmailSendResult)
def notify_record_assignee(
    record_id: int,
    payload: NotifyRecordEmailRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_email_ready()
    record = db.query(DatabaseRecord).filter(DatabaseRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    recipient = payload.to
    if not recipient:
        recipient = email_service.assignee_to_email(record.assignee)
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="No recipient. Set assignee to an email address or provide 'to' in the request.",
        )

    subject, body, html = email_service.format_record_notification(record, payload.message)
    logger.info("Notify record id=%s to=%s user_id=%s", record_id, recipient, user.id)
    try:
        email_service.send_email([recipient], subject, body, body_html=html)
    except (RuntimeError, ValueError, smtplib.SMTPException, httpx.HTTPError) as exc:
        logger.exception("Failed to notify assignee")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmailSendResult(message=f"Notification sent to {recipient}")


@router.post("/expiry-digest", response_model=EmailSendResult)
def send_expiry_digest(
    payload: ExpiryDigestEmailRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_email_ready()
    category = payload.category
    if category not in KPI_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Use one of: {sorted(KPI_CATEGORIES)}")

    today = date.today()
    next_year, next_month = _next_calendar_month(today.year, today.month)
    query = db.query(DatabaseRecord)
    if payload.database_type:
        query = query.filter(DatabaseRecord.database_type == payload.database_type)
    query = _apply_kpi_category_filter(query, category, today, next_year, next_month)
    records = query.order_by(DatabaseRecord.end_date.asc().nulls_last(), DatabaseRecord.database_name).all()

    title = KPI_TITLES.get(category, category)
    if payload.database_type:
        title = f"{title} — {payload.database_type}"

    subject, body, html = email_service.format_records_digest(title, records, payload.message)
    logger.info(
        "Expiry digest category=%s count=%s to=%s user_id=%s",
        category,
        len(records),
        payload.to,
        user.id,
    )
    try:
        email_service.send_email(payload.to, subject, body, body_html=html, cc=payload.cc)
    except (RuntimeError, ValueError, smtplib.SMTPException, httpx.HTTPError) as exc:
        logger.exception("Failed to send expiry digest")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EmailSendResult(
        message=f"Report emailed to {', '.join(payload.to)} ({len(records)} databases)"
    )
