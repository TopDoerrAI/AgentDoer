"""
Email tools: send, inbox list, read, summarize, search, draft.
Supports Gmail/Outlook via IMAP+SMTP (app passwords) or SendGrid for send-only.
"""
import email
import imaplib
import smtplib
import time
from contextlib import contextmanager
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain.tools import tool

from app.core.config import get_settings


@contextmanager
def _with_imap(folder: str = "INBOX"):
    s = get_settings()
    conn = imaplib.IMAP4_SSL(s.email_imap_host, s.email_imap_port)
    conn.login(s.email_imap_user, s.email_imap_password)
    conn.select(folder)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass


def _decode_header_value(header: str | None) -> str:
    if not header:
        return ""
    parts = decode_header(header)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(part))
    return " ".join(out).strip()


def _extract_body(msg: email.message.Message) -> tuple[str, str]:
    plain, html = "", ""
    for part in msg.walk():
        if part.get_content_maintype() == "text":
            payload = part.get_payload(decode=True)
            if payload:
                try:
                    text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                except Exception:
                    text = payload.decode("utf-8", errors="replace")
                if part.get_content_subtype() == "html":
                    html += text
                else:
                    plain += text
    if not plain and html:
        plain = html.replace("<br>", "\n").replace("</p>", "\n")
        import re
        plain = re.sub(r"<[^>]+>", "", plain)
    return (plain.strip(), html.strip())


def _parse_message(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw)
    plain, html = _extract_body(msg)
    return {
        "from": _decode_header_value(msg.get("From")),
        "to": _decode_header_value(msg.get("To")),
        "subject": _decode_header_value(msg.get("Subject")),
        "date": _decode_header_value(msg.get("Date")),
        "body_plain": plain[: 10_000],
        "body_html": html[: 5_000] if html else "",
    }


def _email_signature() -> str:
    """Build sign-off block from config. Empty if no sender name set."""
    s = get_settings()
    name = s.email_sender_name
    if not name:
        return ""
    lines = ["Best regards,", name]
    if s.email_sender_company:
        lines.append(s.email_sender_company)
    if s.email_sender_contact:
        lines.append(s.email_sender_contact)
    return "\n".join(lines)


def _strip_placeholder_signature(body: str) -> str:
    """Remove common placeholder lines so we can append a real signature."""
    import re
    # Remove lines like [Your Name], [Your Position/Company], [Contact Information], [Company], etc.
    body = re.sub(r"\n\s*\[Your Name\].*", "", body, flags=re.I)
    body = re.sub(r"\n\s*\[Your Position/Company\].*", "", body, flags=re.I)
    body = re.sub(r"\n\s*\[Contact Information\].*", "", body, flags=re.I)
    body = re.sub(r"\n\s*\[Company\].*", "", body, flags=re.I)
    body = re.sub(r"\n\s*\[Name\].*", "", body, flags=re.I)
    return body.rstrip()


def _prepare_body(body: str) -> str:
    """Strip placeholder sign-off and append configured signature if set."""
    body = _strip_placeholder_signature(body)
    sig = _email_signature()
    if not sig:
        return body
    if body and not body.endswith("\n"):
        body += "\n\n"
    elif body:
        body = body.rstrip() + "\n\n"
    return body + sig


def _ensure_email_configured(need_imap: bool = False, need_send: bool = False) -> str | None:
    s = get_settings()
    if not s.email_enabled:
        return "Email is not configured. Set EMAIL_IMAP_* and EMAIL_SMTP_* (or SENDGRID_API_KEY) in .env."
    if need_imap and not (s.email_imap_host and s.email_imap_user and s.email_imap_password):
        return "IMAP is not configured. Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD."
    if need_send:
        has_smtp = s.email_smtp_host and s.email_smtp_user and s.email_smtp_password
        if not has_smtp and not s.sendgrid_api_key:
            return "Send is not configured. Set EMAIL_SMTP_* or SENDGRID_API_KEY."
    return None


# ---- Send (SMTP or SendGrid) ----

