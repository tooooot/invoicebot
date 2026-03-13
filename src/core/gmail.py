"""
InvoiceFollowBot - Gmail sender via SMTP + App Password
"""
from __future__ import annotations
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import config as cfg
from core.invoice import Invoice

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _build_message(invoice: Invoice) -> MIMEMultipart:
    """Render subject + body from templates and wrap in a MIME message."""
    subject = cfg.EMAIL_SUBJECT_TEMPLATE.format(
        invoice_num=invoice.invoice_num,
        client_name=invoice.client_name,
    )

    body = cfg.EMAIL_BODY_TEMPLATE.format(
        client_name=invoice.client_name,
        invoice_num=invoice.invoice_num,
        amount=f"{invoice.amount:,.2f}",
        currency=invoice.currency,
        due_date=str(invoice.due_date) if invoice.due_date else "N/A",
        days_overdue=invoice.days_overdue,
        sender_name=cfg.GMAIL_SENDER_NAME,
    )

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"{cfg.GMAIL_SENDER_NAME} <{cfg.GMAIL_USER}>"
    msg["To"]      = invoice.client_email
    msg["Subject"] = subject

    # Plain-text part
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Simple HTML version
    html_body = body.replace("\n", "<br>")
    html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;margin:auto;padding:20px;">
  <div style="background:#f9f9f9;border:1px solid #ddd;border-radius:8px;padding:30px;">
    <h2 style="color:#c0392b;">⚠️ Payment Reminder</h2>
    <p>{html_body}</p>
    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="font-size:12px;color:#999;">
      This is an automated reminder sent by InvoiceFollowBot.<br>
      Please do not reply to this email if it was received in error.
    </p>
  </div>
</body>
</html>"""
    msg.attach(MIMEText(html, "html", "utf-8"))

    return msg


def send_reminder(invoice: Invoice, dry_run: bool = False) -> bool:
    """
    Send a reminder email for the given invoice.

    Parameters
    ----------
    invoice : Invoice
    dry_run : bool
        If True, build the message but don't actually send it (for testing).

    Returns
    -------
    bool  – True if sent (or dry-run success), False on error.
    """
    if not cfg.GMAIL_USER or not cfg.GMAIL_APP_PASS:
        logger.error("GMAIL_USER or GMAIL_APP_PASS not configured.")
        return False

    if not invoice.client_email:
        logger.warning("Invoice #%s has no client email — skipping.", invoice.invoice_num)
        return False

    msg = _build_message(invoice)

    if dry_run:
        logger.info("[DRY RUN] Would send to %s: %s", invoice.client_email, msg["Subject"])
        return True

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg.GMAIL_USER, cfg.GMAIL_APP_PASS)
            smtp.sendmail(cfg.GMAIL_USER, invoice.client_email, msg.as_string())
        logger.info("Reminder sent → %s (Invoice #%s)", invoice.client_email, invoice.invoice_num)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail authentication failed. Check GMAIL_USER and GMAIL_APP_PASS.\n"
            "Make sure you created an App Password at https://myaccount.google.com/apppasswords"
        )
        return False
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", invoice.client_email, exc)
        return False


def test_connection() -> tuple[bool, str]:
    """
    Verify Gmail SMTP credentials without sending any email.
    Returns (success: bool, message: str).
    """
    if not cfg.GMAIL_USER or not cfg.GMAIL_APP_PASS:
        return False, "GMAIL_USER or GMAIL_APP_PASS is not set."
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg.GMAIL_USER, cfg.GMAIL_APP_PASS)
        return True, f"✅ Connected as {cfg.GMAIL_USER}"
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Authentication failed. Check your App Password."
    except Exception as exc:
        return False, f"❌ Connection error: {exc}"
