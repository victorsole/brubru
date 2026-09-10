#!/usr/bin/env python3.12
"""D1a: bring the Critical Medicines Act deep-dive up to date (6 languages).

WHAT CHANGED SINCE THE PAGE WAS WRITTEN
---------------------------------------
The page's timeline ended at the 11-12 May 2026 provisional agreement, marked
active, followed by a generic "Next steps".

Brubru's own eMeeting store holds 30 document ROWS for 2025/0102(COD) after that
date, but 14 of the dossier's 23 references appear at more than one meeting -- a
committee agenda re-lists the whole file -- so 30 rows are NOT 30 events. Exactly
TWO documents first appear after May, both SANT, 13 July 2026:

  * "Provisional agreement - Critical Medicines Act"
  * "VL_CMA Regulation 2025_0102(COD)_vote on provisional agreement"

The voting list was read rather than inferred. It says, verbatim:
    "Vote on the text provisionally agreed between the EP and the Council and
     confirmed by COREPER on 20 June 2026 (Roll-call vote)"
    Rapporteur: Tomislav Sokol (EPP).  Header date: 14 July 2026.

NO TALLY IS WRITTEN. The document carries the column headings "In favour /
Against / Abstentions" and no numbers -- it is the ballot, not the result. An
invented tally is the exact fabrication class the audit rules name.

A DATE CONFLICT IS RECORDED RATHER THAN RESOLVED. Council outcome document
ST-11059/26 is headed "Brussels, 30 June 2026" and says "Following the Permanent
Representatives Committee meeting of 30 June 2026 which endorsed the final
compromise text"; Parliament's voting list says COREPER confirmed on 20 June
2026. Two primary sources, two dates. The page states the Council's own date for
its own meeting and notes Parliament's differs, because silently picking one
would be a guess presented as a fact.

Idempotent: re-running detects the marker and does nothing.
"""
import argparse
import pathlib
import re
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DIR = _REPO_ROOT / "frontend" / "public" / "critical-medicines-act"
MARKER = "data-brubru-update=\"2026-09-10-cma\""

ST = "https://data.consilium.europa.eu/doc/document/ST-11059-2026-INIT/en/pdf"
VL = ("https://www.europarl.europa.eu/meetdocs/2024_2029/plmrep/COMMITTEES/SANT/DV/2026/07-13/"
      "VL_CMARegulation2025_0102(COD)_voteonprovisionalagreement_EN.pdf")

# (new timeline items HTML, replacement "next steps" text, replacement banner strong, banner small)
L = {
"index": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 June 2026</div>
      <div class="timeline__text"><strong>COREPER endorses the final compromise text.</strong> The Presidency sent it to the chair of Parliament's Committee on Public Health, annexed to Council document <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. That annex is still headed <em>Regulation (EU) 2026/… of …</em>: the number and date are not yet assigned. Parliament's own voting list dates the COREPER confirmation to 20 June 2026; the two institutions' documents differ on the day.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 July 2026</div>
      <div class="timeline__text"><strong>SANT votes on the provisionally agreed text.</strong> The Committee on Public Health held a <strong>roll-call vote</strong> on the text agreed with the Council, rapporteur <strong>Tomislav Sokol</strong> (EPP). See the <a href="{vl}" target="_blank" rel="noopener">committee voting list</a>. The published list carries the ballot, not the result, so no tally is reproduced here.</div>
    </div>
""",
  "Plenary confirmation by both institutions; legal-linguistic revision in all EU official languages; formal adoption and publication in the Official Journal; entry into force and application dates as set out in Chapter VIII. COREPER and the SANT committee have now both endorsed the text, so the remaining steps are the plenary vote, the lawyer-linguists and publication.",
  "Provisional agreement 11-12 May 2026; endorsed by COREPER and voted in the SANT committee in July 2026",
  "Still not law: awaiting the plenary vote, legal-linguistic revision and publication in the Official Journal")),

"es": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 de junio de 2026</div>
      <div class="timeline__text"><strong>El COREPER refrenda el texto de compromiso final.</strong> La Presidencia lo remitió a la presidencia de la Comisión de Salud Pública del Parlamento, como anexo al documento del Consejo <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. Ese anexo sigue encabezado <em>Reglamento (UE) 2026/… de …</em>: el número y la fecha aún no están asignados. La lista de votación del Parlamento sitúa la confirmación del COREPER el 20 de junio de 2026; los documentos de ambas instituciones difieren en el día.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 de julio de 2026</div>
      <div class="timeline__text"><strong>La comisión SANT vota el texto acordado provisionalmente.</strong> La Comisión de Salud Pública celebró una <strong>votación nominal</strong> sobre el texto acordado con el Consejo, ponente <strong>Tomislav Sokol</strong> (PPE). Véase la <a href="{vl}" target="_blank" rel="noopener">lista de votación</a>. La lista publicada contiene la papeleta, no el resultado, por lo que aquí no se reproduce ningún recuento.</div>
    </div>
""",
  "Confirmación en el pleno por ambas instituciones; revisión jurídico-lingüística en todas las lenguas oficiales de la UE; adopción formal y publicación en el Diario Oficial; entrada en vigor y fechas de aplicación conforme al capítulo VIII. El COREPER y la comisión SANT ya han refrendado el texto, de modo que quedan la votación en el pleno, los juristas-lingüistas y la publicación.",
  "Acuerdo provisional de 11-12 de mayo de 2026; refrendado por el COREPER y votado en la comisión SANT en julio de 2026",
  "Aún no es ley: pendiente de la votación en el pleno, la revisión jurídico-lingüística y la publicación en el Diario Oficial")),

