"""
One-off welcome email to Guiomar Ibáñez (ACCIÓ, gencat.cat).

Modes:
  --preview        print plain + html to terminal (default)
  --test           send to hello@beresol.eu
  --send           send to guiomar.ibanez@gencat.cat

Hard rules enforced:
  - Catalan body, signature 'Víctor Solé' with accent
  - From: hello@beresol.eu (never victor@)
  - No em-dashes, no emojis
  - Multipart/alternative with HTML hyperlink on "dret europeu en català"
"""
from __future__ import annotations
import argparse, os, smtplib, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1].parent / ".env")

RECIPIENT       = "guiomar.ibanez@gencat.cat"
RECIPIENT_NAME  = "Guiomar Ibáñez"
TEST_RECIPIENT  = "hello@beresol.eu"
FROM_ADDR       = "hello@beresol.eu"
FROM_NAME       = "Víctor Solé (Brubru)"
LOGIN_URL       = "https://brubru.beresol.eu/login"
CATALA_LAW_URL  = "https://brubru.beresol.eu/legislacio-ue-catala/"

SUBJECT = "Guiomar, els fitxers UE per a la detecció tecnològica d'ACCIÓ"

BODY_PLAIN = f"""Hola Guiomar,

Sóc el Víctor, fundador de Brubru. Vaig veure que dilluns vas crear un compte a brubru.beresol.eu però la sessió va quedar a mitges, així que t'escric per donar-te la benvinguda i explicar-te què hi trobaràs.

Brubru és un assistent d'IA per a afers legislatius europeus. Coneixent la teva feina a ACCIÓ com a líder de l'equip d'Anàlisi i Detecció d'Oportunitats Tecnològiques, i recordant la presentació de l'informe sobre robòtica a Catalunya del passat 4 de maig, hem deixat el teu perfil llest amb els fitxers UE que més afecten l'agenda de detecció tecnològica:

  1. Industrial Accelerator Act
  2. Critical Raw Materials Act (i les seves modificacions)
  3. Net-Zero Industry Act
  4. Chips Act
  5. Digital Networks Act
  6. Carbon Border Adjustment Mechanism (CBAM)
  7. Anti-Coercion Instrument
  8. Horizon Europe (R+D 2028-2034)

També t'hem subscrit a cinc canals de notícies de la Comissió (DG GROW, DG RTD, DG CNECT i Eurostat). A My EU Bubble veuràs cada fitxer amb l'estat actual, el ponent del Parlament, la configuració de Consell i la propera data de decisió.

Una cosa més: Brubru també publica el dret europeu en català, traduint la legislació adoptada de l'OJ. És probable que sigui útil a l'equip d'ACCIÓ i a la delegació a Brussel·les per consultar regulacions concretes en la llengua de treball.

Pots tornar a entrar aquí: {LOGIN_URL}

Si vols, faig una demo curta de quinze minuts ajustada al cas d'ús d'ACCIÓ. Respon a aquest correu i quadrem.

Una abraçada,

Víctor Solé Ferioli
Fundador, Beresol BV
{FROM_ADDR}
"""

