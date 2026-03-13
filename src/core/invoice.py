"""
InvoiceFollowBot - Invoice data model & helpers
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]


def parse_date(value: str) -> Optional[date]:
    """Try multiple date formats and return a date object, or None."""
    value = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Invoice:
    row_index: int                   # 1-based row in the sheet (for updates)
    client_name: str
    client_email: str
    invoice_num: str
    amount: float
    currency: str
    due_date: Optional[date]
    status: str
    last_reminder: Optional[date]
    notes: str = ""

    # ── derived ───────────────────────────────────────────────────────────────
    @property
    def days_overdue(self) -> int:
        """How many calendar days past the due date (0 if not yet overdue)."""
        if self.due_date is None:
            return 0
        delta = date.today() - self.due_date
        return max(0, delta.days)

    @property
    def is_unpaid(self) -> bool:
        return self.status.strip().lower() in ("unpaid", "partial", "overdue", "")

    @property
    def days_since_last_reminder(self) -> Optional[int]:
        if self.last_reminder is None:
            return None
        return (date.today() - self.last_reminder).days

    def needs_reminder(self, min_overdue: int, cooldown: int) -> bool:
        """
        Return True when:
          - invoice is unpaid
          - overdue by at least `min_overdue` days
          - no reminder was sent in the last `cooldown` days
        """
        if not self.is_unpaid:
            return False
        if self.days_overdue < min_overdue:
            return False
        if self.days_since_last_reminder is not None and \
                self.days_since_last_reminder < cooldown:
            return False
        return True

    # ── convenience ──────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "Row":           self.row_index,
            "Client":        self.client_name,
            "Email":         self.client_email,
            "Invoice #":     self.invoice_num,
            "Amount":        f"{self.currency}{self.amount:,.2f}",
            "Due Date":      str(self.due_date) if self.due_date else "—",
            "Days Overdue":  self.days_overdue,
            "Status":        self.status,
            "Last Reminder": str(self.last_reminder) if self.last_reminder else "Never",
        }