"ca": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 de juny de 2026</div>
      <div class="timeline__text"><strong>El COREPER referenda el text de compromís final.</strong> La Presidència el va trametre a la presidència de la Comissió de Salut Pública del Parlament, com a annex al document del Consell <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. Aquest annex encara duu l'encapçalament <em>Reglament (UE) 2026/… de …</em>: el número i la data encara no estan assignats. La llista de votació del Parlament situa la confirmació del COREPER el 20 de juny de 2026; els documents de les dues institucions difereixen en el dia.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 de juliol de 2026</div>
      <div class="timeline__text"><strong>La comissió SANT vota el text acordat provisionalment.</strong> La Comissió de Salut Pública va celebrar una <strong>votació nominal</strong> sobre el text acordat amb el Consell, ponent <strong>Tomislav Sokol</strong> (PPE). Vegeu la <a href="{vl}" target="_blank" rel="noopener">llista de votació</a>. La llista publicada conté la papereta, no el resultat, de manera que aquí no es reprodueix cap recompte.</div>
    </div>
""",
  "Confirmació al ple per part de les dues institucions; revisió juridicolingüística en totes les llengües oficials de la UE; adopció formal i publicació al Diari Oficial; entrada en vigor i dates d'aplicació segons el capítol VIII. El COREPER i la comissió SANT ja han referendat el text, de manera que queden la votació al ple, els juristes-lingüistes i la publicació.",
  "Acord provisional de l'11-12 de maig de 2026; referendat pel COREPER i votat a la comissió SANT el juliol de 2026",
  "Encara no és llei: pendent de la votació al ple, la revisió juridicolingüística i la publicació al Diari Oficial")),

"fr": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 juin 2026</div>
      <div class="timeline__text"><strong>Le COREPER approuve le texte de compromis final.</strong> La présidence l'a transmis au président de la commission de la santé publique du Parlement, en annexe au document du Conseil <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. Cette annexe porte encore l'intitulé <em>Règlement (UE) 2026/… du …</em> : le numéro et la date ne sont pas encore attribués. La liste de vote du Parlement date la confirmation du COREPER du 20 juin 2026 ; les documents des deux institutions divergent sur le jour.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 juillet 2026</div>
      <div class="timeline__text"><strong>La commission SANT vote le texte provisoirement convenu.</strong> La commission de la santé publique a procédé à un <strong>vote par appel nominal</strong> sur le texte convenu avec le Conseil, rapporteur <strong>Tomislav Sokol</strong> (PPE). Voir la <a href="{vl}" target="_blank" rel="noopener">liste de vote</a>. La liste publiée contient le bulletin, non le résultat : aucun décompte n'est donc reproduit ici.</div>
    </div>
""",
  "Confirmation en plénière par les deux institutions ; révision juridico-linguistique dans toutes les langues officielles de l'UE ; adoption formelle et publication au Journal officiel ; entrée en vigueur et dates d'application prévues au chapitre VIII. Le COREPER et la commission SANT ayant tous deux approuvé le texte, il reste le vote en plénière, les juristes-linguistes et la publication.",
  "Accord provisoire des 11-12 mai 2026 ; approuvé par le COREPER et voté en commission SANT en juillet 2026",
  "Pas encore en vigueur : en attente du vote en plénière, de la révision juridico-linguistique et de la publication au Journal officiel")),

"it": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 giugno 2026</div>
      <div class="timeline__text"><strong>Il COREPER approva il testo di compromesso finale.</strong> La presidenza lo ha trasmesso al presidente della commissione per la sanità pubblica del Parlamento, in allegato al documento del Consiglio <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. L'allegato reca ancora l'intestazione <em>Regolamento (UE) 2026/… del …</em>: numero e data non sono ancora assegnati. L'elenco di votazione del Parlamento colloca la conferma del COREPER al 20 giugno 2026; i documenti delle due istituzioni divergono sul giorno.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 luglio 2026</div>
      <div class="timeline__text"><strong>La commissione SANT vota il testo concordato in via provvisoria.</strong> La commissione per la sanità pubblica ha tenuto una <strong>votazione per appello nominale</strong> sul testo concordato con il Consiglio, relatore <strong>Tomislav Sokol</strong> (PPE). Si veda l'<a href="{vl}" target="_blank" rel="noopener">elenco di votazione</a>. L'elenco pubblicato contiene la scheda, non il risultato, perciò qui non si riproduce alcun conteggio.</div>
    </div>
