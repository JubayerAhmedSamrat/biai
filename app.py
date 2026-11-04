import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crm.db"
CSV_PATH = BASE_DIR / "data" / "sample-enquiries.csv"

PIPELINE = ["New", "Contacted", "Interested", "Paid", "Lost"]
INTERESTS = ["Bootcamp", "Fellowship", "Corporate training", "Other"]
INTENT_TYPES = ["Sales enquiry", "Support", "Spam", "Job enquiry", "General"]

st.set_page_config(page_title="BIAI CRM", page_icon="📇", layout="wide")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT,
                received_at TEXT,
                name TEXT,
                phone TEXT,
                channel TEXT,
                message TEXT NOT NULL,
                interest TEXT DEFAULT 'Other',
                intent_type TEXT DEFAULT 'General',
                status TEXT DEFAULT 'New',
                priority TEXT DEFAULT 'Normal',
                summary TEXT DEFAULT '',
                language TEXT DEFAULT 'Unknown',
                suggested_reply TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0]
        if count == 0 and CSV_PATH.exists():
            df = pd.read_csv(CSV_PATH).fillna("")
            for _, r in df.iterrows():
                conn.execute("""
                    INSERT INTO enquiries
                    (source_id, received_at, name, phone, channel, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(r.get("id", "")), str(r.get("received at", "")),
                    str(r.get("sender name", "")), str(r.get("phone", "")),
                    str(r.get("channel", "")), str(r.get("message", ""))
                ))


def get_api_key():
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "") or st.secrets.get("GEMINI_KEY", "")
    except Exception:
        return ""


def call_gemini(prompt):
    key = get_api_key()
    if not key:
        raise RuntimeError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")
    from google import genai
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)


def extract_message(message, sender="", phone="", channel="Unknown"):
    prompt = f"""
You are an assistant for BIAI, a Bangladesh-based AI training institute.
Analyze this enquiry and return ONLY valid JSON with these keys:
name, phone, interest, intent_type, priority, summary, language, suggested_reply.
Rules:
- interest must be one of: Bootcamp, Fellowship, Corporate training, Other.
- intent_type must be one of: Sales enquiry, Support, Spam, Job enquiry, General.
- priority must be one of: Low, Normal, High, Urgent.
- status is not needed; a human will choose the pipeline status.
- Preserve supplied sender name/phone unless the message clearly corrects them.
- Do not invent prices, dates, refund rules, course guarantees, certificates, or policies.
- For complaints/payment/refund issues, acknowledge the concern and suggest a human team member follow up.
- Match the language/style of the original message (Bangla, Banglish, or English).
- Keep suggested_reply concise, polite, and ready for a human to review.
- If the message is spam or a job application, do not treat it as a sales lead.
Sender name: {sender}
Phone: {phone}
Channel: {channel}
Message: {message}
"""
    return call_gemini(prompt)


def save_enquiry(data):
    with db() as conn:
        conn.execute("""
            INSERT INTO enquiries
            (name, phone, channel, message, interest, intent_type, status,
             priority, summary, language, suggested_reply)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name", ""), data.get("phone", ""), data.get("channel", "Manual"),
            data["message"], data.get("interest", "Other"),
            data.get("intent_type", "General"), data.get("status", "New"),
            data.get("priority", "Normal"), data.get("summary", ""),
            data.get("language", "Unknown"), data.get("suggested_reply", "")
        ))


def load_data():
    with db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM enquiries ORDER BY received_at DESC, id DESC", conn
        )


def update_field(enquiry_id, field, value):
    allowed = {"status", "priority", "interest", "intent_type", "suggested_reply"}
    if field not in allowed:
        return
    with db() as conn:
        conn.execute(f"UPDATE enquiries SET {field} = ? WHERE id = ?", (value, enquiry_id))


init_db()
st.title("📇 BIAI Enquiry CRM")
st.caption("A lightweight CRM prototype · Sample data supplied for the BIAI AI Intern Round 2 task")

df = load_data()

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to", ["Dashboard", "Enquiries", "Add enquiry", "AI reply assistant"])
    st.divider()
    st.caption("AI provider: Gemini 2.5 Flash")
    st.caption("Database: local SQLite")

