# 🧾 InvoiceFollowBot

**InvoiceFollowBot** is a lightweight Python tool that automatically tracks unpaid invoices stored in a Google Sheet and sends payment reminders via Gmail.

---

## Features

- 📊 **Reads your Google Sheet** — client name, email, amount, due date, and status
- 📧 **Sends HTML + plain-text reminders** via Gmail SMTP (App Password — no OAuth dance)
- ⏱ **Smart scheduling** — configurable minimum overdue days and cooldown between reminders
- 📝 **Auto-updates the sheet** — writes today's date into the "Last Reminder" column after each send
- 🖥️ **Streamlit dashboard** — view invoices, trigger reminders manually, test connections
- 🔵 **Dry-run mode** — preview what would be sent without hitting Send

---

## Project Structure

```
invoicebot/
├── app.py              ← Streamlit UI (dashboard, reminders, settings)
├── main.py             ← CLI entry point
├── config.py           ← All configuration variables
├── core/
│   ├── invoice.py      ← Invoice data model & helpers
│   ├── sheets.py       ← Google Sheets reader/writer (gspread)
│   └── gmail.py        ← Gmail SMTP sender
├── requirements.txt
├── .env.example        ← Copy to .env and fill in your values
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up Gmail App Password

1. Enable **2-Step Verification** on your Google Account
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create a new App Password (App: Mail, Device: Other → type "InvoiceFollowBot")
4. Copy the 16-character password

### 3. Set up Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create a service account
5. Download the JSON key file and save it as `credentials.json` in this folder
6. **Share your Google Sheet** with the service account email (found in the JSON file under `client_email`) — give it **Editor** access

### 4. Prepare your Google Sheet

Create a Google Sheet with a header row containing these columns (exact names, case-insensitive):

| Client Name | Client Email | Invoice # | Amount | Currency | Due Date   | Status | Last Reminder | Notes |
|-------------|--------------|-----------|--------|----------|------------|--------|---------------|-------|
| Acme Corp   | ar@acme.com  | INV-001   | 1500   | $        | 2024-01-15 | Unpaid |               | Net 30|

- **Status** should be: `Unpaid`, `Paid`, or `Partial`
- **Due Date** formats accepted: `YYYY-MM-DD`, `MM/DD/YYYY`, `DD/MM/YYYY`
- **Last Reminder** is auto-filled by the bot — leave it blank initially

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
GMAIL_USER=you@gmail.com
GMAIL_APP_PASS=xxxx xxxx xxxx xxxx
GMAIL_SENDER_NAME=Your Company Name
SPREADSHEET_ID=your_sheet_id_here
SHEET_NAME=Invoices
```

Your Sheet ID is in the URL:  
`https://docs.google.com/spreadsheets/d/**<SPREADSHEET_ID>**/edit`

---

## Usage

### Option A — Streamlit UI (recommended)

```bash
streamlit run app.py
```

Opens at [http://localhost:8501](http://localhost:8501) with three pages:

| Page | Description |
|------|-------------|
| 📊 Dashboard | View all invoices, KPI cards, overdue highlights |
| 📨 Send Reminders | Preview & send reminders, manual single-invoice send |
| ⚙️ Settings | View config, test Gmail & Sheets connections, view logs |

### Option B — CLI

```bash
# Normal run (sends real emails)
python main.py

# Dry run — see what would be sent without sending
python main.py --dry-run
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GMAIL_USER` | — | Your Gmail address |
| `GMAIL_APP_PASS` | — | Gmail App Password |
| `GMAIL_SENDER_NAME` | `InvoiceFollowBot` | Name shown in From field |
| `GOOGLE_CREDS_FILE` | `credentials.json` | Path to service account key |
| `SPREADSHEET_ID` | — | Google Sheet ID from URL |
| `SHEET_NAME` | `Invoices` | Worksheet tab name |
| `REMINDER_DAYS_OVERDUE` | `1` | Min days past due before first reminder |
| `REMINDER_COOLDOWN_DAYS` | `3` | Min days between reminders to same client |

---

## Email Template

The reminder email is built from templates in `config.py`:

```
Subject: Payment Reminder – Invoice #INV-001

Dear Acme Corp,

This is a friendly reminder that Invoice #INV-001 for $1,500.00
was due on 2024-01-15 and remains unpaid as of today.

Please arrange payment at your earliest convenience.
...
```

To customize, edit `EMAIL_SUBJECT_TEMPLATE` and `EMAIL_BODY_TEMPLATE` in `config.py`.

---

## Automation (optional)

To run the bot automatically every morning, add a cron job:

```bash
# Run every day at 8 AM
0 8 * * * cd /path/to/invoicebot && python main.py >> invoicebot.log 2>&1
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `SMTPAuthenticationError` | Use an **App Password**, not your regular Gmail password |
| `SPREADSHEET_NOT_FOUND` | Share the Sheet with your service account email |
| `FileNotFoundError: credentials.json` | Check `GOOGLE_CREDS_FILE` path in `.env` |
| Reminders not sending | Check `REMINDER_DAYS_OVERDUE` — invoice may not be overdue yet |
| Cooldown skipping sends | Last reminder was too recent — check `Last Reminder` column |

---

## License

MIT — free to use, modify, and distribute.
