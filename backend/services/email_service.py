"""
Email Service

Sends transactional and re-engagement emails via Gmail SMTP (Google Workspace).
Sender: hello@beresol.eu

No third-party dependencies - uses Python stdlib smtplib + email.mime.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Send emails via Gmail SMTP using Google Workspace App Password.

    Usage:
        service = EmailService()
        service.send(
            to="user@example.com",
            subject="Welcome back to Brubru",
            html_body="<h1>Hello!</h1><p>We missed you.</p>",
        )
    """

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_name = settings.SMTP_FROM_NAME

        if not self.user or not self.password:
            logger.warning("[EMAIL] SMTP credentials not configured - emails will be logged only")

    @property
    def is_configured(self) -> bool:
        return bool(self.user and self.password)

    def _from_address(self) -> str:
        return f"{self.from_name} <{self.user}>"

    def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send a single email.

        Args:
            to: Recipient email address
            subject: Email subject line
            html_body: HTML content
            text_body: Plain text fallback (auto-generated from subject if not provided)

        Returns:
            True if sent successfully
        """
        if not self.is_configured:
            logger.info(f"[EMAIL][DRY-RUN] To: {to} | Subject: {subject}")
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = self._from_address()
        msg["To"] = to
        msg["Subject"] = subject

        # Plain text fallback
        if not text_body:
            text_body = f"{subject}\n\nView this email in HTML for the full content."
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
                server.sendmail(self.user, to, msg.as_string())

            logger.info(f"[EMAIL] Sent to {to}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("[EMAIL] Authentication failed - check SMTP_PASSWORD (App Password)")
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.error(f"[EMAIL] Recipient refused: {to}")
            return False
        except Exception as e:
            logger.error(f"[EMAIL] Failed to send to {to}: {e}")
            return False

    def send_bulk(
        self,
        recipients: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> dict:
        """
        Send the same email to multiple recipients (one at a time, BCC-style).

        Args:
            recipients: List of email addresses
            subject: Email subject line
            html_body: HTML content
            text_body: Plain text fallback

        Returns:
            Dict with sent/failed counts and failed addresses
        """
        sent = 0
        failed = []

        for email in recipients:
            if self.send(to=email, subject=subject, html_body=html_body, text_body=text_body):
                sent += 1
            else:
                failed.append(email)

        logger.info(f"[EMAIL] Bulk send complete: {sent} sent, {len(failed)} failed")
        return {"sent": sent, "failed": len(failed), "failed_addresses": failed}


# --- Email Templates ---

def build_welcome_back_email(user_name: str, days_since_login: int) -> dict:
    """
    Build a re-engagement email for inactive users.

    Returns:
        Dict with 'subject' and 'html_body'
    """
    subject = f"{user_name}, we miss you at Brubru!"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
            <tr><td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" style="margin-bottom:12px;" />
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">Your AI-powered EU policy assistant</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">Hello {user_name},</h1>
                            <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 20px;">
                                It's been <strong>{days_since_login} days</strong> since your last visit to Brubru.
                                A lot has happened in EU policy — let us help you catch up.
                            </p>

                            <h2 style="color:#1e293b;font-size:17px;margin:24px 0 12px;">What you can do with Brubru:</h2>
                            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#0693e3;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Chat with an EU policy expert</strong> — ask anything about regulations, directives, or institutional processes
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#9b51e0;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Track EU legislation</strong> — monitor legislative files, RSS feeds from 15+ EU sources, and committee work
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:#059669;font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        <strong>Draft amendments</strong> — use the Amendator to create professional legislative amendments with AI assistance
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="https://brubru.beresol.eu/main"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        Open Brubru
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                You received this email because you have a Brubru account.
                                If you no longer wish to receive these emails, simply reply to this message.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f1f5f9;padding:20px 40px;text-align:center;">
                            <p style="color:#94a3b8;font-size:12px;margin:0;">
                                Beresol &middot; EU Public Affairs &middot;
                                <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
    </body>
    </html>
    """

    return {"subject": subject, "html_body": html_body}


