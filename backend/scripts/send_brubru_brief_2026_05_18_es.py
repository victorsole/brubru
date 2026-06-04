"""
Brubru Brief — Spanish edition: lunes 18 de mayo de 2026 (semana de pleno en Estrasburgo).

Target audience: Spanish-speaking subscribers + Spanish (country='SPAIN') EUTR orgs.

BLOCKER (18 May 2026): Spain has 1033 EUTR orgs, 206 with contact_email, but
ZERO with email_verified=true. Per memory/feedback_eutr_email_verification_required.md
(11 May 2026), sends to unverified addresses caused a 50%+ bounce wave. Live send to
EUTR-SPAIN is therefore blocked today; --test still works and goes to hello@beresol.eu.

Usage:
    python3.12 scripts/send_brubru_brief_2026_05_18_es.py --test     # to hello@beresol.eu
    python3.12 scripts/send_brubru_brief_2026_05_18_es.py --preview  # show ES recipient pool (expect 0)
    python3.12 scripts/send_brubru_brief_2026_05_18_es.py --send-eutr-es  # LIVE (will abort if pool=0)
"""
import argparse
import os
import smtplib
import sys
import time
import uuid as _uuid
from datetime import datetime as _dt
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]
_env_path = _project_root / ".env"
load_dotenv(_env_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal
from services.email_service import EmailService


SUBJECT = "Brubru Brief: Lo que nadie más te cuenta sobre la Burbuja UE - lunes 18 de mayo de 2026"
BRUBRU_CHAT = "https://brubru.beresol.eu/main"


HEADLINES = [
    {
        "title": "La UE y China formalizan un ajuste de la lista de concesiones en la OMC en el Diario Oficial de hoy",
        "source": "Diario Oficial de la Unión Europea, serie L, lunes 18 de mayo de 2026",
        "snippet": (
            "Un intercambio de cartas entre la Unión Europea y la República Popular China, en virtud "
            "del Artículo XXVIII del Acuerdo General sobre Aranceles Aduaneros y Comercio de 1994, se "
            "publicó hoy en el Diario Oficial. El Artículo XXVIII es el procedimiento de la OMC para "
            "renegociar compromisos arancelarios previamente consolidados. El ajuste bilateral se "
            "enmarca en la estrategia más amplia de seguridad económica de la UE respecto a China. La "
            "prensa generalista resumirá el relato político, no la mecánica jurídica."
        ),
        "ask": "¿Qué cambia el nuevo intercambio de cartas UE-China bajo el Artículo XXVIII del GATT para los importadores y exportadores europeos?",
        "feature_label": "Seguimiento legislativo",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "La derogación ePrivacy expiró el 3 de abril, el pleno de Estrasburgo desde mañana es la ventana de adopción más plausible",
        "source": "Informe en proyecto de la comisión LIBE del PE, lunes 18 de mayo",
        "snippet": (
            "La derogación temporal que permite a las plataformas de mensajería escanear "
            "voluntariamente material de abuso sexual infantil expiró el 3 de abril de 2026. El "
            "informe en proyecto de LIBE sobre la prórroga reapareció hoy en el portal de la comisión, "
            "coincidiendo con la apertura del pleno de Estrasburgo. Con el expediente en estado "
            "'cercano a la adopción' y seis semanas de limbo jurídico a sus espaldas, la ventana de "
            "martes a viernes es la opción de adopción más creíble. El Reglamento CSAM más amplio "
            "sigue siendo un expediente separado y controvertido."
        ),
        "ask": "¿Por qué lleva la derogación voluntaria de escaneo de CSAM en limbo jurídico desde el 3 de abril de 2026?",
        "feature_label": "Seguimiento legislativo",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#9b51e0",
    },
    {
        "title": "¿Quién reemplazará a Laura Codruta Kovesi al frente de la EPPO? LIBE mantiene en marcha el procedimiento de aprobación durante la semana de Estrasburgo",
        "source": "Informe en proyecto de la comisión LIBE del PE, lunes 18 de mayo",
        "snippet": (
            "El mandato de siete años de Laura Codruta Kovesi como Fiscal Jefe Europea termina en "
            "octubre de 2026. La lista corta conjunta Consejo-PE para su sucesor sigue siendo "
            "confidencial. El informe en proyecto de LIBE sobre el procedimiento de aprobación "
            "reapareció hoy, aunque no hay votación plenaria programada esta semana. El expediente "
            "está en preparación en fase de comisión; la votación de aprobación en pleno se espera "
            "como muy pronto en junio o julio."
        ),
        "ask": "¿En qué consiste el procedimiento de aprobación para nombrar al próximo Fiscal Jefe Europeo de la EPPO?",
        "feature_label": "Seguimiento legislativo",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#059669",
    },
    {
        "title": "AFCO presenta hoy cuatro informes institucionales: Unión Europea de Defensa, relación Parlamento-Comisión, Artículo 19 TUE, y nombramientos en agencias",
        "source": "Portal de la comisión AFCO del PE, lunes 18 de mayo",
        "snippet": (
            "La comisión de Asuntos Constitucionales presentó cuatro informes en proyecto el lunes "
            "por la mañana. Cubren la arquitectura de la Unión Europea de Defensa Común, el Acuerdo "
            "Marco entre el Parlamento y la Comisión, el marco institucional de la UE bajo el "
            "Artículo 19 TUE (el artículo del Tratado que exige a los tribunales nacionales facilitar "
            "la tutela judicial bajo el Derecho de la Unión), y el artículo 135 del Reglamento del PE "
            "sobre los nombramientos en las agencias de la Unión. Ninguno de estos temas aparece hoy "
            "en la prensa generalista."
        ),
        "ask": "¿Qué propone AFCO sobre la arquitectura institucional de la Unión Europea de Defensa Común?",
        "feature_label": "Análisis de posiciones",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=position_analysis",
        "color": "#d97706",
    },
    {
        "title": "El presupuesto plurianual de la UE para 2028 a 2034 vuelve al Parlamento con la opinión de PETI presentada hoy",
        "source": "Portal de la comisión PETI del PE, lunes 18 de mayo",
        "snippet": (
            "PETI presentó esta mañana su opinión sobre el Marco Financiero Plurianual para el "
            "período 2028-2034. La propuesta de la Comisión establece un compromiso total de "
            "aproximadamente 1,763 billones de euros en precios de 2025 (alrededor del 1,26 por "
            "ciento de la RNB de la UE), simplifica la arquitectura de siete rúbricas a cuatro, y "
            "consolida los 52 programas anteriores en 16. Alrededor del 35 por ciento se destina al "
            "gasto climático, con la devolución de la deuda de NextGenerationEU incluida. La opinión "
            "de PETI se suma a otros siete expedientes presentados por la misma comisión esta "
            "semana de pleno."
        ),
        "ask": "¿Cuál es la estructura y el calendario del presupuesto plurianual de la Unión Europea para 2028 a 2034?",
        "feature_label": "Seguimiento legislativo",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#dc2626",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  El pleno de Estrasburgo abre mañana. A continuación, <strong>cinco movimientos institucionales</strong>
  de esta semana que la prensa europea generalista (Politico, Euractiv, Euronews) y la prensa
  financiera anglosajona (FT, Bloomberg, Reuters) no cubrirán hoy.
</p>
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
  Cada uno se puede consultar en el chat de Brubru en seis idiomas, y cada uno apunta a la
  herramienta de Brubru con la que puedes actuar al respecto.
</p>
"""

FOOTER_INTRO_HTML = """
<p style="font-size: 14px; color: #6b7280; line-height: 1.6; margin: 20px 0 12px 0; padding-top: 16px; border-top: 1px solid #e5e7eb;">
  El Brubru Brief llega solo cuando hay una señal institucional que merezca tu tiempo, no según
  el calendario. Para el flujo diario continuo, el chat en
  <a href="https://brubru.beresol.eu" style="color: #0693e3; text-decoration: none;">brubru.beresol.eu</a>
  y
  <a href="https://www.linkedin.com/company/105185376/" style="color: #0693e3; text-decoration: none;">nuestra página de LinkedIn</a>
  lo cubren.
</p>
"""


def _build_headline_block(h: dict, index: int) -> str:
    color = h["color"]
    ask_url = f"{BRUBRU_CHAT}?q={quote(h['ask'])}"
    return f"""
    <tr>
      <td style="padding: 18px 0; border-bottom: 1px solid #f3f4f6;">
        <div style="color: #111827; font-size: 16px; font-weight: 600; line-height: 1.4; margin-bottom: 8px;">
          {index + 1}. {h['title']}
        </div>
        <div style="color: #374151; font-size: 14px; line-height: 1.6; margin-bottom: 10px;">
          {h['snippet']}
        </div>
        <div style="margin-bottom: 6px;">
          <a href="{ask_url}" style="color: {color}; font-size: 14px; font-style: italic; text-decoration: none; line-height: 1.4;">
            &ldquo;{h['ask']}&rdquo;
          </a>
        </div>
        <div style="margin-bottom: 6px;">
          <a href="{ask_url}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none; margin-right: 6px;">
            Pregúntale a Brubru
          </a>
          <a href="{h['feature_url']}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: #ffffff; background: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none;">
            Ir a {h['feature_label']}
          </a>
        </div>
        <div style="font-size: 11px; color: #9ca3af; margin-top: 6px;">
          Fuente: {h['source']}
        </div>
      </td>
    </tr>"""


def _build_html(recipient: str) -> str:
    headline_rows = "\n".join(_build_headline_block(h, i) for i, h in enumerate(HEADLINES))
    unsub_url = (
        "https://brubru-production.up.railway.app/api/daily-brief/unsubscribe?email="
        + quote(recipient)
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Brubru Brief: Lo que nadie más te cuenta sobre la Burbuja UE</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb; padding: 24px 0;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="640" style="max-width: 640px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
        <tr><td style="padding: 32px 32px 8px 32px;">
          <div style="font-family: 'Adobe Caslon Pro', Georgia, serif; font-size: 28px; font-weight: 700; color: #111827; letter-spacing: -0.5px;">
            Brubru Brief
          </div>
          <div style="font-size: 14px; color: #6b7280; margin-top: 4px;">
            Lunes 18 de mayo de 2026, semana de pleno en Estrasburgo
          </div>
        </td></tr>
        <tr><td style="padding: 16px 32px 0 32px;">
          {HERO_HTML}
        </td></tr>
        <tr><td style="padding: 0 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            {headline_rows}
          </table>
        </td></tr>
        <tr><td style="padding: 0 32px;">
          {FOOTER_INTRO_HTML}
        </td></tr>
        <tr><td style="padding: 20px 32px 28px 32px; font-size: 11px; color: #9ca3af; line-height: 1.5;">
          Recibes el Brubru Brief porque te diste de alta en
          <a href="https://brubru.beresol.eu" style="color: #9ca3af; text-decoration: underline;">brubru.beresol.eu</a>,
          fuiste capturado a través de un correo de Brubru, o tu organización está registrada en el
          Registro de Transparencia de la UE en un ámbito político que aparece en los titulares de hoy.
          <br>
          <a href="{unsub_url}" style="color: #9ca3af; text-decoration: underline;">Cancelar suscripción</a>
          &middot;
          <a href="https://brubru.beresol.eu" style="color: #9ca3af; text-decoration: underline;">brubru.beresol.eu</a>
          &middot;
          <a href="https://beresol.eu" style="color: #9ca3af; text-decoration: underline;">Beresol</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_test():
    test_email = "hello@beresol.eu"
    html = _build_html(test_email)
    service = EmailService()
    ok = service.send(
        to=test_email,
        subject=f"[TEST] {SUBJECT}",
        html_body=html,
    )
    if ok:
        print(f"[OK] Test sent to {test_email}")
        print(f"     Subject: [TEST] {SUBJECT}")
        print(f"     Headlines: {len(HEADLINES)}")
    else:
        print("[ERROR] Test send failed")
        sys.exit(1)


# Generic local-parts that must NEVER receive marketing/outreach emails
# (per memory/feedback_no_generic_inbox_sends.md, set 18 May 2026).
GENERIC_LOCAL_PARTS = (
    'info', 'contact', 'office', 'mail', 'support', 'secretary', 'admin',
    'webmaster', 'enquiries', 'inquiries', 'hello',
)


def preview():
    db = SessionLocal()
    try:
        total = db.execute(text(
            "SELECT COUNT(*) FROM transparency_register_orgs WHERE country='SPAIN'"
        )).scalar()
        with_email = db.execute(text(
            "SELECT COUNT(*) FROM transparency_register_orgs WHERE country='SPAIN' "
            "AND contact_email IS NOT NULL AND contact_email <> ''"
        )).scalar()
        generic_share = db.execute(text(
            "SELECT COUNT(*) FROM transparency_register_orgs WHERE country='SPAIN' "
            "AND contact_email IS NOT NULL AND contact_email <> '' "
            "AND LOWER(SPLIT_PART(contact_email,'@',1)) = ANY(:generic_parts)"
        ), {"generic_parts": list(GENERIC_LOCAL_PARTS)}).scalar()
        verified = db.execute(text(
            "SELECT COUNT(*) FROM transparency_register_orgs WHERE country='SPAIN' "
            "AND email_verified=true AND outreach_status NOT IN ('bounced','unsubscribed') "
            "AND LOWER(SPLIT_PART(contact_email,'@',1)) <> ALL(:generic_parts)"
        ), {"generic_parts": list(GENERIC_LOCAL_PARTS)}).scalar()
        print("SPAIN EUTR pool inventory:")
        print(f"  Total orgs:                                 {total}")
        print(f"  With contact_email:                         {with_email}")
        print(f"  ... of which generic-inbox (info@/...):     {generic_share}  [BLOCKED by filter]")
        print(f"  Verified + sendable (real-person, not bounced): {verified}")
        if verified == 0:
            print()
            print("[BLOCKED] No verified, non-generic addresses. Live send disabled.")
            print("          Manually verify a subset via website crawl + LinkedIn before next attempt.")
            print("          See memory/feedback_no_generic_inbox_sends.md (18 May 2026).")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Send TEST to hello@beresol.eu")
    parser.add_argument("--preview", action="store_true", help="Show SPAIN sendable pool")
    parser.add_argument("--send-eutr-es", action="store_true", help="LIVE send to SPAIN EUTR verified orgs (blocked today)")
    args = parser.parse_args()
    if args.test:
        send_test()
    elif args.preview:
        preview()
    elif args.send_eutr_es:
        db = SessionLocal()
        try:
            verified = db.execute(text(
                "SELECT COUNT(*) FROM transparency_register_orgs WHERE country='SPAIN' "
                "AND email_verified=true AND outreach_status NOT IN ('bounced','unsubscribed')"
            )).scalar()
        finally:
            db.close()
        if verified == 0:
            print("[BLOCKED] SPAIN EUTR sendable pool is 0. Verify emails first.")
            print("          See memory/feedback_eutr_email_verification_required.md (11 May 2026).")
            sys.exit(1)
        print("(live send not implemented in this short script; once pool > 0, build the per-recipient SMTP loop like the EN script).")
    else:
        parser.print_help()
