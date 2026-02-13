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


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
