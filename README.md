# BIAI Enquiry CRM

A small Streamlit + SQLite CRM prototype for the BIAI AI Intern Round 2 Task 1.

## Features
- Imports the 20 fictional sample enquiries on first launch.
- Enquiry inbox with search and filters.
- Pipeline: New, Contacted, Interested, Paid, Lost.
- Gemini-powered message extraction and reply drafting.
- Separates sales enquiries, support, spam, job enquiries and general messages.
- Flags possible repeat contacts by phone number.
- Keeps AI suggestions editable and requires human review.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

Set your Gemini key (use either variable name):

```bash
# Linux/macOS
export GEMINI_API_KEY="your_key"

# Windows PowerShell
$env:GEMINI_API_KEY="your_key"
```

Then run:

```bash
streamlit run app.py
```

The app opens in your browser. The database `crm.db` is created locally.
The sample CSV is loaded automatically the first time the app starts.

## Important notes
- Use only the fictional sample data in the assignment pack.
- AI output is a draft. A staff member must review replies, especially payment/refund complaints.
- This is an internship-task prototype, not a production CRM. Authentication, role permissions,
  audit logs, backups, and secure deployment are future work.