if page == "Dashboard":
    st.subheader("Overview")
    total = len(df)
    sales = int((df["intent_type"] == "Sales enquiry").sum()) if total else 0
    support = int((df["intent_type"] == "Support").sum()) if total else 0
    urgent = int((df["priority"] == "Urgent").sum()) if total else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total messages", total)
    c2.metric("Sales enquiries", sales)
    c3.metric("Support cases", support)
    c4.metric("Urgent", urgent)

    st.subheader("Sales pipeline")
    cols = st.columns(5)
    for col, status in zip(cols, PIPELINE):
        count = int((df["status"] == status).sum()) if total else 0
        col.metric(status, count)

    st.subheader("Needs attention")
    attention = df[(df["priority"].isin(["High", "Urgent"])) |
                   (df["intent_type"].isin(["Support", "Job enquiry", "Spam"]))]
    if attention.empty:
        st.success("Nothing flagged for attention.")
    else:
        st.dataframe(attention[["name", "channel", "intent_type", "priority", "summary"]],
                     use_container_width=True, hide_index=True)

    if total:
        st.subheader("Enquiry types")
        st.bar_chart(df["intent_type"].value_counts())

elif page == "Enquiries":
    st.subheader("Enquiry inbox")
    f1, f2, f3 = st.columns(3)
    intent_filter = f1.selectbox("Type", ["All"] + INTENT_TYPES)
    status_filter = f2.selectbox("Pipeline status", ["All"] + PIPELINE)
    search = f3.text_input("Search name, phone or message")
    view = df.copy()
    if intent_filter != "All":
        view = view[view["intent_type"] == intent_filter]
    if status_filter != "All":
        view = view[view["status"] == status_filter]
    if search:
        mask = (
            view["name"].astype(str).str.contains(search, case=False, na=False) |
            view["phone"].astype(str).str.contains(search, case=False, na=False) |
            view["message"].astype(str).str.contains(search, case=False, na=False)
        )
        view = view[mask]
    st.dataframe(view[["id", "name", "phone", "channel", "interest", "intent_type",
                       "status", "priority", "message"]],
                 use_container_width=True, hide_index=True)

    if not view.empty:
        selected_id = st.selectbox("Open enquiry", view["id"].tolist(),
                                   format_func=lambda x: f"#{x} — {view.loc[view.id == x, 'name'].iloc[0] or 'Unknown'}")
        record = view[view["id"] == selected_id].iloc[0]
        st.markdown("#### Enquiry details")
        st.write(record["message"])
        if record["summary"]:
            st.info(record["summary"])
        if record["phone"]:
            duplicates = df[(df["phone"] == record["phone"]) & (df["phone"] != "")]
            if len(duplicates) > 1:
                st.warning(f"Possible repeat contact: this phone number appears in {len(duplicates)} enquiries.")
        with st.form("update_enquiry"):
            a, b, c = st.columns(3)
            new_status = a.selectbox("Pipeline status", PIPELINE,
                                     index=PIPELINE.index(record["status"]) if record["status"] in PIPELINE else 0)
            new_priority = b.selectbox("Priority", ["Low", "Normal", "High", "Urgent"],
                                       index=["Low", "Normal", "High", "Urgent"].index(record["priority"])
                                       if record["priority"] in ["Low", "Normal", "High", "Urgent"] else 1)
            new_interest = c.selectbox("Interest", INTERESTS,
                                       index=INTERESTS.index(record["interest"]) if record["interest"] in INTERESTS else 3)
            if st.form_submit_button("Save changes"):
                update_field(selected_id, "status", new_status)
                update_field(selected_id, "priority", new_priority)
                update_field(selected_id, "interest", new_interest)
                st.success("Enquiry updated.")
                st.rerun()