def build_first_time_welcome_email(user_name: str) -> dict:
    """
    Build a welcome email for users who registered but never logged in.

    Returns:
        Dict with 'subject' and 'html_body'
    """
    subject = f"Welcome to Brubru, {user_name}! Here's how to get started"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
            <tr><td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" style="margin-bottom:12px;" />
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">Your AI-powered EU policy assistant</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">Welcome, {user_name}!</h1>
                            <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 20px;">
                                Thank you for signing up for Brubru. You now have access to an AI assistant
                                built specifically for EU policy professionals.
                            </p>

                            <h2 style="color:#1e293b;font-size:17px;margin:24px 0 12px;">3 things to try first:</h2>

                            <table cellpadding="0" cellspacing="0" style="width:100%;margin-bottom:24px;">
                                <tr>
                                    <td style="padding:12px;background:#f0f9ff;border-radius:8px;margin-bottom:8px;">
                                        <strong style="color:#0693e3;">1. Ask Brubru a question</strong>
                                        <p style="color:#475569;font-size:14px;margin:4px 0 0;">
                                            Try: "What is the current status of the AI Act implementation?"
                                        </p>
                                    </td>
                                </tr>
                                <tr><td style="height:8px;"></td></tr>
                                <tr>
                                    <td style="padding:12px;background:#faf5ff;border-radius:8px;">
                                        <strong style="color:#9b51e0;">2. Explore My EU Bubble</strong>
                                        <p style="color:#475569;font-size:14px;margin:4px 0 0;">
                                            Browse RSS feeds from 15+ EU institutions, track legislative files, and stay up to date.
                                        </p>
                                    </td>
                                </tr>
                                <tr><td style="height:8px;"></td></tr>
                                <tr>
                                    <td style="padding:12px;background:#ecfdf5;border-radius:8px;">
                                        <strong style="color:#059669;">3. Draft an amendment</strong>
                                        <p style="color:#475569;font-size:14px;margin:4px 0 0;">
                                            Load any EU legislative text and use the Amendator to create professional amendments.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="https://brubru.beresol.eu/main"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        Start using Brubru
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                You received this email because you signed up for Brubru.
                                If you no longer wish to receive these emails, simply reply to this message.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f1f5f9;padding:20px 40px;text-align:center;">
                            <p style="color:#94a3b8;font-size:12px;margin:0;">
                                Beresol &middot; EU Public Affairs &middot;
                                <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
    </body>
    </html>
    """

    return {"subject": subject, "html_body": html_body}


# Global singleton
_email_service: Optional[EmailService] = None


# ---------------------------------------------------------------------------
# Password reset emails (migration 211).
#
# Localised into Brubru's six languages off users.language, defaulting to
# English when the column is null or holds something unexpected.
# ---------------------------------------------------------------------------

SUPPORTED_EMAIL_LANGS = ("en", "es", "ca", "fr", "it", "nl")

_RESET_STRINGS = {
    "en": {
        "subject": "Reset your Brubru password",
        "greeting": "Hello {name},",
        "intro": "Someone asked to reset the password on your Brubru account.",
        "cta": "Choose a new password",
        "expiry": "This link expires in one hour and can be used once.",
        "ignore": "If this was not you, you can ignore this email. Your password will not change.",
        "fallback": "If the button does not work, paste this link into your browser:",
    },
    "es": {
        "subject": "Restablece tu contraseña de Brubru",
        "greeting": "Hola {name}:",
        "intro": "Alguien ha solicitado restablecer la contraseña de tu cuenta de Brubru.",
        "cta": "Elegir una contraseña nueva",
        "expiry": "Este enlace caduca en una hora y solo se puede usar una vez.",
        "ignore": "Si no has sido tú, puedes ignorar este correo. Tu contraseña no cambiará.",
        "fallback": "Si el botón no funciona, pega este enlace en tu navegador:",
    },
    "ca": {
        "subject": "Restableix la teva contrasenya de Brubru",
        "greeting": "Hola {name},",
        "intro": "Algú ha demanat restablir la contrasenya del teu compte de Brubru.",
        "cta": "Tria una contrasenya nova",
        "expiry": "Aquest enllaç caduca d'aquí a una hora i només es pot fer servir un cop.",
        "ignore": "Si no has estat tu, pots ignorar aquest correu. La teva contrasenya no canviarà.",
        "fallback": "Si el botó no funciona, enganxa aquest enllaç al navegador:",
    },
    "fr": {
        "subject": "Réinitialiser votre mot de passe Brubru",
        "greeting": "Bonjour {name},",
        "intro": "Quelqu'un a demandé la réinitialisation du mot de passe de votre compte Brubru.",
        "cta": "Choisir un nouveau mot de passe",
        "expiry": "Ce lien expire dans une heure et ne peut servir qu'une seule fois.",
        "ignore": "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message. Votre mot de passe restera inchangé.",
        "fallback": "Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :",
    },
    "it": {
        "subject": "Reimposta la tua password Brubru",
        "greeting": "Ciao {name},",
        "intro": "Qualcuno ha chiesto di reimpostare la password del tuo account Brubru.",
        "cta": "Scegli una nuova password",
        "expiry": "Questo link scade tra un'ora e può essere usato una sola volta.",
        "ignore": "Se non sei stato tu, puoi ignorare questa email. La tua password non cambierà.",
        "fallback": "Se il pulsante non funziona, incolla questo link nel browser:",
    },
    "nl": {
        "subject": "Stel je Brubru-wachtwoord opnieuw in",
        "greeting": "Hallo {name},",
        "intro": "Iemand heeft gevraagd om het wachtwoord van je Brubru-account opnieuw in te stellen.",
        "cta": "Kies een nieuw wachtwoord",
        "expiry": "Deze link verloopt over een uur en kan één keer worden gebruikt.",
        "ignore": "Heb je dit niet aangevraagd? Dan kun je deze e-mail negeren. Je wachtwoord verandert niet.",
        "fallback": "Werkt de knop niet? Plak deze link dan in je browser:",
    },
}

_OAUTH_ONLY_STRINGS = {
    "en": {
        "subject": "Signing in to Brubru",
        "greeting": "Hello {name},",
        "intro": "You asked to reset your Brubru password. Your account does not have one: it signs in with {provider}.",
        "action": "Go to the Brubru login page and use the {provider} button.",
        "cta": "Go to login",
        "ignore": "If this was not you, nothing has changed on your account.",
    },
    "es": {
        "subject": "Cómo entrar en Brubru",
        "greeting": "Hola {name}:",
        "intro": "Has solicitado restablecer tu contraseña de Brubru. Tu cuenta no tiene: entra con {provider}.",
        "action": "Ve a la página de acceso de Brubru y usa el botón de {provider}.",
        "cta": "Ir al acceso",
        "ignore": "Si no has sido tú, no ha cambiado nada en tu cuenta.",
    },
    "ca": {
        "subject": "Com entrar a Brubru",
        "greeting": "Hola {name},",
        "intro": "Has demanat restablir la contrasenya de Brubru. El teu compte no en té: hi entres amb {provider}.",
        "action": "Ves a la pàgina d'accés de Brubru i fes servir el botó de {provider}.",
        "cta": "Ves a l'accés",
        "ignore": "Si no has estat tu, no ha canviat res al teu compte.",
    },
    "fr": {
        "subject": "Se connecter à Brubru",
        "greeting": "Bonjour {name},",
        "intro": "Vous avez demandé à réinitialiser votre mot de passe Brubru. Votre compte n'en a pas : il se connecte avec {provider}.",
        "action": "Rendez-vous sur la page de connexion Brubru et utilisez le bouton {provider}.",
        "cta": "Aller à la connexion",
        "ignore": "Si vous n'êtes pas à l'origine de cette demande, rien n'a changé sur votre compte.",
    },
    "it": {
        "subject": "Accedere a Brubru",
        "greeting": "Ciao {name},",
        "intro": "Hai chiesto di reimpostare la password di Brubru. Il tuo account non ne ha una: accede con {provider}.",
        "action": "Vai alla pagina di accesso di Brubru e usa il pulsante {provider}.",
        "cta": "Vai all'accesso",
        "ignore": "Se non sei stato tu, sul tuo account non è cambiato nulla.",
    },
    "nl": {
        "subject": "Inloggen bij Brubru",
        "greeting": "Hallo {name},",
        "intro": "Je hebt gevraagd om je Brubru-wachtwoord opnieuw in te stellen. Je account heeft er geen: je logt in met {provider}.",
        "action": "Ga naar de inlogpagina van Brubru en gebruik de {provider}-knop.",
        "cta": "Naar inloggen",
        "ignore": "Heb je dit niet aangevraagd? Dan is er niets aan je account veranderd.",
    },
}

_PROVIDER_LABELS = {"google": "Google", "linkedin": "LinkedIn", "eu_login": "EU Login"}


def _email_lang(user) -> str:
    """Pick the user's email language, falling back to English."""
    lang = (getattr(user, "language", None) or "en").lower()[:2]
    return lang if lang in SUPPORTED_EMAIL_LANGS else "en"


