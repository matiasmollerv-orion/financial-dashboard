# ============================================================
# EMAIL SENDER — Gmail SMTP
#
# Envía emails HTML/text via Gmail con App Password.
# Requiere variables de entorno:
#   GMAIL_USER          → tu gmail (ej. matiasmollerv@gmail.com)
#   GMAIL_APP_PASSWORD  → App Password de 16 caracteres
#   RECIPIENT_EMAIL     → destino (puede ser el mismo)
#
# Cómo generar App Password:
#   1. Google Account → Security → 2-Step Verification
#   2. App Passwords → Generate
#   3. Copy 16-char password (sin espacios)
#
# Uso:
#   from intelligence.email_sender import send_email
#   send_email("Asunto", html_body, text_body)
# ============================================================

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


def _get_creds() -> tuple[str, str, str]:
    """Lee credenciales desde env. Retorna (user, password, recipient)."""
    user = os.getenv("GMAIL_USER", "").strip()
    pwd  = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
    to   = os.getenv("RECIPIENT_EMAIL", user).strip()

    if not user or not pwd:
        raise RuntimeError(
            "Falta GMAIL_USER y/o GMAIL_APP_PASSWORD en .env. "
            "Ver intelligence/email_sender.py docstring."
        )
    return user, pwd, to


def send_email(
    subject: str,
    html_body: str,
    text_body: str = "",
    recipient: str | None = None,
    sender_name: str = "Financial Dashboard",
    dry_run: bool = False,
) -> bool:
    """
    Envía email vía Gmail SMTP. Retorna True si OK.
    """
    user, pwd, default_to = _get_creds()
    to = recipient or default_to

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((sender_name, user))
    msg["To"]      = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if dry_run:
        print(f"📧 [DRY RUN] To: {to}")
        print(f"   Subject: {subject}")
        print(f"   HTML len: {len(html_body)} chars")
        return True

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(user, pwd)
            server.sendmail(user, [to], msg.as_string())
        print(f"✅ Email enviado a {to}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Auth error: revisa GMAIL_APP_PASSWORD. {e}")
        return False
    except Exception as e:
        print(f"❌ Error SMTP: {e}")
        return False


# ── Self-test ────────────────────────────────────────────────
def test_email():
    """Envía un email de prueba simple."""
    html = """
    <html><body style="font-family: Arial, sans-serif; padding: 20px;">
      <h2 style="color: #4e79a7;">✅ Test Email — Financial Dashboard</h2>
      <p>Si lees esto, el setup de Gmail SMTP funciona correctamente.</p>
      <p style="color: #888; font-size: 12px;">Enviado desde intelligence/email_sender.py</p>
    </body></html>
    """
    return send_email(
        subject="✅ Test — Financial Dashboard email funcionando",
        html_body=html,
        text_body="Test email funcionando.",
    )


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from dotenv import load_dotenv
    load_dotenv()
    test_email()
