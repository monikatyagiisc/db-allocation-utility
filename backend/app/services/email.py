"""Send email via SMTP (Microsoft 365 / Outlook: smtp.office365.com:587)."""

from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Sequence

from email_validator import EmailNotValidError, validate_email

from app.config import settings
from app.logging_config import get_logger
from app.models import DatabaseRecord

logger = get_logger("app.email")

_EMAIL_LIKE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_email_configured() -> bool:
    return bool(
        settings.email_enabled
        and settings.smtp_host
        and settings.smtp_user
        and settings.smtp_password
        and settings.mail_from
    )


def normalize_email(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw or not _EMAIL_LIKE.match(raw):
        return None
    try:
        return validate_email(raw, check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def assignee_to_email(assignee: str | None) -> str | None:
    if not assignee:
        return None
    text = assignee.strip()
    if normalize_email(text):
        return normalize_email(text)
    # "Name <email@corp.com>" or "email@corp.com (Name)"
    angle = re.search(r"<([^>]+)>", text)
    if angle:
        return normalize_email(angle.group(1))
    paren = re.search(r"\(([^)]+@[^)]+)\)", text)
    if paren:
        return normalize_email(paren.group(1))
    for token in re.split(r"[\s,;]+", text):
        found = normalize_email(token)
        if found:
            return found
    return None


def send_email(
    to: Sequence[str],
    subject: str,
    body_text: str,
    *,
    body_html: str | None = None,
    cc: Sequence[str] | None = None,
) -> None:
    if not is_email_configured():
        raise RuntimeError(
            "Email is not configured. Set EMAIL_ENABLED=true and SMTP_* variables in backend/.env"
        )

    recipients = [normalize_email(r) for r in to]
    recipients = [r for r in recipients if r]
    if not recipients:
        raise ValueError("At least one valid recipient email is required")

    cc_list = [normalize_email(r) for r in (cc or [])]
    cc_list = [r for r in cc_list if r]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(recipients)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    all_recipients = recipients + cc_list
    logger.info("Sending email to=%s subject=%s", all_recipients, subject[:80])

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=60) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(settings.mail_from, all_recipients, msg.as_string())

    logger.info("Email sent to %s", all_recipients)


def format_record_notification(record: DatabaseRecord, extra_message: str | None = None) -> tuple[str, str, str]:
    end = record.end_date.isoformat() if record.end_date else "—"
    subject = f"DB allocation: {record.database_name}"
    lines = [
        f"Database: {record.database_name}",
        f"Type: {record.database_type or '—'}",
        f"Assignee: {record.assignee or '—'}",
        f"Team: {record.team or '—'}",
        f"Status: {record.status or '—'}",
        f"End date: {end}",
        f"Prod mirror: {record.prod_mirror or '—'}",
        f"Can be released: {record.can_be_released or '—'}",
    ]
    if record.comments:
        lines.append(f"Comments: {record.comments}")
    if extra_message:
        lines.append("")
        lines.append(extra_message)
    lines.append("")
    lines.append("— DB Allocation Utility")
    body = "\n".join(lines)
    html = "<br>".join(lines[:-2]) + "<br><br><em>DB Allocation Utility</em>"
    return subject, body, html


def format_records_digest(title: str, records: Sequence[DatabaseRecord], extra_message: str | None = None) -> tuple[str, str, str]:
    subject = f"DB allocation report: {title} ({len(records)} databases)"
    if not records:
        body = f"{title}\n\nNo databases in this list.\n\n— DB Allocation Utility"
        return subject, body, f"<p>{title}</p><p>No databases in this list.</p>"

    lines = [title, f"Count: {len(records)}", ""]
    html_rows = []
    for r in records:
        end = r.end_date.isoformat() if r.end_date else "—"
        line = f"- {r.database_name} | {r.database_type or '—'} | {r.assignee or '—'} | end {end} | {r.status or '—'}"
        lines.append(line)
        html_rows.append(
            f"<tr><td>{r.database_name}</td><td>{r.database_type or '—'}</td>"
            f"<td>{r.assignee or '—'}</td><td>{end}</td><td>{r.status or '—'}</td></tr>"
        )
    if extra_message:
        lines.extend(["", extra_message])
    lines.extend(["", "— DB Allocation Utility"])
    body = "\n".join(lines)
    html = (
        f"<h3>{title}</h3><p>{len(records)} database(s)</p>"
        f"<table border='1' cellpadding='4' cellspacing='0'>"
        f"<tr><th>Database</th><th>Type</th><th>Assignee</th><th>End date</th><th>Status</th></tr>"
        + "".join(html_rows)
        + "</table>"
    )
    if extra_message:
        html += f"<p>{extra_message}</p>"
    html += "<p><em>DB Allocation Utility</em></p>"
    return subject, body, html
