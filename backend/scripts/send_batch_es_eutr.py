"""
/send-batch — Spanish EUTR organisations targeted news alert (3 days/week routine).

Picks ~100 Spanish orgs from EU Transparency Register matching today's headline clusters,
sends a Spanish-language outreach email tying that day's news to Brubru's value, with a
21-day no-repeat rotation tracked via pre_user_events (event_type='send_batch_es_eutr').

Every "Brubru" mention is bold + hyperlinked to https://brubru.beresol.eu.

Usage:
    python3.12 scripts/send_batch_es_eutr.py --preview         # show recipients + email body
    python3.12 scripts/send_batch_es_eutr.py --test            # send to hello@beresol.eu only
    python3.12 scripts/send_batch_es_eutr.py --send            # SMTP-level BCC to all 100
"""
import argparse
import logging
import os
import sys
from datetime import date, timedelta
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from services.email_service import EmailService  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

BRUBRU_URL = "https://brubru.beresol.eu"
BATCH_SIZE = 100
NO_REPEAT_DAYS = 21
EVENT_TYPE = "send_batch_es_eutr"

# Today's headlines as bullet items in Spanish
# Edit these per-day; the rest of the email is template
ISSUES_THIS_WEEK_SHORT = "MFF 2028-2034, DMA, AI Act, Mercosur, Better Regulation"
ISSUES_BULLETS = [
    "<strong>MFF 2028-2034 — voto del Parlamento Europeo el miércoles 29 de abril en Estrasburgo</strong>. La comisión BUDG ya adoptó el mandato de negociación el 16 de abril; coponentes Siegfried Mureşan (PPE, RO) y Carla Tavares (S&amp;D). Posición del PE: 1,27 % de la RNB de la UE (frente al 1,26 % de la Comisión), servicio de la deuda de NextGenerationEU fuera de los topes, mecanismo de protección frente a la inflación, defensa y competitividad como nuevas prioridades.",
    "<strong>Aplicación del DMA — la Comisión abre consulta pública sobre la interoperabilidad de Google Android con dispositivos de terceros</strong> (smartwatches, auriculares, dispositivos del hogar inteligente) bajo el artículo 6(7) DMA. Reglamento (UE) 2022/1925, CELEX 32022R1925. Tercera ofensiva de aplicación tras Meta WhatsApp y Google Search.",
    "<strong>EU-Mercosur — aplicación provisional del Acuerdo Comercial Interino desde el viernes 1 de mayo</strong> (CELEX 22026A00184). Cambia la realidad arancelaria para importadores agrarios, automoción, textil y cuero.",
    "<strong>Comunicación sobre Mejor Regulación y Aplicación adoptada hoy por el Colegio de Comisarios</strong>; declaración del EVP Valdis Dombrovskis (Economía y Productividad, Implementación y Simplificación) en el pleno del martes por la tarde. Por primera vez, simplificación + procedimientos de infracción del artículo 258 TFUE en una única estrategia.",
    "<strong>Ley de IA — tercera reunión del grupo de trabajo de signatarios del Código de Buenas Prácticas para IA de Propósito General</strong> (capítulo Seguridad y Protección). Mecanismo a través del cual los proveedores de IA de propósito general (OpenAI, Anthropic, Google DeepMind, Mistral, Meta, Microsoft) pueden demostrar el cumplimiento de los artículos 53-56 del Reglamento (UE) 2024/1689 antes de las normas armonizadas.",
]


