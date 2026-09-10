#!/usr/bin/env python3.12
"""D1b/c: add committee milestones to a deep-dive timeline, in six languages.

WHAT IS AND IS NOT CLAIMED
--------------------------
Only documents whose FIRST appearance in `ep_emeeting_documents` is after the
page's cut-off are treated as new. A committee agenda re-lists a whole dossier,
so raw row counts overstate movement badly: the Critical Medicines Act showed 30
rows after May and had exactly 2 new documents.

Document CONTENTS are not quoted here. The europarl meetdocs host answered
HTTP 202 with a zero-byte body while this ran -- the WAF signature -- so the
voting lists could not be read. What Brubru's own store records (committee, date,
kind, PE reference, URL) is stated; what the documents SAY is not, because it
could not be read today. A voting list also carries the ballot, not the result,
so no tally is written even when the text is readable.
"""
import argparse
import pathlib
import re
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PUBLIC = _REPO_ROOT / "frontend" / "public"
MARK = 'data-brubru-update="2026-09-10"'

PAGES = {
"biotech-act": {
 "index": [("22-29 June 2026",
   "<strong>Opinion-giving committees table their drafts.</strong> ENVI and JURI each tabled a draft opinion (PE788.881 and PE789.902) on 22 June, and ITRE tabled its draft report PE789.987 on 29 June."),
  ("7 September 2026",
   "<strong>JURI returns to the file.</strong> The legal affairs committee tabled amendment PE790.241 and a reasoned opinion PE790.871, and published a voting list for item 17 of its meeting. Brubru holds the documents; their contents are not summarised here because the Parliament's document host was unreachable at the time of writing.")],
 "es": [("22-29 de junio de 2026",
   "<strong>Las comisiones de opinión presentan sus proyectos.</strong> ENVI y JURI presentaron sendos proyectos de opinión (PE788.881 y PE789.902) el 22 de junio, e ITRE presentó su proyecto de informe PE789.987 el 29 de junio."),
  ("7 de septiembre de 2026",
   "<strong>JURI vuelve sobre el expediente.</strong> La comisión de asuntos jurídicos presentó la enmienda PE790.241 y una opinión motivada PE790.871, y publicó una lista de votación para el punto 17 de su reunión. Brubru conserva los documentos; su contenido no se resume aquí porque el servidor documental del Parlamento no estaba accesible en el momento de redactar.")],
 "ca": [("22-29 de juny de 2026",
   "<strong>Les comissions d'opinió presenten els seus projectes.</strong> ENVI i JURI van presentar sengles projectes d'opinió (PE788.881 i PE789.902) el 22 de juny, i ITRE va presentar el seu projecte d'informe PE789.987 el 29 de juny."),
  ("7 de setembre de 2026",
   "<strong>JURI torna a l'expedient.</strong> La comissió d'afers jurídics va presentar l'esmena PE790.241 i una opinió motivada PE790.871, i va publicar una llista de votació per al punt 17 de la reunió. Brubru conserva els documents; el contingut no es resumeix aquí perquè el servidor documental del Parlament no era accessible en el moment de redactar.")],
 "fr": [("22-29 juin 2026",
   "<strong>Les commissions saisies pour avis déposent leurs projets.</strong> ENVI et JURI ont chacune déposé un projet d'avis (PE788.881 et PE789.902) le 22 juin, et ITRE a déposé son projet de rapport PE789.987 le 29 juin."),
  ("7 septembre 2026",
   "<strong>La commission JURI revient sur le dossier.</strong> La commission des affaires juridiques a déposé l'amendement PE790.241 et un avis motivé PE790.871, et publié une liste de vote pour le point 17 de sa réunion. Brubru conserve les documents ; leur contenu n'est pas résumé ici, le serveur documentaire du Parlement étant inaccessible au moment de la rédaction.")],
 "it": [("22-29 giugno 2026",
   "<strong>Le commissioni competenti per parere depositano i progetti.</strong> ENVI e JURI hanno depositato ciascuna un progetto di parere (PE788.881 e PE789.902) il 22 giugno, e ITRE ha depositato il proprio progetto di relazione PE789.987 il 29 giugno."),
  ("7 settembre 2026",
   "<strong>JURI torna sul fascicolo.</strong> La commissione giuridica ha depositato l'emendamento PE790.241 e un parere motivato PE790.871, e ha pubblicato un elenco di votazione per il punto 17 della riunione. Brubru conserva i documenti; il contenuto non è riassunto qui perché il server documentale del Parlamento non era raggiungibile al momento della stesura.")],
 "nl": [("22-29 juni 2026",
   "<strong>De adviserende commissies dienen hun ontwerpen in.</strong> ENVI en JURI dienden elk een ontwerpadvies in (PE788.881 en PE789.902) op 22 juni, en ITRE diende op 29 juni haar ontwerpverslag PE789.987 in."),
  ("7 september 2026",
   "<strong>JURI komt terug op het dossier.</strong> De commissie juridische zaken diende amendement PE790.241 en een met redenen omkleed advies PE790.871 in, en publiceerde een stemlijst voor punt 17 van de vergadering. Brubru bewaart de documenten; de inhoud wordt hier niet samengevat omdat de documentserver van het Parlement bij het schrijven onbereikbaar was.")],
},
"industrial-accelerator-act": {
 "index": [("6 July 2026",
   "<strong>ENVI tables its opinion documents.</strong> The environment committee tabled draft opinion PE789.106 and reasoned opinion PE790.123 on the file.")],
 "es": [("6 de julio de 2026",
   "<strong>ENVI presenta sus documentos de opinión.</strong> La comisión de medio ambiente presentó el proyecto de opinión PE789.106 y la opinión motivada PE790.123 sobre el expediente.")],
 "ca": [("6 de juliol de 2026",
   "<strong>ENVI presenta els seus documents d'opinió.</strong> La comissió de medi ambient va presentar el projecte d'opinió PE789.106 i l'opinió motivada PE790.123 sobre l'expedient.")],
 "fr": [("6 juillet 2026",
   "<strong>La commission ENVI dépose ses documents d'avis.</strong> La commission de l'environnement a déposé le projet d'avis PE789.106 et l'avis motivé PE790.123 sur le dossier.")],
 "it": [("6 luglio 2026",
   "<strong>ENVI deposita i suoi documenti di parere.</strong> La commissione ambiente ha depositato il progetto di parere PE789.106 e il parere motivato PE790.123 sul fascicolo.")],
 "nl": [("6 juli 2026",
   "<strong>ENVI dient haar adviesdocumenten in.</strong> De milieucommissie diende ontwerpadvies PE789.106 en met redenen omkleed advies PE790.123 over het dossier in.")],
},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", choices=sorted(PAGES))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    spec = PAGES[args.slug]
    directory = PUBLIC / args.slug
    changed = 0
    for key, entries in spec.items():
        path = directory / (f"{key}.html" if key != "index" else "index.html")
        if not path.exists():
            print(f"  [warn] {path.name} missing"); continue
        text = path.read_text(encoding="utf-8")
        if MARK in text:
            print(f"  [skip] {path.name} already updated"); continue

        block = "".join(
            f'    <div class="timeline__item{" timeline__item--active" if i == len(entries)-1 else ""}" {MARK}>\n'
            f'      <div class="timeline__date">{d}</div>\n'
            f'      <div class="timeline__text">{t}</div>\n'
            f'    </div>\n'
            for i, (d, t) in enumerate(entries))

        new = text.replace('<div class="timeline__item timeline__item--active">',
                           '<div class="timeline__item">', 1)
        anchor = '<div class="timeline__item timeline__item--next">'
        if anchor in new:
            i = new.index(anchor)
        else:
            # no "next" item: append after the last timeline item instead
            i = new.rindex('</div>', 0, new.index('</div>', new.rindex('timeline__text')))
            i = new.index('\n', i) + 1
        start = new.rindex("\n", 0, i) + 1 if anchor in new else i
        new = new[:start] + block + new[start:]

        if new == text:
            print(f"  [warn] {path.name}: nothing changed"); continue
        changed += 1
        print(f"  [edit] {path.name} (+{len(new)-len(text)} chars, {len(entries)} entr{'y' if len(entries)==1 else 'ies'})")
        if args.apply:
            path.write_text(new, encoding="utf-8")
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