BODY_HTML = f"""<!doctype html>
<html lang="ca">
<body style="font-family: Georgia, 'Times New Roman', serif; font-size: 16px; color: #1a1a1a; line-height: 1.55; max-width: 640px; margin: 0 auto; padding: 24px;">

<p>Hola Guiomar,</p>

<p>Sóc el Víctor, fundador de Brubru. Vaig veure que dilluns vas crear un compte a <a href="https://brubru.beresol.eu" style="color: #0693e3; text-decoration: none;">brubru.beresol.eu</a> però la sessió va quedar a mitges, així que t'escric per donar-te la benvinguda i explicar-te què hi trobaràs.</p>

<p>Brubru és un assistent d'IA per a afers legislatius europeus. Coneixent la teva feina a ACCIÓ com a líder de l'equip d'Anàlisi i Detecció d'Oportunitats Tecnològiques, i recordant la presentació de l'informe sobre robòtica a Catalunya del passat 4 de maig, hem deixat el teu perfil llest amb els fitxers UE que més afecten l'agenda de detecció tecnològica:</p>

<ol style="padding-left: 22px;">
  <li>Industrial Accelerator Act</li>
  <li>Critical Raw Materials Act (i les seves modificacions)</li>
  <li>Net-Zero Industry Act</li>
  <li>Chips Act</li>
  <li>Digital Networks Act</li>
  <li>Carbon Border Adjustment Mechanism (CBAM)</li>
  <li>Anti-Coercion Instrument</li>
  <li>Horizon Europe (R+D 2028-2034)</li>
</ol>

<p>També t'hem subscrit a cinc canals de notícies de la Comissió (DG GROW, DG RTD, DG CNECT i Eurostat). A <em>My EU Bubble</em> veuràs cada fitxer amb l'estat actual, el ponent del Parlament, la configuració de Consell i la propera data de decisió.</p>

<p>Una cosa més: Brubru també publica el <a href="{CATALA_LAW_URL}" style="color: #0693e3; text-decoration: none; font-weight: 600;">dret europeu en català</a>, traduint la legislació adoptada de l'OJ. És probable que sigui útil a l'equip d'ACCIÓ i a la delegació a Brussel·les per consultar regulacions concretes en la llengua de treball.</p>

<p style="margin: 28px 0;">
  <a href="{LOGIN_URL}" style="background: linear-gradient(135deg, #0693e3 0%, #9b51e0 100%); color: #ffffff; padding: 12px 22px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">Entrar a Brubru</a>
</p>

<p>Si vols, faig una demo curta de quinze minuts ajustada al cas d'ús d'ACCIÓ. Respon a aquest correu i quadrem.</p>

<p>Una abraçada,</p>

<p style="margin-bottom: 4px;"><strong>Víctor Solé Ferioli</strong><br/>
Fundador, Beresol BV<br/>
<a href="mailto:{FROM_ADDR}" style="color: #0693e3;">{FROM_ADDR}</a></p>

</body>
</html>
"""


def preflight() -> None:
    text_blob = BODY_PLAIN + BODY_HTML + SUBJECT
    assert "Solé" in text_blob, "missing accented Solé"
    assert "victor@" not in text_blob, "must not use victor@ address"
    assert "—" not in text_blob and "–" not in text_blob, "no em/en dashes"
    assert "23 idiomes" not in text_blob and "23 languages" not in text_blob
    # crude emoji check
    for ch in text_blob:
        if ord(ch) >= 0x1F000:
            raise AssertionError(f"emoji-range char found: {ch!r}")


def build_message(to_addr: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>"
    msg["To"] = to_addr
    msg["Reply-To"] = FROM_ADDR
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(BODY_PLAIN, "plain", "utf-8"))
    msg.attach(MIMEText(BODY_HTML, "html", "utf-8"))
    return msg


def send_via_smtp(to_addr: str) -> None:
    pwd = os.environ.get("SMTP_PASSWORD")
    if not pwd:
        sys.exit("SMTP_PASSWORD not set in environment")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", FROM_ADDR)
    msg = build_message(to_addr)
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
    print(f"[OK] sent to {to_addr}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", default=True)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()

    preflight()

    if args.send:
        send_via_smtp(RECIPIENT)
        return
    if args.test:
        send_via_smtp(TEST_RECIPIENT)
        return

    print("=" * 70)
    print(f"Subject: {SUBJECT}")
    print(f"To:      {RECIPIENT}")
    print(f"From:    {FROM_NAME} <{FROM_ADDR}>")
    print("=" * 70)
    print(BODY_PLAIN)
    print("=" * 70)
    print("[OK] preflight passed. Use --test then --send.")


if __name__ == "__main__":
    main()