@tool
def send_email(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    """Send an email. Use for follow-ups, replies, or new messages. to/subject/body required; cc and bcc optional (comma-separated). Sign-off is added from config (EMAIL_SENDER_NAME, etc.); never use [Your Name] or similar placeholders."""
    err = _ensure_email_configured(need_send=True)
    if err:
        return err
    body = _prepare_body(body)
    s = get_settings()
    if s.sendgrid_api_key:
        return _send_via_sendgrid(to, subject, body, cc, bcc)
    return _send_via_smtp(to, subject, body, cc, bcc)


def _send_via_smtp(to: str, subject: str, body: str, cc: str, bcc: str) -> str:
    s = get_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = s.email_smtp_user
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body, "plain", "utf-8"))
    to_list = [a.strip() for a in to.split(",") if a.strip()]
    if cc:
        to_list += [a.strip() for a in cc.split(",") if a.strip()]
    try:
        with smtplib.SMTP(s.email_smtp_host, s.email_smtp_port) as smtp:
            smtp.starttls()
            smtp.login(s.email_smtp_user, s.email_smtp_password)
            smtp.sendmail(s.email_smtp_user, to_list, msg.as_string())
        return f"Email sent to {to}."
    except Exception as e:
        return f"Send failed: {e}"


def _send_via_sendgrid(to: str, subject: str, body: str, cc: str, bcc: str) -> str:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError:
        return "SendGrid is configured but the sendgrid package is not installed. Run: pip install sendgrid."
    s = get_settings()
    message = Mail(
        from_email=s.email_smtp_user or "noreply@example.com",
        to_emails=[a.strip() for a in to.split(",") if a.strip()],
        subject=subject,
        plain_text_content=body,
    )
    if cc:
        message.cc = [a.strip() for a in cc.split(",") if a.strip()]
    if bcc:
        message.bcc = [a.strip() for a in bcc.split(",") if a.strip()]
    try:
        client = SendGridAPIClient(s.sendgrid_api_key)
        client.send(message)
        return f"Email sent to {to} via SendGrid."
    except Exception as e:
        return f"SendGrid send failed: {e}"


# ---- Inbox (IMAP) ----

@tool
def list_inbox(max_emails: int = 20, folder: str = "INBOX") -> str:
    """List recent emails in the inbox (or folder). Returns from, to, subject, date, and uid for each. Use before get_email or summarize_inbox."""
    err = _ensure_email_configured(need_imap=True)
    if err:
        return err
    try:
        with _with_imap(folder) as conn:
            _, data = conn.search(None, "ALL")
            uids = data[0].split()
            if not uids:
                return f"No emails in {folder}."
            uids = uids[-max_emails:][::-1]
            lines = []
            for uid in uids:
                _, msg_data = conn.fetch(uid, "(RFC822.HEADER)")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1] if isinstance(msg_data[0][1], bytes) else msg_data[0][1].encode()
                msg = email.message_from_bytes(raw)
                subj = _decode_header_value(msg.get("Subject"))
                from_ = _decode_header_value(msg.get("From"))
                date = _decode_header_value(msg.get("Date"))
                lines.append(f"uid={uid.decode() if isinstance(uid, bytes) else uid} | from={from_[:50]} | date={date} | subject={subj[:60]}")
            return "\n".join(lines) if lines else f"No messages in {folder}."
    except Exception as e:
        return f"Inbox list failed: {e}"


@tool
def get_email(uid: str, folder: str = "INBOX") -> str:
    """Get full content of one email by its uid (from list_inbox). Returns from, to, subject, date, and body."""
    err = _ensure_email_configured(need_imap=True)
    if err:
        return err
    try:
        with _with_imap(folder) as conn:
            _, data = conn.fetch(uid.encode() if isinstance(uid, str) else uid, "(RFC822)")
            if not data or not data[0]:
                return f"No email with uid {uid}."
            raw = data[0][1] if isinstance(data[0][1], bytes) else data[0][1].encode()
            m = _parse_message(raw)
            body = m["body_plain"] or "(no text body)"
            return f"From: {m['from']}\nTo: {m['to']}\nSubject: {m['subject']}\nDate: {m['date']}\n\n{body}"
    except Exception as e:
        return f"Get email failed: {e}"


