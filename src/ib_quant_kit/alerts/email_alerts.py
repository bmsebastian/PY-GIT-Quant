
import smtplib, ssl, os
from email.mime.text import MIMEText

def send_email(subject: str, body: str):
    to_addr = os.getenv("ALERT_EMAIL_TO")
    server = os.getenv("SMTP_SERVER"); user = os.getenv("SMTP_USER"); pw = os.getenv("SMTP_PASS")
    if not (to_addr and server and user and pw):
        return False, "missing_email_env"
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject; msg["From"] = user; msg["To"] = to_addr
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(server, 465, context=ctx) as s:
            s.login(user, pw); s.sendmail(user, [to_addr], msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, str(e)
