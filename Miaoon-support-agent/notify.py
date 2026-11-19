"""Handoff alerts: email (SMTP) and/or Slack webhook. Both optional. Stdlib only."""
import os, json, smtplib, threading, urllib.request
from email.message import EmailMessage


def _fmt(h, transcript):
    link = os.getenv("PUBLIC_URL", "").rstrip("/")
    lines = [f"New {h['kind'].upper()} handoff #{h['id']}", "",
             f"Contact: {h.get('contact') or 'not shared yet'}",
             f"Why: {h['reason']}", "", "Summary:", h["summary"], "", "Transcript:"]
    lines += [f"  {r}: {t}" for r, t in transcript]
    if link:
        lines += ["", f"Reply in the dashboard: {link}/admin"]
    return "\n".join(lines)


def _email(subject, body):
    host = os.getenv("SMTP_HOST")
    if not host:
        return
    m = EmailMessage()
    m["Subject"], m["From"] = subject, os.getenv("NOTIFY_FROM") or os.getenv("SMTP_USER", "agent@miaoon.in")
    m["To"] = os.getenv("NOTIFY_TO", "hello@miaoon.in")
    m.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as s:
        s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(m)


def _slack(body):
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return
    req = urllib.request.Request(url, json.dumps({"text": body}).encode(), {"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()


def send(subject, body):
    def run():
        for fn, arg in ((_email, (subject, body)), (_slack, (subject + "\n" + body,))):
            try:
                fn(*arg)
            except Exception as e:
                print("notify error:", e)
    threading.Thread(target=run, daemon=True).start()


def handoff(h, transcript):
    send(f"[Miaoon support] {h['kind']} handoff #{h['id']}", _fmt(h, transcript))


def contact_update(sid, contact):
    send("[Miaoon support] contact shared", f"A customer shared contact details: {contact}\nConversation: {sid}")