@tool
def summarize_inbox(max_emails: int = 15, folder: str = "INBOX") -> str:
    """Fetch recent emails and return a compact summary (from, subject, date) for the agent to summarize or prioritize. Use when the user asks 'what's in my inbox' or 'summarize my emails'."""
    err = _ensure_email_configured(need_imap=True)
    if err:
        return err
    try:
        with _with_imap(folder) as conn:
            _, data = conn.search(None, "ALL")
            uids = data[0].split()
            if not uids:
                return f"Inbox ({folder}) is empty."
            uids = uids[-max_emails:][::-1]
            summaries = []
            for uid in uids:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1] if isinstance(msg_data[0][1], bytes) else msg_data[0][1].encode()
                m = _parse_message(raw)
                body_preview = (m["body_plain"] or "")[:200].replace("\n", " ")
                summaries.append(
                    f"[uid={uid.decode() if isinstance(uid, bytes) else uid}] {m['from']} | {m['subject']} | {m['date']}\n  {body_preview}..."
                )
            return "\n\n".join(summaries) if summaries else f"No messages in {folder}."
    except Exception as e:
        return f"Summarize inbox failed: {e}"


@tool
def search_emails(query: str, folder: str = "INBOX", max_results: int = 20) -> str:
    """Search emails by IMAP criteria. query can be: 'FROM x@y.com', 'TO z@w.com', 'SUBJECT keyword', 'SINCE 01-Jan-2024', 'BEFORE 01-Feb-2024', or combined (e.g. 'FROM x SUBJECT y'). Returns list of uid, from, subject, date."""
    err = _ensure_email_configured(need_imap=True)
    if err:
        return err
    try:
        with _with_imap(folder) as conn:
            _, data = conn.search(None, query)
            uids = data[0].split()
            if not uids:
                return f"No emails matching: {query}."
            uids = uids[-max_results:][::-1]
            lines = []
            for uid in uids:
                _, msg_data = conn.fetch(uid, "(RFC822.HEADER)")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1] if isinstance(msg_data[0][1], bytes) else msg_data[0][1].encode()
                msg = email.message_from_bytes(raw)
                lines.append(
                    f"uid={uid.decode() if isinstance(uid, bytes) else uid} | {_decode_header_value(msg.get('From'))} | {_decode_header_value(msg.get('Subject'))} | {_decode_header_value(msg.get('Date'))}"
                )
            return "\n".join(lines) if lines else f"No matches for: {query}."
    except Exception as e:
        return f"Search failed: {e}. Use criteria like FROM x@y.com SUBJECT term SINCE 01-Jan-2024."


@tool
def create_draft(to: str, subject: str, body: str) -> str:
    """Create an email draft (saved to Drafts folder) for the user to review and send later. Use when the user wants to 'draft' or 'prepare' an email without sending. Sign-off is added from config; never use [Your Name] or similar placeholders."""
    err = _ensure_email_configured(need_imap=True)
    if err:
        return err
    body = _prepare_body(body)
    s = get_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = s.email_imap_user
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        with _with_imap("INBOX") as conn:
            # Append to Drafts (folder name may be "Drafts" or "[Gmail]/Drafts" etc.)
            date_str = imaplib.Time2Internaldate(time.time())
            try:
                conn.append("Drafts", "\\Draft", date_str, msg.as_string().encode("utf-8"))
            except conn.error:
                try:
                    conn.append("[Gmail]/Drafts", "\\Draft", date_str, msg.as_string().encode("utf-8"))
                except Exception:
                    return "Could not save draft (Drafts folder not found). Some providers use a different folder name."
        return f"Draft saved: to={to}, subject={subject}. User can open Drafts and send manually."
    except Exception as e:
        return f"Create draft failed: {e}"


# Export for agent
EMAIL_TOOLS = [
    send_email,
    list_inbox,
    get_email,
    summarize_inbox,
    search_emails,
    create_draft,
]
