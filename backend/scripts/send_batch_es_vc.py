"""
/send-batch — Spanish VC funds outreach (one-off campaign).

Reads `data/emails/vc_spain_2026.csv`, sends a Spanish-language outreach email
tying May 2026 EU files (Cloud and AI Development Act, 28th Regime, AI Act GPAI,
FP10, Mercosur ITA, AccelerateEU, CBAM Phase 1) to Brubru's value for VC funds
managing portfolio companies. Spec lives in `memory/scheduled_content_drops.md`
under "Spanish VC funds outreach batch".

21-day no-repeat rotation, `event_type='send_batch_es_vc'` (separate pool from
`send_batch_es_eutr`).

Usage:
    python3.12 scripts/send_batch_es_vc.py --preview      # show recipients + email
    python3.12 scripts/send_batch_es_vc.py --test         # send to hello@beresol.eu only
    python3.12 scripts/send_batch_es_vc.py --send         # SMTP-level BCC to 18 funds
"""
import argparse
import csv
import logging
import os
import sys
from datetime import date
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env into os.environ before importing services that might need SMTP_PASSWORD.
# The raw smtplib path in --send uses os.environ.get directly; without this, SMTP_PASSWORD
# stays unset even though .env has it. EmailService (used by --test) auto-loads internally.
try:
    from dotenv import load_dotenv  # type: ignore
    _env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from services.email_service import EmailService  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

BRUBRU_URL = "https://brubru.beresol.eu"
EVENT_TYPE = "send_batch_es_vc"
NO_REPEAT_DAYS = 21
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(PROJECT_ROOT, "data", "emails", "vc_spain_2026.csv")

# Funds to skip (no general inbox; route differently per drop entry)
SKIP_FUNDS = {"Antler", "Indra Ventures"}

SUBJECT = ("Brubru para fondos VC españoles: monitoriza la regulación europea "
           "de tu cartera (AI Act, 28th Regime, Cloud and AI Development Act, FP10)")


def _load_recipients(csv_path: str) -> List[dict]:
    """Read CSV, filter out funds without a general email + Antler/Indra + bouncers."""
    recipients = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            email = (row.get("contact_email") or "").strip()
            verified = (row.get("email_verified") or "").strip().lower()
            if not name or not email:
                continue
            if name in SKIP_FUNDS:
                continue
            # Skip rows where the "email" cell is actually a directive (parens)
            if email.startswith("(") or "apply form" in email.lower():
                continue
            # Skip rows that bounced on a previous send (CSV column updated post-bounce-sweep)
            if verified == "bounced":
                continue
            recipients.append({
                "name": name,
                "email": email.lower(),
                "city": (row.get("city") or "").strip(),
                "verified": verified,
                "stage_focus": (row.get("stage_focus") or "").strip(),
                "sector_focus": (row.get("sector_focus") or "").strip(),
            })
    return recipients


def _filter_by_rotation(db, recipients: List[dict]) -> Tuple[List[dict], int]:
    """Exclude funds emailed within the last NO_REPEAT_DAYS days."""
    if not recipients:
        return [], 0
    emails_lower = [r["email"] for r in recipients]
    sent_recently = db.execute(
        text("""
            SELECT DISTINCT LOWER(event_metadata->>'email') AS email
            FROM pre_user_events
            WHERE event_type = :et
              AND created_at >= (NOW() - INTERVAL ':days days')::timestamptz
              AND LOWER(event_metadata->>'email') = ANY(:emails)
        """.replace(":days", str(NO_REPEAT_DAYS))),
        {"et": EVENT_TYPE, "emails": emails_lower},
    ).fetchall()
    blocked = {row[0] for row in sent_recently}
    eligible = [r for r in recipients if r["email"] not in blocked]
    return eligible, len(blocked)


def _bold_link_brubru(html_str: str) -> str:
    linked = (f'<a href="{BRUBRU_URL}" style="color: #0693e3; text-decoration: none; '
              f'font-weight: 700;">Brubru</a>')
    html_str = html_str.replace("<strong>Brubru</strong>", "Brubru")
    return html_str.replace("Brubru", linked)


