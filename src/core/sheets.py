"""
InvoiceFollowBot - Google Sheets integration via gspread
"""
from __future__ import annotations
import logging
from datetime import date
from typing import List, Optional

import gspread
from google.oauth2.service_account import Credentials

from core.invoice import Invoice, parse_date
import config as cfg

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── internal helpers ──────────────────────────────────────────────────────────

def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(cfg.GOOGLE_CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _col_index(headers: list, name: str) -> Optional[int]:
    """Return 0-based index of *name* in headers (case-insensitive), or None."""
    name_lower = name.lower()
    for i, h in enumerate(headers):
        if str(h).strip().lower() == name_lower:
            return i
    return None


def _safe(row: list, idx: Optional[int], default="") -> str:
    if idx is None:
        return default
    try:
        return str(row[idx]).strip()
    except IndexError:
        return default


# ── public API ────────────────────────────────────────────────────────────────

def load_invoices() -> List[Invoice]:
    """
    Read the Google Sheet and return a list of Invoice objects.
    Row 1 is assumed to be the header row.
    """
    client    = _get_client()
    sheet     = client.open_by_key(cfg.SPREADSHEET_ID)
    worksheet = sheet.worksheet(cfg.SHEET_NAME)

    all_rows = worksheet.get_all_values()
    if not all_rows:
        logger.warning("Sheet is empty.")
        return []

    headers = all_rows[0]
    logger.info("Loaded %d data rows from sheet '%s'", len(all_rows) - 1, cfg.SHEET_NAME)

    # Map expected columns → indices
    idx = {
        "name":    _col_index(headers, cfg.COL_CLIENT_NAME),
        "email":   _col_index(headers, cfg.COL_CLIENT_EMAIL),
        "inv":     _col_index(headers, cfg.COL_INVOICE_NUM),
        "amount":  _col_index(headers, cfg.COL_AMOUNT),
        "cur":     _col_index(headers, cfg.COL_CURRENCY),
        "due":     _col_index(headers, cfg.COL_DUE_DATE),
        "status":  _col_index(headers, cfg.COL_STATUS),
        "remind":  _col_index(headers, cfg.COL_LAST_REMINDER),
        "notes":   _col_index(headers, cfg.COL_NOTES),
    }

    invoices = []
    for row_num, row in enumerate(all_rows[1:], start=2):   # row_num = sheet row (1-based)
        # Skip completely empty rows
        if not any(row):
            continue

        try:
            amount_str = _safe(row, idx["amount"], "0").replace(",", "").replace("$", "")
            amount = float(amount_str) if amount_str else 0.0
        except ValueError:
            amount = 0.0

        inv = Invoice(
            row_index     = row_num,
            client_name   = _safe(row, idx["name"]),
            client_email  = _safe(row, idx["email"]),
            invoice_num   = _safe(row, idx["inv"]),
            amount        = amount,
            currency      = _safe(row, idx["cur"], "$"),
            due_date      = parse_date(_safe(row, idx["due"])),
            status        = _safe(row, idx["status"], "Unpaid"),
            last_reminder = parse_date(_safe(row, idx["remind"])),
            notes         = _safe(row, idx["notes"]),
        )
        invoices.append(inv)

    return invoices


def mark_reminder_sent(invoice: Invoice) -> None:
    """
    Write today's date into the 'Last Reminder' column for this invoice.
    """
    if _col_index is None:
        return

    client    = _get_client()
    sheet     = client.open_by_key(cfg.SPREADSHEET_ID)
    worksheet = sheet.worksheet(cfg.SHEET_NAME)

    headers = worksheet.row_values(1)
    col_idx = _col_index(headers, cfg.COL_LAST_REMINDER)
    if col_idx is None:
        logger.warning("Column '%s' not found — cannot update last reminder.", cfg.COL_LAST_REMINDER)
        return

    # gspread uses 1-based column numbers
    col_letter = gspread.utils.rowcol_to_a1(invoice.row_index, col_idx + 1).rstrip("0123456789")
    cell = f"{col_letter}{invoice.row_index}"
    worksheet.update(cell, [[str(date.today())]])
    logger.info("Marked reminder sent for invoice #%s (cell %s)", invoice.invoice_num, cell)
