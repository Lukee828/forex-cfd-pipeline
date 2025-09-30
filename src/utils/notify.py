import smtplib, ssl, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject: str, body_text: str, body_html: str | None = None):
    """
    Sends a plaintext (and optional HTML) email using SMTP creds from env vars:
      ALERT_TO, ALERT_FROM, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    """
    to      = os.getenv("ALERT_TO")
    sender  = os.getenv("ALERT_FROM")
    host    = os.getenv("SMTP_HOST")
    port    = int(os.getenv("SMTP_PORT", "587"))
    user    = os.getenv("SMTP_USER")
    psw     = os.getenv("SMTP_PASS")

    if not all([to, sender, host, user, psw]):
        print("WARN notify: missing SMTP envs; skipping email.")
        return

    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        msg = MIMEText(body_text, "plain", "utf-8")

    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port) as s:
        s.starttls(context=ctx)
        s.login(user, psw)
        s.sendmail(sender, [to], msg.as_string())