def _build_email_html(today_iso: str) -> str:
    body = f"""
    <div style="font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6; color: #1a1a1a; max-width: 640px;">
    <p>Buenos d&iacute;as,</p>

    <p>me llamo V&iacute;ctor Sol&eacute; y he creado Brubru, un agente de IA que ayuda en los asuntos p&uacute;blicos europeos con una API especializada muy potente. Os escribo porque vuestro fondo invierte en startups que cada vez m&aacute;s necesitan navegar el marco regulatorio europeo, y porque la mayor&iacute;a de las herramientas existentes no os lo cuentan en espa&ntilde;ol.</p>

    <p>Brubru es un asistente de IA + plataforma de inteligencia legislativa europea dise&ntilde;ado para profesionales de asuntos p&uacute;blicos. Hoy tambi&eacute;n lo usan equipos de inversi&oacute;n, porque vuestro problema operativo se parece al suyo: monitorizar m&aacute;s de 200 &aacute;reas de pol&iacute;tica p&uacute;blica europea, en 6 idiomas (incluido el espa&ntilde;ol), conectar las decisiones de Bruselas con vuestras carteras (como, por ejemplo, de IA, fintech, healthtech, climate-tech, insurtech, deeptech y construcci&oacute;n).</p>

    <p>Cinco cosas que est&aacute;n pasando ahora mismo, todas relevantes para una cartera VC espa&ntilde;ola:</p>

    <ul style="padding-left: 20px;">
      <li style="margin-bottom: 10px;"><strong>Cloud and AI Development Act</strong>: el Colegio de Comisarios lo adopta el mi&eacute;rcoles 27 de mayo de 2026 (parte del Tech Sovereignty Package, junto con Chips Act 2 y la Estrategia de Open Source). Va a redefinir el acceso a capacidad de c&aacute;lculo en la UE para vuestras startups de IA.</li>
      <li style="margin-bottom: 10px;"><strong>28th Regime / EU Inc</strong>: nuevo reglamento sobre el r&eacute;gimen corporativo paneuropeo del 28&ordm; r&eacute;gimen (nueva persona jur&iacute;dica europea para startups y scaleups). Permite a una startup constituirse bajo una sola legislaci&oacute;n corporativa v&aacute;lida en los 27 Estados miembros. Material directo para vuestras pre-seed/seed que aspiran a escala europea desde el d&iacute;a uno.</li>
      <li style="margin-bottom: 10px;"><strong>AI Act + Code of Practice for GPAI</strong>: el reloj de cumplimiento ya corre para los modelos fundacionales. Si alguna de vuestras participadas entrena o despliega un GPAI, los Art&iacute;culos 53-56 + el considerando 142 sobre sostenibilidad ambiental ya marcan algunas obligaciones. Brubru tiene una gu&iacute;a dedicada a la compatibilidad IA-sostenibilidad con 9 instrumentos UE.</li>
      <li style="margin-bottom: 10px;"><strong>FP10 + European Competitiveness Fund (175.000 millones de euros, 2028-2034)</strong>: el sucesor de Horizon Europe se est&aacute; dise&ntilde;ando ahora dentro del MFF 2028-2034. Para vuestras participadas en climate-tech, deeptech y digital, FP10 ser&aacute; la pipeline de financiaci&oacute;n blended con vuestras rondas Serie A/B.</li>
      <li style="margin-bottom: 10px;"><strong>Mercosur ITA (aplicaci&oacute;n provisional desde el viernes 1 de mayo de 2026), AccelerateEU (energ&iacute;a asequible, adoptado el 22 de abril) y CBAM Phase 1</strong>: nuevas oportunidades + nuevas obligaciones para portfolio cos con producci&oacute;n europea o cadenas de valor con LatAm.</li>
    </ul>

    <p>Brubru tiene 216 gu&iacute;as de pol&iacute;tica UE, 7.000+ disparadores de keywords en 6 idiomas, una API REST muy potente, con m&aacute;s de 80 endpoints enlazados al ecosistema digital institucional de la Uni&oacute;n, con adem&aacute;s un servidor MCP que se integra con LLMs (Claude/GPT/Mistral), y un corpus de 28.513 actos legislativos de la UE.</p>

    <p>Ofrecemos una prueba gratuita de 14 d&iacute;as sin tarjeta. Si os interesa una demo dirigida a vuestra tesis de inversi&oacute;n y a 3-4 portfolio cos representativas, contestad este correo y os la coordinamos esta semana.</p>

    <p>Saludos cordiales,<br/>
    V&iacute;ctor Sol&eacute;<br/>
    Beresol &mdash; Brubru<br/>
    hello@beresol.eu<br/>
    <a href="{BRUBRU_URL}" style="color: #0693e3;">brubru.beresol.eu</a></p>

    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;"/>
    <p style="font-size: 11px; color: #999;">
        Si no dese&aacute;is recibir m&aacute;s correos, respondedme con "BAJA" en el asunto.<br/>
        Brubru by Beresol BV &middot; {today_iso}
    </p>
    </div>
    """
    return _bold_link_brubru(body)