def _select_recipients(db, batch_size: int = BATCH_SIZE) -> Tuple[List[dict], int, int]:
    """Pick top-N Spanish orgs across relevant clusters, excluding those contacted in last 21 days."""
    sql = text("""
        WITH eligible AS (
            SELECT t.id, t.name, t.contact_email, t.policy_cluster, t.calculated_cost,
                   COALESCE(MAX(p.created_at), '1970-01-01'::timestamptz) AS last_sent
            FROM transparency_register_orgs t
            LEFT JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type = :event_type
            WHERE (t.country ILIKE 'spain' OR t.country = 'ES' OR t.country ILIKE 'españa')
              AND t.contact_email IS NOT NULL
              AND t.contact_email != ''
              AND COALESCE(t.outreach_status, '') != 'bounced'
              AND t.policy_cluster IN ('trade','climate','energy','agriculture',
                                       'finance','research','digital','social')
            GROUP BY t.id, t.name, t.contact_email, t.policy_cluster, t.calculated_cost
        )
        SELECT id, name, contact_email, policy_cluster, calculated_cost, last_sent
        FROM eligible
        WHERE last_sent < (NOW() - INTERVAL ':days days')::timestamptz
        ORDER BY
            CASE policy_cluster
                WHEN 'trade' THEN 1
                WHEN 'agriculture' THEN 2
                WHEN 'climate' THEN 3
                WHEN 'energy' THEN 4
                WHEN 'finance' THEN 5
                WHEN 'research' THEN 6
                WHEN 'digital' THEN 7
                WHEN 'social' THEN 8
            END,
            calculated_cost DESC NULLS LAST,
            name
        LIMIT :limit
    """.replace(":days", str(NO_REPEAT_DAYS)))

    rows = db.execute(sql, {"event_type": EVENT_TYPE, "limit": batch_size}).fetchall()
    recipients = [
        {
            "id": str(r[0]),
            "name": r[1],
            "email": r[2].strip().lower(),
            "cluster": r[3],
            "cost": r[4],
            "last_sent": r[5],
        }
        for r in rows
    ]

    # Already-bounced (excluded above) + last-sent-recently counts for reporting
    excluded_recently = db.execute(
        text("""
            SELECT COUNT(DISTINCT LOWER(t.contact_email))
            FROM transparency_register_orgs t
            JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type = :event_type
             AND p.created_at >= (NOW() - INTERVAL ':days days')::timestamptz
            WHERE (t.country ILIKE 'spain' OR t.country = 'ES' OR t.country ILIKE 'españa')
              AND t.contact_email IS NOT NULL
        """.replace(":days", str(NO_REPEAT_DAYS))),
        {"event_type": EVENT_TYPE},
    ).scalar() or 0

    excluded_bounced = db.execute(
        text("""
            SELECT COUNT(*)
            FROM transparency_register_orgs
            WHERE (country ILIKE 'spain' OR country = 'ES' OR country ILIKE 'españa')
              AND contact_email IS NOT NULL
              AND outreach_status = 'bounced'
        """)
    ).scalar() or 0

    return recipients, excluded_recently, excluded_bounced


def _bold_link_brubru(text_str: str) -> str:
    """Replace every 'Brubru' with bold + linked HTML. Idempotent for <strong>Brubru</strong>."""
    linked = f'<a href="{BRUBRU_URL}" style="color: #0693e3; text-decoration: none; font-weight: 700;">Brubru</a>'
    # First, collapse pre-existing <strong>Brubru</strong> wrappers to bare Brubru
    text_str = text_str.replace("<strong>Brubru</strong>", "Brubru")
    # Then replace bare Brubru with the linked version (link's font-weight: 700 = bold)
    return text_str.replace("Brubru", linked)


def _build_email_html(today_iso: str) -> str:
    bullets_html = "\n".join(f"<li style=\"margin-bottom: 10px;\">{b}</li>" for b in ISSUES_BULLETS)
    body = f"""
    <div style="font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6; color: #1a1a1a; max-width: 640px;">
    <p>Buenos días,</p>

    <p>hemos visto vuestra organización en el Registro de Transparencia de la UE y creemos que podéis estar interesados en Brubru y en cómo os puede ayudar con estos asuntos europeos que suceden esta misma semana:</p>

    <ul style="padding-left: 20px;">
{bullets_html}
    </ul>

    <p>En Brubru podréis ver un Chat en qué podréis preguntar todo lo relacionado con estos asuntos. También podréis hacer un seguimiento detallado de la legislación europea que se está llevando a cabo, además de hacer enmiendas siguiendo los parámetros oficiales del Parlamento Europeo, o ver la predicción y el posicionamiento institucional por cada ley.</p>

    <p>En Brubru también podréis generar documentos oficiales de la UE (ej.: preguntas parlamentarias, resoluciones parlamentarias, síntesis legislativas); evaluar el cumplimiento con el derecho europeo de vuestra organización, producto, o servicio; y preparar vuestra candidatura a licitaciones europeas.</p>

    <p>Finalmente, también podéis integrar Brubru en vuestra organización a través de nuestra API.</p>

    <p style="margin-top: 24px;"><strong>¡Contacta con nosotros para una demo gratuita!</strong></p>

    <p>Muchas gracias por vuestra atención y buena semana.</p>

    <p>Atentamente,<br/>
    Equipo de Brubru</p>

    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;"/>
    <p style="font-size: 11px; color: #999;">
        Si no deseáis recibir más correos, respondedme con "BAJA" en el asunto.<br/>
        Brubru by Beresol BV · Brussels · {today_iso}
    </p>
    </div>
    """
    return _bold_link_brubru(body)


