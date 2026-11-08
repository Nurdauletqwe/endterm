import os, json, smtplib, threading, urllib.request
from email.message import EmailMessage


def _brevo(to, subject, body, sender):
    payload = {"sender": {"email": sender}, "to": [{"email": to}], "subject": subject, "textContent": body}
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(payload).encode(), method="POST",
                                 headers={"api-key": os.environ["BREVO_API_KEY"], "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def _smtp(to, subject, body, sender):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg.set_content(body)
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
    server = smtplib.SMTP_SSL(host, port, timeout=15) if port == 465 else smtplib.SMTP(host, port, timeout=15)
    with server:
        if port != 465:
            server.starttls()
        if os.environ.get("SMTP_USER"):
            server.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        server.send_message(msg)


def send(to, subject, body):
    to = os.environ.get("MAIL_REDIRECT_TO") or to
    sender = os.environ.get("MAIL_FROM", "")
    if os.environ.get("BREVO_API_KEY") and sender:
        _brevo(to, subject, body, sender); return "brevo"
    if os.environ.get("SMTP_HOST") and sender:
        _smtp(to, subject, body, sender); return "smtp"
    print(f"[mail not configured] to={to} subject={subject!r}\n{body}")
    return "log"


def send_async(to, subject, body):
    def run():
        try:
            print("[mail] sent via", send(to, subject, body))
        except Exception as exc:                     
            print("[mail] FAILED:", exc)
    threading.Thread(target=run, daemon=True).start()