elif page == "Add enquiry":
    st.subheader("Add an enquiry")
    st.write("Paste a message and let AI extract the details. Review everything before saving.")
    if "parsed" not in st.session_state:
        st.session_state.parsed = {}
    with st.form("parse_message"):
        sender = st.text_input("Sender name")
        phone = st.text_input("Phone number")
        channel = st.selectbox("Source channel", ["WhatsApp", "Facebook Messenger",
                                                  "Facebook comment", "Website form",
                                                  "Phone call note", "Other"])
        message = st.text_area("Message", height=140)
        parse = st.form_submit_button("✨ Extract details with AI")
    if parse:
        if not message.strip():
            st.error("Please paste a message first.")
        else:
            try:
                st.session_state.parsed = extract_message(message, sender, phone, channel)
                st.session_state.parsed.update({"message": message, "channel": channel})
                st.success("AI extraction complete. Review the fields below.")
            except Exception as e:
                st.error(f"AI extraction failed: {e}")
    parsed = st.session_state.parsed
    if parsed:
        st.markdown("#### Review and save")
        with st.form("save_parsed"):
            name_value = st.text_input("Name", value=str(parsed.get("name", sender if 'sender' in locals() else "")))
            phone_value = st.text_input("Phone", value=str(parsed.get("phone", phone if 'phone' in locals() else "")))
            interest_value = st.selectbox("Interest", INTERESTS,
                index=INTERESTS.index(parsed.get("interest", "Other"))
                if parsed.get("interest", "Other") in INTERESTS else 3)
            intent_value = st.selectbox("Enquiry type", INTENT_TYPES,
                index=INTENT_TYPES.index(parsed.get("intent_type", "General"))
                if parsed.get("intent_type", "General") in INTENT_TYPES else 4)
            priority_value = st.selectbox("Priority", ["Low", "Normal", "High", "Urgent"],
                index=["Low", "Normal", "High", "Urgent"].index(parsed.get("priority", "Normal"))
                if parsed.get("priority", "Normal") in ["Low", "Normal", "High", "Urgent"] else 1)
            summary_value = st.text_area("AI summary", value=str(parsed.get("summary", "")))
            reply_value = st.text_area("Suggested reply (editable)", value=str(parsed.get("suggested_reply", "")))
            if st.form_submit_button("Save enquiry"):
                save_enquiry({
                    "name": name_value, "phone": phone_value,
                    "channel": parsed.get("channel", "Manual"),
                    "message": parsed.get("message", ""),
                    "interest": interest_value, "intent_type": intent_value,
                    "priority": priority_value, "summary": summary_value,
                    "language": parsed.get("language", "Unknown"),
                    "suggested_reply": reply_value
                })
                st.session_state.parsed = {}
                st.success("Enquiry saved.")
                st.rerun()

elif page == "AI reply assistant":
    st.subheader("AI reply assistant")
    if df.empty:
        st.info("No enquiries yet.")
    else:
        ids = df["id"].tolist()
        selected_id = st.selectbox("Choose an enquiry", ids,
            format_func=lambda x: f"#{x} — {df.loc[df.id == x, 'name'].iloc[0] or 'Unknown'}")
        record = df[df["id"] == selected_id].iloc[0]
        st.markdown("**Original message**")
        st.write(record["message"])
        if record["suggested_reply"]:
            st.markdown("**Saved suggested reply**")
            st.text_area("Reply draft", value=record["suggested_reply"], height=120, key="saved_reply")
        if st.button("Generate a fresh reply with AI"):
            try:
                result = call_gemini(f"""
Write a concise, polite customer-service reply for BIAI.
Match the original language and style (Bangla, Banglish, or English).
Do not invent prices, dates, refund rules, guarantees, or policies.
For complaints, payment issues, or refunds, acknowledge the issue and say a team member will follow up.
Classify context: {record['intent_type']}
Customer message: {record['message']}
Return JSON only: {{"reply": "..."}}
""")
                st.session_state["fresh_reply"] = result.get("reply", "")
                update_field(selected_id, "suggested_reply", st.session_state["fresh_reply"])
            except Exception as e:
                st.error(f"Could not generate reply: {e}")
        if st.session_state.get("fresh_reply"):
            st.text_area("New AI reply", value=st.session_state["fresh_reply"], height=140)
            st.caption("Review the draft before sending it to a customer.")