def _log_send(db, email: str, name: str) -> None:
    db.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (gen_random_uuid(), gen_random_uuid()::text, :et, 'A',
                    jsonb_build_object('email', :email, 'org_name', :name, 'campaign', 'spain_vc_2026_05_04'),
                    NOW())
        """),
        {"et": EVENT_TYPE, "email": email, "name": name},
    )


def _send_smtp_bcc_batch(recipients: List[dict], subject: str, html_body: str, db) -> Tuple[int, int]:
    import smtplib
    import time
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = (os.environ.get("SMTP_USER") or os.environ.get("EMAIL_FROM") or "hello@beresol.eu")
    smtp_pass = (os.environ.get("SMTP_PASSWORD")
                 or os.environ.get("SMTP_PASS")
                 or os.environ.get("EMAIL_PASSWORD"))
    if not smtp_pass:
        logger.error("[ERROR] No SMTP password env var (tried SMTP_PASSWORD, SMTP_PASS, EMAIL_PASSWORD).")
        logger.error("        Set SMTP_PASSWORD in .env. Aborting.")
        return 0, len(recipients)

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = "hello@beresol.eu"

    sent_n, failed_n = 0, 0
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        for i, r in enumerate(recipients, 1):
            try:
                server.sendmail(smtp_user, [r["email"]], msg.as_string())
                _log_send(db, r["email"], r["name"])
                sent_n += 1
                if i % 5 == 0:
                    logger.info(f"  [{i}/{len(recipients)}] sent so far")
            except Exception as e:  # noqa: BLE001
                logger.error(f"[ERROR] Failed to send to {r['email']}: {e}")
                failed_n += 1
            time.sleep(0.5)
    db.commit()
    return sent_n, failed_n


def main() -> int:
    parser = argparse.ArgumentParser(description="Send batch to Spanish VC funds (one-off, May 2026)")
    parser.add_argument("--preview", action="store_true", help="Show recipients + email, do not send")
    parser.add_argument("--test", action="store_true", help="Send to hello@beresol.eu only")
    parser.add_argument("--send", action="store_true", help="SMTP-level BCC to all eligible funds")
    parser.add_argument("--csv", default=CSV_PATH, help=f"CSV path (default: {CSV_PATH})")
    args = parser.parse_args()

    today_iso = date.today().isoformat()
    html_body = _build_email_html(today_iso)

    if not os.path.isfile(args.csv):
        print(f"[ERROR] CSV not found at {args.csv}")
        return 1

    db = SessionLocal()
    try:
        all_recipients = _load_recipients(args.csv)
        eligible, blocked_recently = _filter_by_rotation(db, all_recipients)

        print(f"\n[INFO] Today: {today_iso}")
        print(f"[INFO] CSV: {args.csv}")
        print(f"[INFO] Loaded from CSV (after Antler/Indra skip): {len(all_recipients)}")
        print(f"[INFO] Blocked by {NO_REPEAT_DAYS}-day rotation: {blocked_recently}")
        print(f"[INFO] Eligible to send: {len(eligible)}")
        print(f"[INFO] Subject: {SUBJECT}")
        print()

        if args.preview:
            print("[PREVIEW] Eligible recipients:")
            for r in eligible:
                v = "✓" if r["verified"] == "verified" else "~"
                print(f"  [{v}] {r['name'][:32]:<32s} | {r['email']:<34s} | {r['city'][:30]}")
            print()
            print("[PREVIEW] HTML body (first 800 chars):")
            print(html_body[:800])
            return 0

        if args.test:
            print("[TEST] Sending to hello@beresol.eu only")
            ok = EmailService().send(
                to="hello@beresol.eu",
                subject=f"[TEST] {SUBJECT}",
                html_body=html_body,
            )
            print("[OK] Test sent" if ok else "[ERROR] test send failed")
            return 0 if ok else 1

        if args.send:
            if not eligible:
                print("[ERROR] No eligible recipients")
                return 1
            print(f"[SEND] Sending to {len(eligible)} VC funds via SMTP-level BCC")
            sent_n, failed_n = _send_smtp_bcc_batch(eligible, SUBJECT, html_body, db)
            print(f"\n[OK] Sent: {sent_n}  Failed: {failed_n}")
            return 0 if failed_n == 0 else 1

        print("[INFO] Use --preview / --test / --send")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