def _email_name(user) -> str:
    """Best available name for a greeting, without ever printing 'None'."""
    for attr in ("preferred_name", "first_name", "full_name"):
        value = (getattr(user, attr, None) or "").strip()
        if value:
            return value.split()[0] if attr == "full_name" else value
    return (user.email or "").split("@")[0] or "there"


def _auth_email_shell(body_html: str) -> str:
    """Shared transactional wrapper, matching the other Brubru emails."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
            <tr><td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" />
                        </td>
                    </tr>
                    <tr><td style="padding:40px;">{body_html}</td></tr>
                    <tr>
                        <td style="padding:24px 40px;background-color:#f1f5f9;text-align:center;">
                            <p style="color:#64748b;font-size:12px;margin:0;">Brubru by Beresol &middot; hello@beresol.eu</p>
                        </td>
                    </tr>
                </table>
            </td></tr>
        </table>
    </body>
    </html>
    """


def build_password_reset_email(user, reset_url: str) -> dict:
    """Build the reset-link email. Returns dict with 'subject' and 'html_body'."""
    s = _RESET_STRINGS[_email_lang(user)]
    name = _email_name(user)

    body = f"""
        <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">{s['greeting'].format(name=name)}</h1>
        <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 24px;">{s['intro']}</p>
        <p style="margin:0 0 24px;">
            <a href="{reset_url}" style="display:inline-block;background:#003399;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:8px;font-size:16px;font-weight:600;">{s['cta']}</a>
        </p>
        <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 8px;">{s['expiry']}</p>
        <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 24px;">{s['ignore']}</p>
        <p style="color:#94a3b8;font-size:12px;line-height:1.6;margin:0;">{s['fallback']}<br>
            <span style="color:#64748b;word-break:break-all;">{reset_url}</span>
        </p>
    """
    return {"subject": s["subject"], "html_body": _auth_email_shell(body)}


def build_oauth_only_reset_email(user, provider: str) -> dict:
    """Reset was requested for an account that has no password, only OAuth."""
    s = _OAUTH_ONLY_STRINGS[_email_lang(user)]
    name = _email_name(user)
    label = _PROVIDER_LABELS.get((provider or "").lower(), (provider or "OAuth").title())
    login_url = "https://brubru.beresol.eu/login"

    body = f"""
        <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">{s['greeting'].format(name=name)}</h1>
        <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 16px;">{s['intro'].format(provider=label)}</p>
        <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 24px;">{s['action'].format(provider=label)}</p>
        <p style="margin:0 0 24px;">
            <a href="{login_url}" style="display:inline-block;background:#003399;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:8px;font-size:16px;font-weight:600;">{s['cta']}</a>
        </p>
        <p style="color:#475569;font-size:14px;line-height:1.6;margin:0;">{s['ignore']}</p>
    """
    return {"subject": s["subject"], "html_body": _auth_email_shell(body)}


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