def _log_send(db, email: str, name: str) -> None:
    """Log a successful send to pre_user_events for 21-day rotation tracking."""
    db.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (gen_random_uuid(), gen_random_uuid()::text, :et, 'A',
                    jsonb_build_object('email', :email, 'org_name', :name, 'campaign', 'spain_eutr_2026_04_27'),
                    NOW())
        """),
        {"et": EVENT_TYPE, "email": email, "name": name},
    )


def _send_smtp_bcc_batch(recipients: List[dict], subject: str, html_body: str, db) -> Tuple[int, int]:
    """Send via SMTP-level BCC pattern (Sant Jordi proven, see memory/feedback_send_batch_use_bcc.md):
    - One MIMEText message envelope, To=hello@beresol.eu (visible)
    - Single SMTP connection reused for all RCPT TO calls
    - 0.5s delay between sends to avoid Gmail per-second cap
    - Each recipient sees only To=hello@beresol.eu (no cross-recipient leak)
    """
    import smtplib
    import time
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = (os.environ.get("SMTP_USER")
                 or os.environ.get("EMAIL_FROM")
                 or "hello@beresol.eu")
    smtp_pass = (os.environ.get("SMTP_PASSWORD")
                 or os.environ.get("SMTP_PASS")
                 or os.environ.get("EMAIL_PASSWORD"))
    if not smtp_pass:
        logger.error("[ERROR] No SMTP password env var found (tried SMTP_PASSWORD, SMTP_PASS, EMAIL_PASSWORD).")
        logger.error("        Set SMTP_PASSWORD in .env. Aborting send to avoid per-recipient connection rate-limit.")
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
                if i % 10 == 0:
                    logger.info(f"  [{i}/{len(recipients)}] sent so far")
            except Exception as e:  # noqa: BLE001
                logger.error(f"[ERROR] Failed to send to {r['email']}: {e}")
                failed_n += 1
            time.sleep(0.5)  # politeness + Gmail rate-limit avoidance
    db.commit()
    return sent_n, failed_n


def main() -> int:
    parser = argparse.ArgumentParser(description="Send batch to Spanish EUTR orgs (3 days/week)")
    parser.add_argument("--preview", action="store_true", help="Show recipients + email, do not send")
    parser.add_argument("--test", action="store_true", help="Send to hello@beresol.eu only")
    parser.add_argument("--send", action="store_true", help="Send to all selected recipients")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help=f"Number of recipients (default {BATCH_SIZE})")
    args = parser.parse_args()

    today_iso = date.today().isoformat()
    subject = f"Brubru para tus asuntos públicos europeos: trabaja fácilmente en {ISSUES_THIS_WEEK_SHORT}"
    html_body = _build_email_html(today_iso)

    db = SessionLocal()
    try:
        recipients, excl_recent, excl_bounced = _select_recipients(db, args.limit)

        from collections import Counter
        mix = Counter(r["cluster"] for r in recipients)
        print(f"\n[INFO] Today: {today_iso}")
        print(f"[INFO] Recipients eligible: {len(recipients)} (cluster mix: {dict(mix)})")
        print(f"[INFO] Excluded as bounced: {excl_bounced}")
        print(f"[INFO] Excluded by 21-day rotation: {excl_recent}")
        print(f"[INFO] Subject: {subject}")
        print()

        if args.preview:
            print("[PREVIEW] First 10 recipients:")
            for r in recipients[:10]:
                print(f"  [{r['cluster']:>11s}] {r['name'][:55]:<55s} | {r['email']}")
            print(f"  ... and {max(0, len(recipients) - 10)} more")
            print()
            print("[PREVIEW] HTML body (first 600 chars):")
            print(html_body[:600])
            return 0

        if args.test:
            print("[TEST] Sending to hello@beresol.eu only")
            ok = EmailService().send(to="hello@beresol.eu", subject=f"[TEST] {subject}", html_body=html_body)
            print("[OK] Test sent" if ok else "[ERROR] test send failed")
            return 0 if ok else 1

        if args.send:
            if len(recipients) == 0:
                print("[ERROR] No eligible recipients")
                return 1
            print(f"[SEND] Sending to {len(recipients)} recipients via SMTP-level BCC")
            sent_n, failed_n = _send_smtp_bcc_batch(recipients, subject, html_body, db)
            print(f"\n[OK] Sent: {sent_n}  Failed: {failed_n}")
            return 0 if failed_n == 0 else 1

        # Default: same as preview
        print("[INFO] Use --preview / --test / --send")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
