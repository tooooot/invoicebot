"""
InvoiceFollowBot - CLI entry point
Run: python main.py [--dry-run]
"""
from __future__ import annotations
import argparse
import logging
import sys
from datetime import date

import config as cfg
from core.sheets import load_invoices, mark_reminder_sent
from core.gmail import send_reminder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("invoicebot.log"),
    ],
)
logger = logging.getLogger(__name__)


def run(dry_run: bool = False) -> dict:
    """
    Main workflow:
      1. Load invoices from Google Sheet
      2. Find those that need a reminder
      3. Send emails
      4. Update the sheet with today's date in 'Last Reminder'

    Returns a summary dict suitable for Streamlit display.
    """
    logger.info("=" * 60)
    logger.info("InvoiceFollowBot started — %s%s", date.today(), " [DRY RUN]" if dry_run else "")
    logger.info("=" * 60)

    summary = {
        "total":    0,
        "unpaid":   0,
        "reminded": 0,
        "skipped":  0,
        "errors":   0,
        "results":  [],          # list of dicts for the UI
    }

    # ── 1. Load ───────────────────────────────────────────────────────────────
    try:
        invoices = load_invoices()
    except Exception as exc:
        logger.error("Could not load invoices: %s", exc)
        raise

    summary["total"] = len(invoices)
    unpaid = [inv for inv in invoices if inv.is_unpaid]
    summary["unpaid"] = len(unpaid)

    logger.info("Total invoices: %d | Unpaid: %d", summary["total"], summary["unpaid"])

    # ── 2. Filter ─────────────────────────────────────────────────────────────
    to_remind = [
        inv for inv in unpaid
        if inv.needs_reminder(cfg.REMINDER_DAYS_OVERDUE, cfg.REMINDER_COOLDOWN_DAYS)
    ]
    logger.info("Need reminder now: %d", len(to_remind))

    # ── 3. Send ───────────────────────────────────────────────────────────────
    for inv in to_remind:
        result = {
            "invoice_num":  inv.invoice_num,
            "client":       inv.client_name,
            "email":        inv.client_email,
            "amount":       f"{inv.currency}{inv.amount:,.2f}",
            "days_overdue": inv.days_overdue,
            "status":       None,
        }

        ok = send_reminder(inv, dry_run=dry_run)

        if ok:
            result["status"] = "✅ Sent" if not dry_run else "🔵 Dry-run"
            summary["reminded"] += 1
            if not dry_run:
                try:
                    mark_reminder_sent(inv)
                except Exception as exc:
                    logger.warning("Could not update sheet for invoice #%s: %s", inv.invoice_num, exc)
        else:
            result["status"] = "❌ Failed"
            summary["errors"] += 1

        summary["results"].append(result)

    skipped = [inv for inv in unpaid if inv not in to_remind]
    summary["skipped"] = len(skipped)
    for inv in skipped:
        summary["results"].append({
            "invoice_num":  inv.invoice_num,
            "client":       inv.client_name,
            "email":        inv.client_email,
            "amount":       f"{inv.currency}{inv.amount:,.2f}",
            "days_overdue": inv.days_overdue,
            "status":       "⏭ Skipped (cooldown or not overdue)",
        })

    logger.info(
        "Done. Reminded: %d | Skipped: %d | Errors: %d",
        summary["reminded"], summary["skipped"], summary["errors"],
    )
    return summary


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="InvoiceFollowBot")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build and log emails without actually sending them",
    )
    args = parser.parse_args()

    summary = run(dry_run=args.dry_run)

    print("\n── Summary ──────────────────────────────")
    print(f"  Total invoices : {summary['total']}")
    print(f"  Unpaid         : {summary['unpaid']}")
    print(f"  Reminders sent : {summary['reminded']}")
    print(f"  Skipped        : {summary['skipped']}")
    print(f"  Errors         : {summary['errors']}")
    print("─────────────────────────────────────────\n")

    sys.exit(1 if summary["errors"] else 0)


if __name__ == "__main__":
    main()