""",
  "Conferma in plenaria da parte di entrambe le istituzioni; revisione giuridico-linguistica in tutte le lingue ufficiali dell'UE; adozione formale e pubblicazione nella Gazzetta ufficiale; entrata in vigore e date di applicazione di cui al capo VIII. COREPER e commissione SANT hanno ormai entrambi approvato il testo, restano quindi il voto in plenaria, i giuristi-linguisti e la pubblicazione.",
  "Accordo provvisorio dell'11-12 maggio 2026; approvato dal COREPER e votato in commissione SANT nel luglio 2026",
  "Non ancora legge: in attesa del voto in plenaria, della revisione giuridico-linguistica e della pubblicazione nella Gazzetta ufficiale")),

"nl": (
 ("""    <div class="timeline__item" {m}>
      <div class="timeline__date">30 juni 2026</div>
      <div class="timeline__text"><strong>Coreper bekrachtigt de definitieve compromistekst.</strong> Het voorzitterschap zond die naar de voorzitter van de commissie volksgezondheid van het Parlement, als bijlage bij Raadsdocument <a href="{st}" target="_blank" rel="noopener">ST-11059/26</a>. Die bijlage draagt nog het opschrift <em>Verordening (EU) 2026/… van …</em>: nummer en datum zijn nog niet toegekend. De stemlijst van het Parlement dateert de bevestiging door Coreper op 20 juni 2026; de documenten van beide instellingen verschillen over de dag.</div>
    </div>
    <div class="timeline__item timeline__item--active" {m}>
      <div class="timeline__date">13-14 juli 2026</div>
      <div class="timeline__text"><strong>De commissie SANT stemt over de voorlopig overeengekomen tekst.</strong> De commissie volksgezondheid hield een <strong>hoofdelijke stemming</strong> over de met de Raad overeengekomen tekst, rapporteur <strong>Tomislav Sokol</strong> (EVP). Zie de <a href="{vl}" target="_blank" rel="noopener">stemlijst</a>. De gepubliceerde lijst bevat het stembiljet, niet de uitslag, dus hier wordt geen telling weergegeven.</div>
    </div>
""",
  "Bevestiging in de plenaire vergadering door beide instellingen; juridisch-taalkundige herziening in alle officiële EU-talen; formele aanneming en bekendmaking in het Publicatieblad; inwerkingtreding en toepassingsdata zoals bepaald in hoofdstuk VIII. Coreper en de commissie SANT hebben de tekst nu beide bekrachtigd, zodat de plenaire stemming, de juristen-linguïsten en de bekendmaking resteren.",
  "Voorlopig akkoord van 11-12 mei 2026; bekrachtigd door Coreper en in de commissie SANT gestemd in juli 2026",
  "Nog geen wet: in afwachting van de plenaire stemming, de juridisch-taalkundige herziening en de bekendmaking in het Publicatieblad")),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    changed = 0
    for key, (items, nextsteps, strong, small) in L.items():
        path = DIR / (f"{key}.html" if key != "index" else "index.html")
        if not path.exists():
            print(f"  [warn] {path.name} missing"); continue
        text = path.read_text(encoding="utf-8")
        if MARKER in text:
            print(f"  [skip] {path.name} already updated"); continue

        new = text
        # 1. demote the old active marker
        new = new.replace('<div class="timeline__item timeline__item--active">',
                          '<div class="timeline__item">', 1)
        # 2. insert the two new items before the "next steps" item
        anchor = '<div class="timeline__item timeline__item--next">'
        if anchor not in new:
            print(f"  [warn] {path.name}: no next-steps anchor, skipped"); continue
        block = items.format(m=MARKER, st=ST, vl=VL)
        i = new.index(anchor)
        line_start = new.rindex("\n", 0, i) + 1
        new = new[:line_start] + block + new[line_start:]
        # 3. rewrite the next-steps prose
        j = new.index(anchor)
        k = new.index('<div class="timeline__text">', j) + len('<div class="timeline__text">')
        end = new.index("</div>", k)
        new = new[:k] + nextsteps + new[end:]
        # 4. refresh the status banner
        new = re.sub(r"(<div class=\"status-banner\">.*?<strong>)(.*?)(</strong>)",
                     lambda mo: mo.group(1) + strong + mo.group(3), new, count=1, flags=re.S)
        new = re.sub(r"(<div class=\"status-banner\">.*?<small>)(.*?)(</small>)",
                     lambda mo: mo.group(1) + small + mo.group(3), new, count=1, flags=re.S)

        if new == text:
            print(f"  [warn] {path.name}: nothing changed"); continue
        changed += 1
        print(f"  [edit] {path.name}  (+{len(new)-len(text)} chars)")
        if args.apply:
            path.write_text(new, encoding="utf-8")
    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {changed}/6 files")
    return 0 if changed == 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
