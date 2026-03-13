"""
InvoiceFollowBot - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Gmail Settings ────────────────────────────────────────────────────────────
GMAIL_USER     = os.getenv("GMAIL_USER", "")          # your Gmail address
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS", "")      # Gmail App Password (not your real password)
GMAIL_SENDER_NAME = os.getenv("GMAIL_SENDER_NAME", "InvoiceFollowBot")

# ── Google Sheets Settings ────────────────────────────────────────────────────
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
SPREADSHEET_ID    = os.getenv("SPREADSHEET_ID", "")   # from the Sheet URL
SHEET_NAME        = os.getenv("SHEET_NAME", "Invoices")

# ── Reminder Rules ────────────────────────────────────────────────────────────
# Send reminder when invoice is overdue by at least this many days
REMINDER_DAYS_OVERDUE  = int(os.getenv("REMINDER_DAYS_OVERDUE", "1"))
# Don't send more than one reminder per invoice per this many days
REMINDER_COOLDOWN_DAYS = int(os.getenv("REMINDER_COOLDOWN_DAYS", "3"))

# ── Expected Google Sheet columns (zero-indexed column names) ─────────────────
# Make sure your Sheet header row matches these exactly (case-insensitive)
COL_CLIENT_NAME  = "Client Name"
COL_CLIENT_EMAIL = "Client Email"
COL_INVOICE_NUM  = "Invoice #"
COL_AMOUNT       = "Amount"
COL_CURRENCY     = "Currency"
COL_DUE_DATE     = "Due Date"        # format: YYYY-MM-DD or MM/DD/YYYY
COL_STATUS       = "Status"          # Unpaid / Paid / Partial
COL_LAST_REMINDER = "Last Reminder"  # auto-filled by bot (YYYY-MM-DD)
COL_NOTES        = "Notes"

# ── Email Template ────────────────────────────────────────────────────────────
EMAIL_SUBJECT_TEMPLATE = "Payment Reminder – Invoice #{invoice_num}"

EMAIL_BODY_TEMPLATE = """\
Dear {client_name},

I hope this message finds you well.

This is a friendly reminder that Invoice #{invoice_num} for {currency}{amount} 
was due on {due_date} and remains unpaid as of today.

Please arrange payment at your earliest convenience.  If you have already sent 
payment, kindly disregard this message and accept our thanks.

If you have any questions or concerns, please don't hesitate to reach out.

Best regards,
{sender_name}
"""
