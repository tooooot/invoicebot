"""
InvoiceFollowBot - Streamlit UI
Run: streamlit run app.py
"""
from __future__ import annotations
import logging
from datetime import date

import streamlit as st
import pandas as pd

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="InvoiceFollowBot",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lazy imports (show friendly error if deps missing) ────────────────────────
@st.cache_resource
def check_deps():
    missing = []
    try:
        import gspread          # noqa: F401
    except ImportError:
        missing.append("gspread")
    try:
        from google.oauth2.service_account import Credentials  # noqa: F401
    except ImportError:
        missing.append("google-auth")
    return missing


missing_deps = check_deps()
if missing_deps:
    st.error(f"Missing dependencies: {', '.join(missing_deps)}. Run `pip install -r requirements.txt`")
    st.stop()

import config as cfg
from core.invoice import Invoice
from core.sheets import load_invoices, mark_reminder_sent
from core.gmail import send_reminder, test_connection


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🧾 InvoiceFollowBot")
    st.markdown("---")
    page = st.radio("Navigation", ["📊 Dashboard", "📨 Send Reminders", "⚙️ Settings"])
    st.markdown("---")
    st.caption(f"Today: **{date.today()}**")
    st.caption("Data source: Google Sheets")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.header("📊 Invoice Dashboard")

    # Load data
    with st.spinner("Loading invoices from Google Sheet…"):
        try:
            invoices = load_invoices()
            load_error = None
        except Exception as exc:
            invoices = []
            load_error = str(exc)

    if load_error:
        st.error(f"❌ Could not load invoices: {load_error}")
        st.info("Make sure `credentials.json` exists and `SPREADSHEET_ID` is set in `.env`.")
        st.stop()

    if not invoices:
        st.warning("No invoices found in the sheet.")
        st.stop()

    # ── KPI cards ─────────────────────────────────────────────────────────────
    total   = len(invoices)
    unpaid  = [i for i in invoices if i.is_unpaid]
    overdue = [i for i in invoices if i.is_unpaid and i.days_overdue > 0]
    paid    = [i for i in invoices if not i.is_unpaid]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Invoices",  total)
    col2.metric("Unpaid",          len(unpaid),  delta=f"{len(unpaid)} pending",    delta_color="inverse")
    col3.metric("Overdue",         len(overdue), delta=f"{len(overdue)} past due",  delta_color="inverse")
    col4.metric("Paid",            len(paid),    delta=f"{len(paid)} collected",    delta_color="normal")

    st.markdown("---")

    # ── Overdue total (money at risk) ─────────────────────────────────────────
    if overdue:
        # Group by currency for mixed-currency sheets
        by_currency: dict[str, float] = {}
        for inv in overdue:
            by_currency[inv.currency] = by_currency.get(inv.currency, 0) + inv.amount
        overdue_str = "  |  ".join(f"**{cur}{amt:,.2f}**" for cur, amt in by_currency.items())
        st.info(f"💰 Total outstanding (overdue): {overdue_str}")

    # ── Full invoice table ────────────────────────────────────────────────────
    st.subheader("All Invoices")

    filter_status = st.multiselect(
        "Filter by status",
        options=list({i.status for i in invoices}),
        default=list({i.status for i in invoices}),
    )

    rows = [i.to_dict() for i in invoices if i.status in filter_status]
    if rows:
        df = pd.DataFrame(rows).drop(columns=["Row"])
        # Color overdue rows
        def highlight_overdue(row):
            days = int(row.get("Days Overdue", 0))
            if days > 14:
                return ["background-color: #ffd6d6"] * len(row)
            elif days > 0:
                return ["background-color: #fff3cd"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(highlight_overdue, axis=1),
            use_container_width=True,
        )
    else:
        st.info("No invoices match the selected filter.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SEND REMINDERS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📨 Send Reminders":
    st.header("📨 Send Payment Reminders")

    with st.spinner("Loading invoices…"):
        try:
            invoices = load_invoices()
        except Exception as exc:
            st.error(f"❌ {exc}")
            st.stop()

    # ── Controls ──────────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)
    dry_run      = col_a.checkbox("🔵 Dry-run (no email sent)", value=True)
    min_overdue  = col_b.number_input("Minimum days overdue", min_value=0, value=cfg.REMINDER_DAYS_OVERDUE)
    cooldown     = col_c.number_input("Cooldown (days between reminders)", min_value=0, value=cfg.REMINDER_COOLDOWN_DAYS)

    # ── Preview ───────────────────────────────────────────────────────────────
    to_remind = [inv for inv in invoices if inv.needs_reminder(int(min_overdue), int(cooldown))]

    if not to_remind:
        st.success("✅ No invoices need a reminder right now.")
    else:
        st.warning(f"⚠️ {len(to_remind)} invoice(s) will receive a reminder.")
        preview_df = pd.DataFrame([{
            "Client":       i.client_name,
            "Email":        i.client_email,
            "Invoice #":    i.invoice_num,
            "Amount":       f"{i.currency}{i.amount:,.2f}",
            "Due Date":     str(i.due_date),
            "Days Overdue": i.days_overdue,
            "Last Reminder":str(i.last_reminder) if i.last_reminder else "Never",
        } for i in to_remind])
        st.dataframe(preview_df, use_container_width=True)

    # ── Run button ────────────────────────────────────────────────────────────
    if st.button("🚀 Run Reminders", type="primary", disabled=not to_remind):
        st.markdown("---")
        results = []
        progress = st.progress(0)
        status_box = st.empty()

        for i, inv in enumerate(to_remind):
            status_box.info(f"Sending to {inv.client_email}…")
            ok = send_reminder(inv, dry_run=dry_run)
            if ok and not dry_run:
                try:
                    mark_reminder_sent(inv)
                except Exception as exc:
                    st.warning(f"Sheet update failed for #{inv.invoice_num}: {exc}")
            results.append({
                "Invoice #": inv.invoice_num,
                "Client":    inv.client_name,
                "Email":     inv.client_email,
                "Result":    ("✅ Sent" if ok else "❌ Failed") if not dry_run else "🔵 Dry-run",
            })
            progress.progress((i + 1) / len(to_remind))

        status_box.empty()
        st.success("Done!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)

    # ── Manual single-invoice send ────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📧 Send to a specific invoice manually"):
        unpaid = [i for i in invoices if i.is_unpaid]
        if not unpaid:
            st.info("No unpaid invoices.")
        else:
            options = {f"#{i.invoice_num} – {i.client_name} ({i.client_email})": i for i in unpaid}
            selected_label = st.selectbox("Choose invoice", list(options.keys()))
            selected_inv   = options[selected_label]
            manual_dry     = st.checkbox("Dry-run", value=True, key="manual_dry")

            if st.button("Send Now", key="manual_send"):
                ok = send_reminder(selected_inv, dry_run=manual_dry)
                if ok:
                    if not manual_dry:
                        mark_reminder_sent(selected_inv)
                        st.success(f"✅ Reminder sent to {selected_inv.client_email}")
                    else:
                        st.info(f"🔵 Dry-run: would send to {selected_inv.client_email}")
                else:
                    st.error("❌ Failed to send. Check logs.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Settings":
    st.header("⚙️ Settings & Status")

    # ── Current config display ────────────────────────────────────────────────
    st.subheader("Current Configuration")
    st.markdown("Edit `.env` to change these values, then restart the app.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Gmail**")
        st.code(f"GMAIL_USER       = {cfg.GMAIL_USER or '(not set)'}")
        st.code(f"GMAIL_APP_PASS   = {'*' * 8 if cfg.GMAIL_APP_PASS else '(not set)'}")
        st.code(f"GMAIL_SENDER_NAME= {cfg.GMAIL_SENDER_NAME}")

    with col2:
        st.markdown("**Google Sheets**")
        st.code(f"SPREADSHEET_ID   = {cfg.SPREADSHEET_ID or '(not set)'}")
        st.code(f"SHEET_NAME       = {cfg.SHEET_NAME}")
        st.code(f"GOOGLE_CREDS_FILE= {cfg.GOOGLE_CREDS_FILE}")

    st.markdown("**Reminder Rules**")
    c1, c2 = st.columns(2)
    c1.metric("Minimum overdue (days)", cfg.REMINDER_DAYS_OVERDUE)
    c2.metric("Cooldown between reminders (days)", cfg.REMINDER_COOLDOWN_DAYS)

    st.markdown("---")

    # ── Connection tests ──────────────────────────────────────────────────────
    st.subheader("🔌 Connection Tests")

    col_g, col_s = st.columns(2)
    with col_g:
        if st.button("Test Gmail Connection"):
            with st.spinner("Connecting to Gmail SMTP…"):
                ok, msg = test_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with col_s:
        if st.button("Test Google Sheets"):
            with st.spinner("Reading sheet…"):
                try:
                    invoices = load_invoices()
                    st.success(f"✅ Sheet loaded — {len(invoices)} row(s) found.")
                except Exception as exc:
                    st.error(f"❌ {exc}")

    # ── Expected sheet format ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Expected Google Sheet Format")
    st.markdown(
        "Your sheet must have a **header row** with these column names "
        "(order doesn't matter, case-insensitive):"
    )
    example = pd.DataFrame({
        "Client Name":   ["Acme Corp",    "TechStart Ltd"],
        "Client Email":  ["ar@acme.com",  "pay@techstart.io"],
        "Invoice #":     ["INV-001",      "INV-002"],
        "Amount":        [1500.00,        800.00],
        "Currency":      ["$",            "$"],
        "Due Date":      ["2024-01-15",   "2024-02-01"],
        "Status":        ["Unpaid",       "Paid"],
        "Last Reminder": ["2024-01-18",   ""],
        "Notes":         ["Net 30",       ""],
    })
    st.dataframe(example, use_container_width=True)

    st.markdown("---")
    st.subheader("📖 Logs")
    try:
        with open("invoicebot.log") as f:
            log_lines = f.readlines()
        last_100 = "".join(log_lines[-100:])
        st.code(last_100, language="text")
    except FileNotFoundError:
        st.info("No logs yet. Run the bot first.")
