"""Send email via SMTP or Microsoft Graph (Outlook / Office 365)."""

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
from app.services import graph_mail

logger = get_logger("app.email")

_EMAIL_LIKE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_BASIC_AUTH_DISABLED_HINT = (
    "Microsoft 365 blocked SMTP username/password (error 5.7.139). "
    "Your organization disabled basic authentication. "
    "Switch to Microsoft Graph in backend/.env: EMAIL_PROVIDER=graph and set "
    "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, GRAPH_SEND_AS. "
    "See README → Email via Microsoft Outlook."
)


def _provider() -> str:
    p = (settings.email_provider or "smtp").strip().lower()
    if p == "graph" or (p == "auto" and graph_mail.is_graph_configured()):
        return "graph"
    return "smtp"


def is_smtp_configured() -> bool:
    return bool(
        settings.email_enabled
        and settings.smtp_host
        and settings.smtp_user
        and settings.smtp_password
        and settings.mail_from
    )


def is_email_configured() -> bool:
    if not settings.email_enabled:
        return False
    if _provider() == "graph":
        return graph_mail.is_graph_configured()
    return is_smtp_configured()


def email_provider_label() -> str:
    return _provider()


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


def _send_via_smtp(
    to: Sequence[str],
    subject: str,
    body_text: str,
    *,
    body_html: str | None = None,
    cc: Sequence[str] | None = None,
) -> None:
    if not is_smtp_configured():
        raise RuntimeError(
            "SMTP is not configured. Set SMTP_USER, SMTP_PASSWORD, MAIL_FROM in backend/.env"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    all_recipients = list(to) + list(cc or [])
    logger.info("SMTP send to=%s subject=%s", all_recipients, subject[:80])

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=60) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.mail_from, all_recipients, msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        err = str(exc).lower()
        if "5.7.139" in err or "basic authentication is disabled" in err:
            raise RuntimeError(_BASIC_AUTH_DISABLED_HINT) from exc
        raise

    logger.info("SMTP email sent to %s", all_recipients)


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
            "Email is not configured. Set EMAIL_ENABLED=true in backend/.env (see README)."
        )

    recipients = [normalize_email(r) for r in to]
    recipients = [r for r in recipients if r]
    if not recipients:
        raise ValueError("At least one valid recipient email is required")

    cc_list = [normalize_email(r) for r in (cc or [])]
    cc_list = [r for r in cc_list if r]

    if _provider() == "graph":
        graph_mail.send_via_graph(
            recipients, subject, body_text, body_html=body_html, cc=cc_list
        )
    else:
        _send_via_smtp(recipients, subject, body_text, body_html=body_html, cc=cc_list)


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
