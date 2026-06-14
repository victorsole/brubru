"""
Generate the 5 translated Brubru API-docs landing pages (es/fr/it/nl/ca.html)
from a single structural template, translating only the visible strings.

Structure is identical across all languages (no tag drift). Code blocks, URLs,
folder slugs, agency acronyms and the switcher option values stay verbatim.
English source of truth: index.html (kept in sync by hand).

Run: python3.12 frontend/scripts/gen_api_docs_translations.py
"""
import pathlib

DOCS = pathlib.Path(__file__).resolve().parents[1] / "public" / "api" / "docs"

# Folder slugs in canonical display order (anchors in endpoints.html). Language-independent.
ORDER_SECTIONS = [
    ("legislation", ["legislative"]),
    ("parliament", ["parliament"]),
    ("council", ["council", "european-council", "eurogroup"]),
    ("commission", ["commission"]),
    ("economic", ["ecb", "eu-financial-institutions", "esm"]),
    ("agencies", ["acer","berec","cedefop","cpvo","ecdc","echa","eea","efsa","eige","eit","ema","enisa","eu-lisa","eu-osha","euaa","euda","euipo","fra"]),
    ("funding", ["funding", "consultations"]),
    ("opendata", ["open-data", "general-publications", "who-is-who", "geographical-indications"]),
    ("proprietary", ["proprietary"]),
]

# Per-language data. Each lang provides: meta scalars, the 9 section titles,
# the word for folder(s), the 34 card (title, desc), the cadence table rows,
# nav section headers + nav link labels.
LANGS = {}

# ---------------------------------------------------------------- SPANISH ----
LANGS["es"] = {
  "lang": "es", "sep_opt": "es.html",
  "title": "Introducci&oacute;n &mdash; Brubru EU Data API",
  "desc": "Brubru EU Data API v2: 469 endpoints REST en 34 carpetas de instituciones de la UE. 8.710 leyes de la UE, procedimientos legislativos, eurodiputados y funcionarios, enmiendas, las bases de datos de Parlamento / Consejo / Comisi&oacute;n, las bases de datos de las agencias de la UE (medicamentos, seguridad alimentaria, medio ambiente, sustancias qu&iacute;micas, drogas, derechos fundamentales), financiaci&oacute;n, datos abiertos y la inteligencia propia de Brubru sobre la UE. Una sola clave de API.",
  "pw_text": "Est&aacute; viendo la referencia. Para ejecutar llamadas reales necesita una clave de API de Brubru &mdash; ",
  "pw_trial": "Inicie una prueba Professional",
  "pw_or": " &middot; o ",
  "pw_sales": "contacte con ventas",
  "eyebrow": "Brubru EU Data API &middot; v2 &middot; 469 endpoints en 34 carpetas de instituciones de la UE",
  "h1": "La UE, estructurada.",
  "lede": "Brubru es un proveedor vertical de datos de la UE. Nuestra API REST da a desarrolladores, plataformas RegTech, equipos de asuntos p&uacute;blicos y agentes de IA acceso program&aacute;tico a <strong>8.710 leyes de la UE adoptadas</strong> (28.513 publicaciones del DO), <strong>2.080 expedientes legislativos</strong> en seguimiento, <strong>16.521 funcionarios de la UE</strong>, todos los eurodiputados, <strong>58.399 enmiendas del PE</strong>, los registros del Parlamento / Consejo / Consejo Europeo / Eurogrupo / Comisi&oacute;n, el Banco Central Europeo y las instituciones financieras de la UE, las agencias descentralizadas de la UE (medicamentos, seguridad alimentaria, medio ambiente, sustancias qu&iacute;micas, drogas, derechos fundamentales y m&aacute;s), financiaci&oacute;n y licitaciones de la UE, datos abiertos y la propia inteligencia de Brubru sobre la UE. Los mismos datos que usamos internamente son los que usted consulta. Brubru es el primer cliente de su propia API.",
  "box": "<strong>Una superficie, una clave.</strong> La API est&aacute; organizada como la propia UE &mdash; una carpeta por instituci&oacute;n u organismo, 34 carpetas en total, <strong>469 endpoints</strong>. Explore las carpetas a continuaci&oacute;n o abra la <a href=\"/api/docs/reference.html\"><strong>referencia completa y siempre actualizada de la API &rarr;</strong></a> &mdash; cada endpoint desplegado, generado en vivo desde la especificaci&oacute;n OpenAPI.",
  "callout_q": "&iquest;Nuevo en las API?",
  "callout_b": " Una API es una forma de que su software hable con el software de Brubru por internet. Usted env&iacute;a una petici&oacute;n HTTP (como hace un navegador) y nosotros devolvemos JSON (datos estructurados). El resto de esta documentaci&oacute;n explica c&oacute;mo.",
  "wyg_h": "Qu&eacute; obtiene",
  "wyg_p": "Cada carpeta corresponde a una instituci&oacute;n u organismo de la UE. Las cifras son exactas y se actualizan a medida que crece la API.",
  "folder_one": "carpeta", "folder_many": "carpetas",
  "sections": {
    "legislation":"Legislaci&oacute;n","parliament":"Parlamento Europeo","council":"Consejo y cumbres",
    "commission":"Comisi&oacute;n Europea","economic":"Econom&iacute;a y finanzas","agencies":"Agencias de la UE",
    "funding":"Financiaci&oacute;n y consultas","opendata":"Datos abiertos y personas","proprietary":"Inteligencia propia",
  },
  "ds_h":"Fuentes de datos y frecuencia de actualizaci&oacute;n",
  "ds_p":"Toda la superficie v2 se resincroniza a diario (un barrido a las 10:00 / 15:00 / 21:00 UTC). Las fuentes de la UE que hay detr&aacute;s de cada carpeta se actualizan con las frecuencias siguientes.",
  "ds_th":["Frecuencia de actualizaci&oacute;n","Qu&eacute; cubre"],
  "auth_h":"Autenticaci&oacute;n de un vistazo",
  "auth_p":"Cada llamada a <code>/api/v2/*</code> requiere una clave de API enviada como token Bearer o como cabecera <code>X-API-Key</code>:",
  "auth_full":"Detalles completos en <a href=\"/api/docs/authentication.html\">Autenticaci&oacute;n</a>.",
  "env_h":"El sobre de respuesta de un vistazo",
  "env_p":"Cada endpoint paginado devuelve la misma forma. Programe una vez contra este sobre y cambie de conjunto de datos cambiando la ruta:",
  "env_hdr_p":"La procedencia y la informaci&oacute;n de l&iacute;mite de uso viven en las cabeceras de respuesta, no en el cuerpo:",
  "env_full":"Detalles completos en <a href=\"/api/docs/envelope.html\">Sobre de respuesta</a>.",
  "qs_h":"Inicio r&aacute;pido: su primera llamada",
  "qs1":"<strong>1. Consiga una clave de API.</strong> Escriba a <a href=\"mailto:hello@beresol.eu\">hello@beresol.eu</a> cuando tenga la suscripci&oacute;n Professional. Las claves tienen la forma <code>brubru_live_</code> seguido de 48 caracteres hexadecimales.",
  "qs2":"<strong>2. Compruebe que el servicio funciona.</strong> El chequeo de salud es p&uacute;blico &mdash; no requiere clave:",
  "qs2resp":"Respuesta:",
  "qs3":"<strong>3. Pruebe una b&uacute;squeda real.</strong>",
  "qs3_after":"Obtiene una lista paginada de leyes de la UE que coinciden con \"artificial intelligence\", con identificadores CELEX, t&iacute;tulos, fechas y URL de EUR-Lex. A partir de ah&iacute;, cada endpoint sigue el mismo patr&oacute;n de sobre &mdash; solo cambie la ruta.",
  "lim_h":"Limitaciones (lo que no cubrimos)",
  "lim":[
    "<strong>Legislaci&oacute;n no comunitaria.</strong> No seguimos los bolet&iacute;nes nacionales directamente. Si necesita el BOE espa&ntilde;ol junto con la UE, comb&iacute;nenos con GovClipping o similar.",
    "<strong>Notificaci&oacute;n en tiempo real.</strong> A&uacute;n no hay webhooks ni SSE. El patr&oacute;n de integraci&oacute;n es el sondeo seg&uacute;n nuestra frecuencia. Webhooks en la hoja de ruta de septiembre de 2026.",
    "<strong>Idiomas.</strong> Las respuestas de la API est&aacute;n hoy en ingl&eacute;s. Algunos textos legales est&aacute;n disponibles en las 24 lenguas de la UE v&iacute;a Cellar, pero las respuestas estructuradas son solo en ingl&eacute;s. Endpoints multiling&uuml;es en septiembre de 2026.",
    "<strong>Exportaciones masivas.</strong> A&uacute;n no hay volcados nocturnos CSV/Parquet. Hoja de ruta de septiembre de 2026. Por ahora, recorra las listas paginadas.",
    "<strong>Parlamentos nacionales.</strong> No ingerimos de los parlamentos <em>nacionales</em>. Solo el PE.",
  ],
  "next_h":"A d&oacute;nde ir despu&eacute;s",
  "next":[
    ("/api/docs/endpoints.html","Todos los endpoints","La lista completa y agrupada de los 469 endpoints de v2, una secci&oacute;n por carpeta de instituci&oacute;n."),
    ("/api/docs/authentication.html","Autenticaci&oacute;n","C&oacute;mo enviar su clave de API, ciclo de vida, rotaci&oacute;n y seguridad."),
    ("/api/docs/use-cases.html","Casos de uso por perfil","Consultores de asuntos p&uacute;blicos, asociaciones, empresas, ONG, funcionarios de la UE &mdash; qu&eacute; consultar&iacute;a realmente."),
    ("/api/docs/glossary.html","Glosario","CELEX, OEIL, tr&iacute;logo, ponente, tipos de comisi&oacute;n, directiva frente a reglamento &mdash; cada sigla explicada."),
  ],
  "footer":"&copy; 2026 Beresol BV &mdash; Brubru EU Data API v2.",
  "footer_back":"Volver a la p&aacute;gina de marketing",
}

# ---------------------------------------------------------------- FRENCH -----
LANGS["fr"] = {
  "lang": "fr", "sep_opt": "fr.html",
  "title": "Introduction &mdash; Brubru EU Data API",
  "desc": "Brubru EU Data API v2 : 469 endpoints REST r&eacute;partis sur 34 dossiers d'institutions de l'UE. 8 710 actes de l'UE, proc&eacute;dures l&eacute;gislatives, d&eacute;put&eacute;s et fonctionnaires, amendements, les bases de donn&eacute;es du Parlement / Conseil / Commission, les bases des agences de l'UE (m&eacute;dicaments, s&eacute;curit&eacute; alimentaire, environnement, produits chimiques, drogues, droits fondamentaux), financements, donn&eacute;es ouvertes et l'intelligence propre de Brubru sur l'UE. Une seule cl&eacute; d'API.",
  "pw_text": "Vous consultez la r&eacute;f&eacute;rence. Pour ex&eacute;cuter des appels r&eacute;els, il vous faut une cl&eacute; d'API Brubru &mdash; ",
  "pw_trial": "D&eacute;marrer un essai Professional",
  "pw_or": " &middot; ou ",
  "pw_sales": "contacter les ventes",
  "eyebrow": "Brubru EU Data API &middot; v2 &middot; 469 endpoints sur 34 dossiers d'institutions de l'UE",
  "h1": "L'UE, structur&eacute;e.",
  "lede": "Brubru est un fournisseur vertical de donn&eacute;es de l'UE. Notre API REST donne aux d&eacute;veloppeurs, plateformes RegTech, &eacute;quipes d'affaires publiques et agents d'IA un acc&egrave;s programmatique &agrave; <strong>8 710 actes de l'UE adopt&eacute;s</strong> (28 513 publications du JO), <strong>2 080 dossiers l&eacute;gislatifs</strong> suivis, <strong>16 521 fonctionnaires de l'UE</strong>, tous les d&eacute;put&eacute;s, <strong>58 399 amendements du PE</strong>, les registres du Parlement / Conseil / Conseil europ&eacute;en / Eurogroupe / Commission, la Banque centrale europ&eacute;enne et les institutions financi&egrave;res de l'UE, les agences d&eacute;centralis&eacute;es de l'UE (m&eacute;dicaments, s&eacute;curit&eacute; alimentaire, environnement, produits chimiques, drogues, droits fondamentaux et plus), financements et appels d'offres de l'UE, donn&eacute;es ouvertes et l'intelligence propre de Brubru sur l'UE. Les m&ecirc;mes donn&eacute;es que nous utilisons en interne sont celles que vous appelez. Brubru est le premier client de sa propre API.",
  "box": "<strong>Une seule surface, une seule cl&eacute;.</strong> L'API est organis&eacute;e comme l'UE elle-m&ecirc;me &mdash; un dossier par institution ou organe, 34 dossiers au total, <strong>469 endpoints</strong>. Parcourez les dossiers ci-dessous ou ouvrez la <a href=\"/api/docs/reference.html\"><strong>r&eacute;f&eacute;rence compl&egrave;te et toujours &agrave; jour de l'API &rarr;</strong></a> &mdash; chaque endpoint d&eacute;ploy&eacute;, g&eacute;n&eacute;r&eacute; en direct depuis la sp&eacute;cification OpenAPI.",
  "callout_q": "Nouveau dans les API&nbsp;?",
  "callout_b": " Une API permet &agrave; votre logiciel de dialoguer avec celui de Brubru sur internet. Vous envoyez une requ&ecirc;te HTTP (comme un navigateur) et nous renvoyons du JSON (des donn&eacute;es structur&eacute;es). Le reste de cette documentation explique comment.",
  "wyg_h": "Ce que vous obtenez",
  "wyg_p": "Chaque dossier correspond &agrave; une institution ou un organe de l'UE. Les compteurs sont exacts et &eacute;voluent &agrave; mesure que l'API grandit.",
  "folder_one": "dossier", "folder_many": "dossiers",
  "sections": {
    "legislation":"L&eacute;gislation","parliament":"Parlement europ&eacute;en","council":"Conseil et sommets",
    "commission":"Commission europ&eacute;enne","economic":"&Eacute;conomie et finance","agencies":"Agences de l'UE",
    "funding":"Financements et consultations","opendata":"Donn&eacute;es ouvertes et personnes","proprietary":"Intelligence propri&eacute;taire",
  },
  "ds_h":"Sources de donn&eacute;es et fr&eacute;quence de mise &agrave; jour",
  "ds_p":"Toute la surface v2 est resynchronis&eacute;e quotidiennement (un balayage &agrave; 10h00 / 15h00 / 21h00 UTC). Les sources de l'UE derri&egrave;re chaque dossier sont mises &agrave; jour aux fr&eacute;quences ci-dessous.",
  "ds_th":["Fr&eacute;quence de mise &agrave; jour","Ce que &ccedil;a couvre"],
  "auth_h":"L'authentification en un coup d'&oelig;il",
  "auth_p":"Chaque appel &agrave; <code>/api/v2/*</code> exige une cl&eacute; d'API envoy&eacute;e en token Bearer ou en en-t&ecirc;te <code>X-API-Key</code> :",
  "auth_full":"D&eacute;tails complets dans <a href=\"/api/docs/authentication.html\">Authentification</a>.",
  "env_h":"L'enveloppe de r&eacute;ponse en un coup d'&oelig;il",
  "env_p":"Chaque endpoint pagin&eacute; renvoie la m&ecirc;me forme. Programmez une fois contre cette enveloppe et changez de jeu de donn&eacute;es en changeant le chemin :",
  "env_hdr_p":"La provenance et les informations de limite de d&eacute;bit vivent dans les en-t&ecirc;tes de r&eacute;ponse, pas dans le corps :",
  "env_full":"D&eacute;tails complets dans <a href=\"/api/docs/envelope.html\">Enveloppe de r&eacute;ponse</a>.",
  "qs_h":"D&eacute;marrage rapide : votre premier appel",
  "qs1":"<strong>1. Obtenez une cl&eacute; d'API.</strong> &Eacute;crivez &agrave; <a href=\"mailto:hello@beresol.eu\">hello@beresol.eu</a> une fois l'abonnement Professional souscrit. Les cl&eacute;s ont la forme <code>brubru_live_</code> suivi de 48 caract&egrave;res hexad&eacute;cimaux.",
  "qs2":"<strong>2. V&eacute;rifiez que le service r&eacute;pond.</strong> Le contr&ocirc;le de sant&eacute; est public &mdash; aucune cl&eacute; requise :",
  "qs2resp":"R&eacute;ponse :",
  "qs3":"<strong>3. Essayez une vraie recherche.</strong>",
  "qs3_after":"Vous obtenez une liste pagin&eacute;e d'actes de l'UE correspondant &agrave; \"artificial intelligence\", avec identifiants CELEX, titres, dates et URL EUR-Lex. &Agrave; partir de l&agrave;, chaque endpoint suit le m&ecirc;me mod&egrave;le d'enveloppe &mdash; changez simplement le chemin.",
  "lim_h":"Limites (ce que nous ne couvrons pas)",
  "lim":[
    "<strong>L&eacute;gislation non europ&eacute;enne.</strong> Nous ne suivons pas directement les journaux officiels nationaux. Si vous avez besoin du BOE espagnol et de l'UE ensemble, associez-nous &agrave; GovClipping ou similaire.",
    "<strong>Notification en temps r&eacute;el.</strong> Pas encore de webhooks ni de SSE. L'int&eacute;gration se fait par interrogation selon notre fr&eacute;quence. Webhooks pr&eacute;vus pour septembre 2026.",
    "<strong>Langues.</strong> Les r&eacute;ponses de l'API sont en anglais aujourd'hui. Certains textes juridiques sont disponibles dans les 24 langues de l'UE via Cellar, mais les r&eacute;ponses structur&eacute;es sont en anglais uniquement. Endpoints multilingues en septembre 2026.",
    "<strong>Exports en masse.</strong> Pas encore de vidages nocturnes CSV/Parquet. Pr&eacute;vu pour septembre 2026. Pour l'instant, parcourez les listes pagin&eacute;es.",
    "<strong>Parlements nationaux.</strong> Nous n'ing&eacute;rons pas les parlements <em>nationaux</em>. PE uniquement.",
  ],
  "next_h":"O&ugrave; aller ensuite",
  "next":[
    ("/api/docs/endpoints.html","Tous les endpoints","La liste compl&egrave;te et regroup&eacute;e des 469 endpoints v2, une section par dossier d'institution."),
    ("/api/docs/authentication.html","Authentification","Comment envoyer votre cl&eacute; d'API, cycle de vie, rotation, s&eacute;curit&eacute;."),
    ("/api/docs/use-cases.html","Cas d'usage par profil","Consultants en affaires publiques, associations, entreprises, ONG, fonctionnaires de l'UE &mdash; ce que vous appelleriez vraiment."),
    ("/api/docs/glossary.html","Glossaire","CELEX, OEIL, trilogue, rapporteur, types de commission, directive contre r&egrave;glement &mdash; chaque sigle expliqu&eacute;."),
  ],
  "footer":"&copy; 2026 Beresol BV &mdash; Brubru EU Data API v2.",
  "footer_back":"Retour &agrave; la page marketing",
}

# ---------------------------------------------------------------- ITALIAN ----
LANGS["it"] = {
  "lang": "it", "sep_opt": "it.html",
  "title": "Introduzione &mdash; Brubru EU Data API",
  "desc": "Brubru EU Data API v2: 469 endpoint REST in 34 cartelle di istituzioni dell'UE. 8.710 atti dell'UE, procedure legislative, deputati e funzionari, emendamenti, le banche dati di Parlamento / Consiglio / Commissione, le banche dati delle agenzie dell'UE (medicinali, sicurezza alimentare, ambiente, sostanze chimiche, droghe, diritti fondamentali), finanziamenti, dati aperti e l'intelligence propria di Brubru sull'UE. Una sola chiave API.",
  "pw_text": "Stai consultando il riferimento. Per eseguire chiamate reali ti serve una chiave API Brubru &mdash; ",
  "pw_trial": "Avvia una prova Professional",
  "pw_or": " &middot; oppure ",
  "pw_sales": "contatta le vendite",
  "eyebrow": "Brubru EU Data API &middot; v2 &middot; 469 endpoint in 34 cartelle di istituzioni dell'UE",
  "h1": "L'UE, strutturata.",
  "lede": "Brubru &egrave; un fornitore verticale di dati dell'UE. La nostra API REST offre a sviluppatori, piattaforme RegTech, team di affari pubblici e agenti di IA accesso programmatico a <strong>8.710 atti dell'UE adottati</strong> (28.513 pubblicazioni della GU), <strong>2.080 fascicoli legislativi</strong> monitorati, <strong>16.521 funzionari dell'UE</strong>, tutti i deputati, <strong>58.399 emendamenti del PE</strong>, i registri di Parlamento / Consiglio / Consiglio europeo / Eurogruppo / Commissione, la Banca centrale europea e le istituzioni finanziarie dell'UE, le agenzie decentrate dell'UE (medicinali, sicurezza alimentare, ambiente, sostanze chimiche, droghe, diritti fondamentali e altro), finanziamenti e gare dell'UE, dati aperti e l'intelligence propria di Brubru sull'UE. Gli stessi dati che usiamo internamente sono quelli che chiami. Brubru &egrave; il primo cliente della propria API.",
  "box": "<strong>Una superficie, una chiave.</strong> L'API &egrave; organizzata come l'UE stessa &mdash; una cartella per istituzione od organo, 34 cartelle in totale, <strong>469 endpoint</strong>. Sfoglia le cartelle qui sotto, oppure apri il <a href=\"/api/docs/reference.html\"><strong>riferimento API completo e sempre aggiornato &rarr;</strong></a> &mdash; ogni endpoint distribuito, generato in tempo reale dalla specifica OpenAPI.",
  "callout_q": "Nuovo alle API?",
  "callout_b": " Un'API &egrave; un modo per far dialogare il tuo software con quello di Brubru via internet. Tu invii una richiesta HTTP (come fa un browser) e noi restituiamo JSON (dati strutturati). Il resto di questa documentazione spiega come.",
  "wyg_h": "Cosa ottieni",
  "wyg_p": "Ogni cartella corrisponde a un'istituzione o un organo dell'UE. I conteggi sono esatti e si aggiornano man mano che l'API cresce.",
  "folder_one": "cartella", "folder_many": "cartelle",
  "sections": {
    "legislation":"Legislazione","parliament":"Parlamento europeo","council":"Consiglio e vertici",
    "commission":"Commissione europea","economic":"Economia e finanza","agencies":"Agenzie dell'UE",
    "funding":"Finanziamenti e consultazioni","opendata":"Dati aperti e persone","proprietary":"Intelligence proprietaria",
  },
  "ds_h":"Fonti dei dati e frequenza di aggiornamento",
  "ds_p":"L'intera superficie v2 viene risincronizzata ogni giorno (una scansione alle 10:00 / 15:00 / 21:00 UTC). Le fonti dell'UE dietro ogni cartella si aggiornano con le frequenze seguenti.",
  "ds_th":["Frequenza di aggiornamento","Cosa copre"],
  "auth_h":"L'autenticazione in breve",
  "auth_p":"Ogni chiamata a <code>/api/v2/*</code> richiede una chiave API inviata come token Bearer o come intestazione <code>X-API-Key</code>:",
  "auth_full":"Dettagli completi su <a href=\"/api/docs/authentication.html\">Autenticazione</a>.",
  "env_h":"La busta di risposta in breve",
  "env_p":"Ogni endpoint paginato restituisce la stessa forma. Programma una volta sola contro questa busta e cambia set di dati cambiando il percorso:",
  "env_hdr_p":"La provenienza e le informazioni sul limite di frequenza vivono nelle intestazioni di risposta, non nel corpo:",
  "env_full":"Dettagli completi su <a href=\"/api/docs/envelope.html\">Busta di risposta</a>.",
  "qs_h":"Avvio rapido: la tua prima chiamata",
  "qs1":"<strong>1. Ottieni una chiave API.</strong> Scrivi a <a href=\"mailto:hello@beresol.eu\">hello@beresol.eu</a> una volta attivato l'abbonamento Professional. Le chiavi hanno la forma <code>brubru_live_</code> seguito da 48 caratteri esadecimali.",
  "qs2":"<strong>2. Verifica che il servizio sia attivo.</strong> Il controllo di stato &egrave; pubblico &mdash; non serve la chiave:",
  "qs2resp":"Risposta:",
  "qs3":"<strong>3. Prova una ricerca reale.</strong>",
  "qs3_after":"Ottieni un elenco paginato di atti dell'UE corrispondenti a \"artificial intelligence\", con identificatori CELEX, titoli, date e URL di EUR-Lex. Da l&igrave; ogni endpoint segue lo stesso schema di busta &mdash; basta cambiare il percorso.",
  "lim_h":"Limiti (cosa non copriamo)",
  "lim":[
    "<strong>Legislazione extra-UE.</strong> Non seguiamo direttamente le gazzette nazionali. Se ti serve il BOE spagnolo insieme all'UE, abbinaci a GovClipping o simili.",
    "<strong>Notifica in tempo reale.</strong> Ancora nessun webhook n&eacute; SSE. Il modello di integrazione &egrave; il polling secondo la nostra frequenza. Webhook nella roadmap di settembre 2026.",
    "<strong>Lingue.</strong> Le risposte dell'API sono oggi in inglese. Alcuni testi giuridici sono disponibili in tutte le 24 lingue dell'UE tramite Cellar, ma le risposte strutturate sono solo in inglese. Endpoint multilingue a settembre 2026.",
    "<strong>Esportazioni di massa.</strong> Ancora nessun dump notturno CSV/Parquet. Roadmap settembre 2026. Per ora, scorri gli elenchi paginati.",
    "<strong>Parlamenti nazionali.</strong> Non acquisiamo dai parlamenti <em>nazionali</em>. Solo il PE.",
  ],
  "next_h":"Dove andare dopo",
  "next":[
    ("/api/docs/endpoints.html","Tutti gli endpoint","L'elenco completo e raggruppato di tutti i 469 endpoint v2, una sezione per cartella di istituzione."),
    ("/api/docs/authentication.html","Autenticazione","Come inviare la chiave API, ciclo di vita, rotazione, sicurezza."),
    ("/api/docs/use-cases.html","Casi d'uso per ruolo","Consulenti di affari pubblici, associazioni, aziende, ONG, funzionari dell'UE &mdash; cosa chiameresti davvero."),
    ("/api/docs/glossary.html","Glossario","CELEX, OEIL, trilogo, relatore, tipi di commissione, direttiva contro regolamento &mdash; ogni sigla spiegata."),
  ],
  "footer":"&copy; 2026 Beresol BV &mdash; Brubru EU Data API v2.",
  "footer_back":"Torna alla pagina di marketing",
}

# ---------------------------------------------------------------- DUTCH ------
LANGS["nl"] = {
  "lang": "nl", "sep_opt": "nl.html",
  "title": "Inleiding &mdash; Brubru EU Data API",
  "desc": "Brubru EU Data API v2: 469 REST-endpoints in 34 mappen van EU-instellingen. 8.710 EU-wetten, wetgevingsprocedures, Europarlementari&euml;rs en ambtenaren, amendementen, de databanken van Parlement / Raad / Commissie, de databanken van de EU-agentschappen (geneesmiddelen, voedselveiligheid, milieu, chemische stoffen, drugs, grondrechten), financiering, open data en Brubru's eigen EU-intelligentie. E&eacute;n API-sleutel.",
  "pw_text": "U bekijkt de referentie. Om echte calls uit te voeren hebt u een Brubru API-sleutel nodig &mdash; ",
  "pw_trial": "Start een Professional-proef",
  "pw_or": " &middot; of ",
  "pw_sales": "neem contact op met sales",
  "eyebrow": "Brubru EU Data API &middot; v2 &middot; 469 endpoints in 34 mappen van EU-instellingen",
  "h1": "De EU, gestructureerd.",
  "lede": "Brubru is een verticale EU-dataleverancier. Onze REST-API geeft ontwikkelaars, RegTech-platforms, public-affairsteams en AI-agents programmatische toegang tot <strong>8.710 vastgestelde EU-wetten</strong> (28.513 PB-publicaties), <strong>2.080 gevolgde wetgevingsdossiers</strong>, <strong>16.521 EU-ambtenaren</strong>, alle Europarlementari&euml;rs, <strong>58.399 EP-amendementen</strong>, de registers van Parlement / Raad / Europese Raad / Eurogroep / Commissie, de Europese Centrale Bank en de financi&euml;le instellingen van de EU, de gedecentraliseerde EU-agentschappen (geneesmiddelen, voedselveiligheid, milieu, chemische stoffen, drugs, grondrechten en meer), EU-financiering en aanbestedingen, open data en Brubru's eigen EU-intelligentie. Dezelfde data die wij intern gebruiken, roept u aan. Brubru is de eerste klant van zijn eigen API.",
  "box": "<strong>E&eacute;n oppervlak, &eacute;&eacute;n sleutel.</strong> De API is ingedeeld zoals de EU zelf &mdash; &eacute;&eacute;n map per instelling of orgaan, 34 mappen in totaal, <strong>469 endpoints</strong>. Blader hieronder door de mappen of open de <a href=\"/api/docs/reference.html\"><strong>volledige, altijd actuele API-referentie &rarr;</strong></a> &mdash; elk uitgerold endpoint, live gegenereerd uit de OpenAPI-specificatie.",
  "callout_q": "Nieuw met API's?",
  "callout_b": " Een API is een manier voor uw software om via internet met de software van Brubru te praten. U stuurt een HTTP-verzoek (zoals een browser doet) en wij sturen JSON terug (gestructureerde data). De rest van deze documentatie legt uit hoe.",
  "wyg_h": "Wat u krijgt",
  "wyg_p": "Elke map komt overeen met &eacute;&eacute;n EU-instelling of -orgaan. De aantallen zijn exact en worden bijgewerkt naarmate de API groeit.",
  "folder_one": "map", "folder_many": "mappen",
  "sections": {
    "legislation":"Wetgeving","parliament":"Europees Parlement","council":"Raad en toppen",
    "commission":"Europese Commissie","economic":"Economie en financi&euml;n","agencies":"EU-agentschappen",
    "funding":"Financiering en consultaties","opendata":"Open data en personen","proprietary":"Eigen intelligentie",
  },
  "ds_h":"Gegevensbronnen en verversingsfrequentie",
  "ds_p":"De volledige v2-oppervlakte wordt dagelijks opnieuw gesynchroniseerd (een sweep om 10:00 / 15:00 / 21:00 UTC). De EU-bronnen achter elke map verversen met onderstaande frequenties.",
  "ds_th":["Verversingsfrequentie","Wat het dekt"],
  "auth_h":"Authenticatie in een oogopslag",
  "auth_p":"Elke call naar <code>/api/v2/*</code> vereist een API-sleutel, verstuurd als Bearer-token of als <code>X-API-Key</code>-header:",
  "auth_full":"Volledige details op <a href=\"/api/docs/authentication.html\">Authenticatie</a>.",
  "env_h":"De response-envelop in een oogopslag",
  "env_p":"Elk gepagineerd endpoint geeft dezelfde vorm terug. Programmeer &eacute;&eacute;n keer tegen deze envelop en wissel van dataset door het pad te wijzigen:",
  "env_hdr_p":"Herkomst en rate-limit-informatie staan in de response-headers, niet in de body:",
  "env_full":"Volledige details op <a href=\"/api/docs/envelope.html\">Response-envelop</a>.",
  "qs_h":"Snelstart: uw eerste call",
  "qs1":"<strong>1. Vraag een API-sleutel aan.</strong> Mail <a href=\"mailto:hello@beresol.eu\">hello@beresol.eu</a> zodra u het Professional-abonnement hebt. Sleutels zien eruit als <code>brubru_live_</code> gevolgd door 48 hexadecimale tekens.",
  "qs2":"<strong>2. Controleer of de service draait.</strong> De health-check is openbaar &mdash; geen sleutel nodig:",
  "qs2resp":"Antwoord:",
  "qs3":"<strong>3. Probeer een echte zoekopdracht.</strong>",
  "qs3_after":"U krijgt een gepagineerde lijst van EU-wetten die overeenkomen met \"artificial intelligence\", met CELEX-identificatoren, titels, datums en EUR-Lex-URL's. Vanaf daar volgt elk endpoint hetzelfde envelop-patroon &mdash; wijzig alleen het pad.",
  "lim_h":"Beperkingen (wat we niet dekken)",
  "lim":[
    "<strong>Niet-EU-wetgeving.</strong> We volgen nationale staatsbladen niet rechtstreeks. Hebt u het Spaanse BOE samen met de EU nodig, combineer ons dan met GovClipping of vergelijkbaar.",
    "<strong>Realtime push.</strong> Nog geen webhooks of SSE. Het integratiepatroon is polling volgens onze frequentie. Webhooks op de roadmap voor september 2026.",
    "<strong>Talen.</strong> API-antwoorden zijn vandaag in het Engels. Sommige wetteksten zijn beschikbaar in alle 24 EU-talen via Cellar, maar de gestructureerde antwoorden zijn alleen in het Engels. Meertalige endpoints in september 2026.",
    "<strong>Bulkexports.</strong> Nog geen nachtelijke CSV/Parquet-dumps. Roadmap september 2026. Doorloop voorlopig de gepagineerde lijsten.",
    "<strong>Nationale parlementen.</strong> We nemen geen data op van <em>nationale</em> parlementen. Alleen het EP.",
  ],
  "next_h":"Waar nu naartoe",
  "next":[
    ("/api/docs/endpoints.html","Alle endpoints","De volledige, gegroepeerde lijst van alle 469 v2-endpoints, &eacute;&eacute;n sectie per instellingsmap."),
    ("/api/docs/authentication.html","Authenticatie","Hoe u uw API-sleutel verstuurt, levenscyclus, rotatie, beveiliging."),
    ("/api/docs/use-cases.html","Use cases per rol","Public-affairsconsultants, verenigingen, bedrijven, ngo's, EU-ambtenaren &mdash; wat u echt zou aanroepen."),
    ("/api/docs/glossary.html","Woordenlijst","CELEX, OEIL, triloog, rapporteur, soorten commissies, richtlijn versus verordening &mdash; elke afkorting uitgelegd."),
  ],
  "footer":"&copy; 2026 Beresol BV &mdash; Brubru EU Data API v2.",
  "footer_back":"Terug naar de marketingpagina",
}

# ---------------------------------------------------------------- CATALAN ----
LANGS["ca"] = {
  "lang": "ca", "sep_opt": "ca.html",
  "title": "Introducci&oacute; &mdash; Brubru EU Data API",
  "desc": "Brubru EU Data API v2: 469 endpoints REST en 34 carpetes d'institucions de la UE. 8.710 lleis de la UE, procediments legislatius, eurodiputats i funcionaris, esmenes, les bases de dades del Parlament / Consell / Comissi&oacute;, les bases de dades de les ag&egrave;ncies de la UE (medicaments, seguretat aliment&agrave;ria, medi ambient, subst&agrave;ncies qu&iacute;miques, drogues, drets fonamentals), finan&ccedil;ament, dades obertes i la intel&middot;lig&egrave;ncia pr&ograve;pia de Brubru sobre la UE. Una sola clau d'API.",
  "pw_text": "Esteu veient la refer&egrave;ncia. Per executar crides reals necessiteu una clau d'API de Brubru &mdash; ",
  "pw_trial": "Inicieu una prova Professional",
  "pw_or": " &middot; o ",
  "pw_sales": "contacteu amb vendes",
  "eyebrow": "Brubru EU Data API &middot; v2 &middot; 469 endpoints en 34 carpetes d'institucions de la UE",
  "h1": "La UE, estructurada.",
  "lede": "Brubru &eacute;s un prove&iuml;dor vertical de dades de la UE. La nostra API REST dona a desenvolupadors, plataformes RegTech, equips d'afers p&uacute;blics i agents d'IA acc&eacute;s program&agrave;tic a <strong>8.710 lleis de la UE adoptades</strong> (28.513 publicacions del DO), <strong>2.080 expedients legislatius</strong> en seguiment, <strong>16.521 funcionaris de la UE</strong>, tots els eurodiputats, <strong>58.399 esmenes del PE</strong>, els registres del Parlament / Consell / Consell Europeu / Eurogrup / Comissi&oacute;, el Banc Central Europeu i les institucions financeres de la UE, les ag&egrave;ncies descentralitzades de la UE (medicaments, seguretat aliment&agrave;ria, medi ambient, subst&agrave;ncies qu&iacute;miques, drogues, drets fonamentals i m&eacute;s), finan&ccedil;ament i licitacions de la UE, dades obertes i la intel&middot;lig&egrave;ncia pr&ograve;pia de Brubru sobre la UE. Les mateixes dades que fem servir internament s&oacute;n les que crideu. Brubru &eacute;s el primer client de la seva pr&ograve;pia API.",
  "box": "<strong>Una superf&iacute;cie, una clau.</strong> L'API est&agrave; organitzada com la mateixa UE &mdash; una carpeta per instituci&oacute; o organisme, 34 carpetes en total, <strong>469 endpoints</strong>. Exploreu les carpetes a continuaci&oacute;, o obriu la <a href=\"/api/docs/reference.html\"><strong>refer&egrave;ncia completa i sempre actualitzada de l'API &rarr;</strong></a> &mdash; cada endpoint desplegat, generat en directe des de l'especificaci&oacute; OpenAPI.",
  "callout_q": "Nou en les API?",
  "callout_b": " Una API &eacute;s una manera que el vostre programari parli amb el programari de Brubru per internet. Envieu una petici&oacute; HTTP (com fa un navegador) i us retornem JSON (dades estructurades). La resta d'aquesta documentaci&oacute; explica com.",
  "wyg_h": "Qu&egrave; obteniu",
  "wyg_p": "Cada carpeta correspon a una instituci&oacute; o organisme de la UE. Les xifres s&oacute;n exactes i s'actualitzen a mesura que creix l'API.",
  "folder_one": "carpeta", "folder_many": "carpetes",
  "sections": {
    "legislation":"Legislaci&oacute;","parliament":"Parlament Europeu","council":"Consell i cimeres",
    "commission":"Comissi&oacute; Europea","economic":"Economia i finances","agencies":"Ag&egrave;ncies de la UE",
    "funding":"Finan&ccedil;ament i consultes","opendata":"Dades obertes i persones","proprietary":"Intel&middot;lig&egrave;ncia pr&ograve;pia",
  },
  "ds_h":"Fonts de dades i freq&uuml;&egrave;ncia d'actualitzaci&oacute;",
  "ds_p":"Tota la superf&iacute;cie v2 es resincronitza di&agrave;riament (un escombrat a les 10:00 / 15:00 / 21:00 UTC). Les fonts de la UE darrere de cada carpeta s'actualitzen amb les freq&uuml;&egrave;ncies seg&uuml;ents.",
  "ds_th":["Freq&uuml;&egrave;ncia d'actualitzaci&oacute;","Qu&egrave; cobreix"],
  "auth_h":"L'autenticaci&oacute; d'un cop d'ull",
  "auth_p":"Cada crida a <code>/api/v2/*</code> requereix una clau d'API enviada com a token Bearer o com a cap&ccedil;alera <code>X-API-Key</code>:",
  "auth_full":"Detalls complets a <a href=\"/api/docs/authentication.html\">Autenticaci&oacute;</a>.",
  "env_h":"El sobre de resposta d'un cop d'ull",
  "env_p":"Cada endpoint paginat retorna la mateixa forma. Programeu un sol cop contra aquest sobre i canvieu de conjunt de dades canviant la ruta:",
  "env_hdr_p":"La proced&egrave;ncia i la informaci&oacute; del l&iacute;mit de crides viuen a les cap&ccedil;aleres de resposta, no al cos:",
  "env_full":"Detalls complets a <a href=\"/api/docs/envelope.html\">Sobre de resposta</a>.",
  "qs_h":"Inici r&agrave;pid: la vostra primera crida",
  "qs1":"<strong>1. Aconseguiu una clau d'API.</strong> Escriviu a <a href=\"mailto:hello@beresol.eu\">hello@beresol.eu</a> quan tingueu la subscripci&oacute; Professional. Les claus tenen la forma <code>brubru_live_</code> seguit de 48 car&agrave;cters hexadecimals.",
  "qs2":"<strong>2. Comproveu que el servei funciona.</strong> La comprovaci&oacute; d'estat &eacute;s p&uacute;blica &mdash; no cal clau:",
  "qs2resp":"Resposta:",
  "qs3":"<strong>3. Proveu una cerca real.</strong>",
  "qs3_after":"Obteniu una llista paginada de lleis de la UE que coincideixen amb \"artificial intelligence\", amb identificadors CELEX, t&iacute;tols, dates i URL d'EUR-Lex. A partir d'aqu&iacute;, cada endpoint segueix el mateix patr&oacute; de sobre &mdash; nom&eacute;s cal canviar la ruta.",
  "lim_h":"Limitacions (qu&egrave; no cobrim)",
  "lim":[
    "<strong>Legislaci&oacute; no comunit&agrave;ria.</strong> No seguim els butlletins nacionals directament. Si necessiteu el BOE espanyol juntament amb la UE, combineu-nos amb GovClipping o similar.",
    "<strong>Notificaci&oacute; en temps real.</strong> Encara no hi ha webhooks ni SSE. El patr&oacute; d'integraci&oacute; &eacute;s el sondeig segons la nostra freq&uuml;&egrave;ncia. Webhooks al full de ruta de setembre de 2026.",
    "<strong>Lleng&uuml;es.</strong> Les respostes de l'API s&oacute;n avui en angl&egrave;s. Alguns textos legals estan disponibles en les 24 lleng&uuml;es de la UE via Cellar, per&ograve; les respostes estructurades s&oacute;n nom&eacute;s en angl&egrave;s. Endpoints multiling&uuml;es al setembre de 2026.",
    "<strong>Exportacions massives.</strong> Encara no hi ha bolcats nocturns CSV/Parquet. Full de ruta setembre de 2026. De moment, recorreu les llistes paginades.",
    "<strong>Parlaments nacionals.</strong> No ingerim dels parlaments <em>nacionals</em>. Nom&eacute;s el PE.",
  ],
  "next_h":"On anar despr&eacute;s",
  "next":[
    ("/api/docs/endpoints.html","Tots els endpoints","La llista completa i agrupada dels 469 endpoints de v2, una secci&oacute; per carpeta d'instituci&oacute;."),
    ("/api/docs/authentication.html","Autenticaci&oacute;","Com enviar la vostra clau d'API, cicle de vida, rotaci&oacute; i seguretat."),
    ("/api/docs/use-cases.html","Casos d'&uacute;s per perfil","Consultors d'afers p&uacute;blics, associacions, empreses, ONG, funcionaris de la UE &mdash; qu&egrave; cridar&iacute;eu realment."),
    ("/api/docs/glossary.html","Glossari","CELEX, OEIL, tr&iacute;leg, ponent, tipus de comissi&oacute;, directiva contra reglament &mdash; cada sigla explicada."),
  ],
  "footer":"&copy; 2026 Beresol BV &mdash; Brubru EU Data API v2.",
  "footer_back":"Torna a la p&agrave;gina de m&agrave;rqueting",
}

# Endpoint counts per folder (for nav labels), from the live OpenAPI spec.
COUNT = {"legislative":37,"parliament":38,"council":21,"european-council":12,"eurogroup":10,
 "commission":40,"ecb":17,"eu-financial-institutions":51,"esm":9,"funding":62,"consultations":11,
 "open-data":5,"general-publications":2,"who-is-who":4,"geographical-indications":6,"proprietary":10,
 "ema":27}

# Agency display acronyms (language-independent card titles + nav labels).
AGENCY = {"acer":"ACER","berec":"BEREC","cedefop":"Cedefop","cpvo":"CPVO","ecdc":"ECDC","echa":"ECHA",
 "eea":"EEA","efsa":"EFSA","eige":"EIGE","eit":"EIT","ema":"EMA","enisa":"ENISA","eu-lisa":"eu-LISA",
 "eu-osha":"EU-OSHA","euaa":"EUAA","euda":"EUDA","euipo":"EUIPO","fra":"FRA"}
AGENCY_SLUGS = set(AGENCY)

# Non-agency card titles per language (slug -> {lang: title}).
TITLE = {
 "legislative":{"es":"Legislaci&oacute;n y procedimientos","fr":"L&eacute;gislation et proc&eacute;dures","it":"Legislazione e procedure","nl":"Wetgeving en procedures","ca":"Legislaci&oacute; i procediments"},
 "council":{"es":"Consejo de la UE","fr":"Conseil de l'UE","it":"Consiglio dell'UE","nl":"Raad van de EU","ca":"Consell de la UE"},
 "european-council":{"es":"Consejo Europeo","fr":"Conseil europ&eacute;en","it":"Consiglio europeo","nl":"Europese Raad","ca":"Consell Europeu"},
 "eurogroup":{"es":"Eurogrupo","fr":"Eurogroupe","it":"Eurogruppo","nl":"Eurogroep","ca":"Eurogrup"},
 "commission":{"es":"Comisi&oacute;n Europea","fr":"Commission europ&eacute;enne","it":"Commissione europea","nl":"Europese Commissie","ca":"Comissi&oacute; Europea"},
 "parliament":{"es":"Parlamento Europeo","fr":"Parlement europ&eacute;en","it":"Parlamento europeo","nl":"Europees Parlement","ca":"Parlament Europeu"},
 "ecb":{"es":"Banco Central Europeo","fr":"Banque centrale europ&eacute;enne","it":"Banca centrale europea","nl":"Europese Centrale Bank","ca":"Banc Central Europeu"},
 "eu-financial-institutions":{"es":"Instituciones financieras de la UE","fr":"Institutions financi&egrave;res de l'UE","it":"Istituzioni finanziarie dell'UE","nl":"Financi&euml;le instellingen van de EU","ca":"Institucions financeres de la UE"},
 "esm":{"es":"Mecanismo Europeo de Estabilidad","fr":"M&eacute;canisme europ&eacute;en de stabilit&eacute;","it":"Meccanismo europeo di stabilit&agrave;","nl":"Europees Stabiliteitsmechanisme","ca":"Mecanisme Europeu d'Estabilitat"},
 "funding":{"es":"Financiaci&oacute;n, subvenciones y licitaciones","fr":"Financements, subventions et appels d'offres","it":"Finanziamenti, sovvenzioni e gare","nl":"Financiering, subsidies en aanbestedingen","ca":"Finan&ccedil;ament, subvencions i licitacions"},
 "consultations":{"es":"Consultas de agencias","fr":"Consultations des agences","it":"Consultazioni delle agenzie","nl":"Consultaties van agentschappen","ca":"Consultes d'ag&egrave;ncies"},
 "open-data":{"es":"Datos abiertos","fr":"Donn&eacute;es ouvertes","it":"Dati aperti","nl":"Open data","ca":"Dades obertes"},
 "general-publications":{"es":"Publicaciones generales","fr":"Publications g&eacute;n&eacute;rales","it":"Pubblicazioni generali","nl":"Algemene publicaties","ca":"Publicacions generals"},
 "who-is-who":{"es":"Qui&eacute;n es qui&eacute;n","fr":"Qui est qui","it":"Chi &egrave; chi","nl":"Wie is wie","ca":"Qui &eacute;s qui"},
 "geographical-indications":{"es":"Indicaciones geogr&aacute;ficas","fr":"Indications g&eacute;ographiques","it":"Indicazioni geografiche","nl":"Geografische aanduidingen","ca":"Indicacions geogr&agrave;fiques"},
 "proprietary":{"es":"Inteligencia propia de Brubru","fr":"Intelligence propri&eacute;taire Brubru","it":"Intelligence proprietaria Brubru","nl":"Brubru EU-intelligentie","ca":"Intel&middot;lig&egrave;ncia pr&ograve;pia de Brubru"},
}

# Card descriptions per slug per language.
DESC = {
 "legislative":{
  "es":"8.710 leyes adoptadas (28.513 publicaciones del DO) y 2.080 expedientes legislativos en seguimiento, m&aacute;s actos delegados y de ejecuci&oacute;n, texto completo + XML, mapas de considerandos a art&iacute;culos, t&eacute;rminos definidos, EuroVoc, el Tren Legislativo y los resolvedores de citas y alias.",
  "fr":"8 710 actes adopt&eacute;s (28 513 publications du JO) et 2 080 dossiers l&eacute;gislatifs suivis, plus les actes d&eacute;l&eacute;gu&eacute;s et d'ex&eacute;cution, le texte int&eacute;gral + XML, les correspondances consid&eacute;rants-articles, les termes d&eacute;finis, EuroVoc, le Train l&eacute;gislatif et les r&eacute;solveurs de citations et d'alias.",
  "it":"8.710 atti adottati (28.513 pubblicazioni della GU) e 2.080 fascicoli legislativi monitorati, pi&ugrave; atti delegati e di esecuzione, testo integrale + XML, mappe considerando-articolo, termini definiti, EuroVoc, il Treno legislativo e i resolver di citazioni e alias.",
  "nl":"8.710 vastgestelde wetten (28.513 PB-publicaties) en 2.080 gevolgde wetgevingsdossiers, plus gedelegeerde en uitvoeringshandelingen, volledige tekst + XML, overweging-naar-artikel-kaarten, gedefinieerde termen, EuroVoc, de Wetgevingstrein en de citatie- en alias-resolvers.",
  "ca":"8.710 lleis adoptades (28.513 publicacions del DO) i 2.080 expedients legislatius en seguiment, m&eacute;s actes delegats i d'execuci&oacute;, text complet + XML, mapes de consideracions a articles, termes definits, EuroVoc, el Tren Legislatiu i els resoluts de cites i &agrave;lies.",
 },
 "parliament":{
  "es":"Eurodiputados, trabajo en comisi&oacute;n, enmiendas, informes, opiniones, resoluciones, textos aprobados y presentados, votaciones nominales, preguntas parlamentarias, documentos de eMeeting, retransmisiones web + transcripciones de IA, investigaci&oacute;n EPRS y declaraciones y asistentes de los eurodiputados.",
  "fr":"D&eacute;put&eacute;s, travaux en commission, amendements, rapports, avis, r&eacute;solutions, textes adopt&eacute;s et d&eacute;pos&eacute;s, votes par appel nominal, questions parlementaires, documents eMeeting, webstreams + transcriptions IA, recherche EPRS, et d&eacute;clarations et assistants des d&eacute;put&eacute;s.",
  "it":"Deputati, lavori in commissione, emendamenti, relazioni, pareri, risoluzioni, testi approvati e presentati, voti per appello nominale, interrogazioni parlamentari, documenti eMeeting, webstream + trascrizioni IA, ricerca EPRS e dichiarazioni e assistenti dei deputati.",
  "nl":"Europarlementari&euml;rs, commissiewerk, amendementen, verslagen, adviezen, resoluties, aangenomen en ingediende teksten, hoofdelijke stemmingen, parlementaire vragen, eMeeting-documenten, webstreams + AI-transcripties, EPRS-onderzoek, en verklaringen en medewerkers van leden.",
  "ca":"Eurodiputats, treball en comissi&oacute;, esmenes, informes, opinions, resolucions, textos aprovats i presentats, votacions nominals, preguntes parlament&agrave;ries, documents d'eMeeting, retransmissions web + transcripcions d'IA, recerca EPRS i declaracions i assistents dels eurodiputats.",
 },
 "council":{
  "es":"Documentos, reuniones, notas de prensa, conclusiones, resultados de votaciones, &oacute;rganos preparatorios, el registro p&uacute;blico, los reg&iacute;menes de sanciones y las 10 formaciones ministeriales.",
  "fr":"Documents, r&eacute;unions, communiqu&eacute;s, conclusions, r&eacute;sultats de votes, organes pr&eacute;paratoires, le registre public, les r&eacute;gimes de sanctions et les 10 formations minist&eacute;rielles.",
  "it":"Documenti, riunioni, comunicati stampa, conclusioni, risultati delle votazioni, organi preparatori, il registro pubblico, i regimi sanzionatori e le 10 formazioni ministeriali.",
  "nl":"Documenten, vergaderingen, persberichten, conclusies, stemresultaten, voorbereidende organen, het openbaar register, de sanctieregimes en de 10 ministeri&euml;le formaties.",
  "ca":"Documents, reunions, notes de premsa, conclusions, resultats de votacions, &ograve;rgans preparatoris, el registre p&uacute;blic, els r&egrave;gims de sancions i les 10 formacions ministerials.",
 },
 "european-council":{
  "es":"Conclusiones de las cumbres (desde 2004), reuniones, miembros, la Agenda Estrat&eacute;gica 2024-2029 y la Cumbre del Euro.",
  "fr":"Conclusions des sommets (depuis 2004), r&eacute;unions, membres, l'Agenda strat&eacute;gique 2024-2029 et le Sommet de la zone euro.",
  "it":"Conclusioni dei vertici (dal 2004), riunioni, membri, l'Agenda strategica 2024-2029 e il Vertice euro.",
  "nl":"Conclusies van de toppen (sinds 2004), vergaderingen, leden, de Strategische Agenda 2024-2029 en de Eurotop.",
  "ca":"Conclusions de les cimeres (des del 2004), reunions, membres, l'Agenda Estrat&egrave;gica 2024-2029 i la Cimera de l'Euro.",
 },
 "eurogroup":{
  "es":"Reuniones de los ministros de finanzas de la zona euro, documentos, miembros y el programa de trabajo.",
  "fr":"R&eacute;unions des ministres des finances de la zone euro, documents, membres et programme de travail.",
  "it":"Riunioni dei ministri delle finanze dell'area euro, documenti, membri e programma di lavoro.",
  "nl":"Vergaderingen van de ministers van Financi&euml;n van de eurozone, documenten, leden en het werkprogramma.",
  "ca":"Reunions dels ministres de finances de la zona euro, documents, membres i el programa de treball.",
 },
 "commission":{
  "es":"Colegio de Comisarios + agendas en vivo, documentos del Registro, reuniones de la Iniciativa de Transparencia, opiniones del RSB, infracciones, notificaciones TRIS, consultas, comitolog&iacute;a, alertas RASFF, proyectos CORDIS, ayudas estatales, casos DMA, defensa comercial, aranceles y la lista de sanciones financieras.",
  "fr":"Coll&egrave;ge des commissaires + agendas en direct, documents du Registre, r&eacute;unions de l'Initiative pour la transparence, avis du CER, infractions, notifications TRIS, consultations, comitologie, alertes RASFF, projets CORDIS, aides d'&Eacute;tat, affaires DMA, d&eacute;fense commerciale, tarifs et la liste des sanctions financi&egrave;res.",
  "it":"Collegio dei commissari + agende in tempo reale, documenti del Registro, riunioni dell'Iniziativa per la trasparenza, pareri del RSB, infrazioni, notifiche TRIS, consultazioni, comitatologia, allerte RASFF, progetti CORDIS, aiuti di Stato, casi DMA, difesa commerciale, dazi e l'elenco delle sanzioni finanziarie.",
  "nl":"College van commissarissen + live agenda's, registerdocumenten, vergaderingen van het Transparantie-initiatief, RSB-adviezen, inbreuken, TRIS-kennisgevingen, consultaties, comitologie, RASFF-waarschuwingen, CORDIS-projecten, staatssteun, DMA-zaken, handelsbescherming, tarieven en de financi&euml;le sanctielijst.",
  "ca":"Col&middot;legi de Comissaris + agendes en directe, documents del Registre, reunions de la Iniciativa de Transpar&egrave;ncia, opinions del RSB, infraccions, notificacions TRIS, consultes, comitologia, alertes RASFF, projectes CORDIS, ajuts estatals, casos DMA, defensa comercial, aranzels i la llista de sancions financeres.",
 },
 "ecb":{
  "es":"El BCE y la Supervisi&oacute;n Bancaria del BCE: noticias, eventos, publicaciones, actos jur&iacute;dicos y conjuntos de datos estad&iacute;sticos.",
  "fr":"La BCE et la supervision bancaire de la BCE : actualit&eacute;s, &eacute;v&eacute;nements, publications, actes juridiques et jeux de donn&eacute;es statistiques.",
  "it":"La BCE e la Vigilanza bancaria della BCE: notizie, eventi, pubblicazioni, atti giuridici e set di dati statistici.",
  "nl":"De ECB en het ECB-bankentoezicht: nieuws, evenementen, publicaties, rechtshandelingen en statistische datasets.",
  "ca":"El BCE i la Supervisi&oacute; Banc&agrave;ria del BCE: not&iacute;cies, esdeveniments, publicacions, actes jur&iacute;dics i conjunts de dades estad&iacute;stiques.",
 },
 "eu-financial-institutions":{
  "es":"AMLA, EBA, BEI, EIOPA, EPPO, ESMA, ESRB y la Junta &Uacute;nica de Resoluci&oacute;n, con las entidades de cr&eacute;dito de la EBA, los instrumentos financieros de ESMA y los proyectos del BEI.",
  "fr":"AMLA, ABE, BEI, EIOPA, EPPO, AEMF, CERS et le Conseil de r&eacute;solution unique, avec les &eacute;tablissements de cr&eacute;dit de l'ABE, les instruments financiers de l'AEMF et les projets de la BEI.",
  "it":"AMLA, ABE, BEI, EIOPA, EPPO, ESMA, CERS e il Comitato di risoluzione unico, con gli enti creditizi dell'ABE, gli strumenti finanziari di ESMA e i progetti della BEI.",
  "nl":"AMLA, EBA, EIB, EIOPA, EPPO, ESMA, ESRB en de Gemeenschappelijke Afwikkelingsraad, met de kredietinstellingen van de EBA, de financi&euml;le instrumenten van ESMA en de EIB-projecten.",
  "ca":"AMLA, EBA, BEI, EIOPA, EPPO, ESMA, ESRB i la Junta &Uacute;nica de Resoluci&oacute;, amb les entitats de cr&egrave;dit de l'EBA, els instruments financers d'ESMA i els projectes del BEI.",
 },
 "esm":{
  "es":"Programas, noticias, eventos y publicaciones.",
  "fr":"Programmes, actualit&eacute;s, &eacute;v&eacute;nements et publications.",
  "it":"Programmi, notizie, eventi e pubblicazioni.",
  "nl":"Programma's, nieuws, evenementen en publicaties.",
  "ca":"Programes, not&iacute;cies, esdeveniments i publicacions.",
 },
 "funding":{
  "es":"Convocatorias de propuestas (Horizon Europe, Digital Europe, LIFE, EU4Health, Erasmus+...), proyectos financiados, financiaci&oacute;n EIC para startups y pymes, licitaciones TED + Portal F&amp;T, beneficiarios de fondos y convocatorias de agencias descentralizadas.",
  "fr":"Appels &agrave; propositions (Horizon Europe, Digital Europe, LIFE, EU4Health, Erasmus+...), projets financ&eacute;s, financement EIC pour startups et PME, appels d'offres TED + portail F&amp;T, b&eacute;n&eacute;ficiaires de fonds et appels des agences d&eacute;centralis&eacute;es.",
  "it":"Inviti a presentare proposte (Horizon Europe, Digital Europe, LIFE, EU4Health, Erasmus+...), progetti finanziati, finanziamenti EIC per startup e PMI, gare TED + Portale F&amp;T, beneficiari di fondi e inviti delle agenzie decentrate.",
  "nl":"Oproepen tot voorstellen (Horizon Europe, Digital Europe, LIFE, EU4Health, Erasmus+...), gefinancierde projecten, EIC-financiering voor start-ups en mkb, TED- + F&amp;T-portaal-aanbestedingen, fondsbegunstigden en oproepen van gedecentraliseerde agentschappen.",
  "ca":"Convocat&ograve;ries de propostes (Horizon Europe, Digital Europe, LIFE, EU4Health, Erasmus+...), projectes finan&ccedil;ats, finan&ccedil;ament EIC per a startups i pimes, licitacions TED + Portal F&amp;T, beneficiaris de fons i convocat&ograve;ries d'ag&egrave;ncies descentralitzades.",
 },
 "consultations":{
  "es":"Consultas p&uacute;blicas de agencias descentralizadas: AMLA, BEREC, ECHA, EIOPA y EMA.",
  "fr":"Consultations publiques des agences d&eacute;centralis&eacute;es : AMLA, BEREC, ECHA, EIOPA et EMA.",
  "it":"Consultazioni pubbliche delle agenzie decentrate: AMLA, BEREC, ECHA, EIOPA ed EMA.",
  "nl":"Openbare consultaties van gedecentraliseerde agentschappen: AMLA, BEREC, ECHA, EIOPA en EMA.",
  "ca":"Consultes p&uacute;bliques d'ag&egrave;ncies descentralitzades: AMLA, BEREC, ECHA, EIOPA i EMA.",
 },
 "open-data":{
  "es":"Cat&aacute;logos de data.europa.eu, conjuntos de datos con enlaces de descarga directa y los Conjuntos de Datos de Alto Valor.",
  "fr":"Catalogues de data.europa.eu, jeux de donn&eacute;es avec liens de t&eacute;l&eacute;chargement direct et les Ensembles de donn&eacute;es de grande valeur.",
  "it":"Cataloghi di data.europa.eu, set di dati con link di download diretti e i Set di dati di elevato valore.",
  "nl":"Catalogi van data.europa.eu, datasets met directe downloadlinks en de Datasets met hoge waarde.",
  "ca":"Cat&agrave;legs de data.europa.eu, conjunts de dades amb enlla&ccedil;os de desc&agrave;rrega directa i els Conjunts de Dades d'Alt Valor.",
 },
 "general-publications":{
  "es":"Folletos, informes y estudios de la UE de la Oficina de Publicaciones.",
  "fr":"Brochures, rapports et &eacute;tudes de l'UE de l'Office des publications.",
  "it":"Brochure, relazioni e studi dell'UE dell'Ufficio delle pubblicazioni.",
  "nl":"Brochures, rapporten en studies van de EU van het Publicatiebureau.",
  "ca":"Fullets, informes i estudis de la UE de l'Oficina de Publicacions.",
 },
 "who-is-who":{
  "es":"Funcionarios de la UE y los departamentos organizativos de todas las instituciones (EU Who Is Who).",
  "fr":"Fonctionnaires de l'UE et les d&eacute;partements organisationnels de toutes les institutions (EU Who Is Who).",
  "it":"Funzionari dell'UE e i dipartimenti organizzativi di tutte le istituzioni (EU Who Is Who).",
  "nl":"EU-ambtenaren en de organisatorische afdelingen van alle instellingen (EU Who Is Who).",
  "ca":"Funcionaris de la UE i els departaments organitzatius de totes les institucions (EU Who Is Who).",
 },
 "geographical-indications":{
  "es":"Nombres protegidos: el registro EU de eAmbrosia, EUIPO GIview y las IG de terceros pa&iacute;ses.",
  "fr":"Noms prot&eacute;g&eacute;s : le registre UE eAmbrosia, EUIPO GIview et les IG des pays tiers.",
  "it":"Nomi protetti: il registro UE eAmbrosia, EUIPO GIview e le IG dei paesi terzi.",
  "nl":"Beschermde namen: het EU-register eAmbrosia, EUIPO GIview en de GI's van derde landen.",
  "ca":"Noms protegits: el registre UE d'eAmbrosia, EUIPO GIview i les IG de tercers pa&iuml;sos.",
 },
 "proprietary":{
  "es":"El directorio clasificado de lobbies de Bruselas, los an&aacute;lisis del EU Canon, el corpus de legislaci&oacute;n traducida al catal&aacute;n y las gu&iacute;as de conocimiento que sustentan el chatbot.",
  "fr":"L'annuaire class&eacute; des lobbies de Bruxelles, les analyses du EU Canon, le corpus de l&eacute;gislation traduite en catalan et les guides de connaissances qui alimentent le chatbot.",
  "it":"La directory classificata delle lobby di Bruxelles, gli approfondimenti del EU Canon, il corpus di legislazione tradotta in catalano e le guide di conoscenza che alimentano il chatbot.",
  "nl":"De gerangschikte directory van Brusselse lobby's, de EU Canon-analyses, het corpus van naar het Catalaans vertaalde wetgeving en de kennisgidsen die de chatbot voeden.",
  "ca":"El directori classificat de lobbies de Brussel&middot;les, les an&agrave;lisis de l'EU Canon, el corpus de legislaci&oacute; tradu&iuml;da al catal&agrave; i les guies de coneixement que sustenten el chatbot.",
 },
 # ---- agencies (title = acronym; only desc translated) ----
 "acer":{"es":"Agencia de Cooperaci&oacute;n de los Reguladores de la Energ&iacute;a: noticias y publicaciones.","fr":"Agence de coop&eacute;ration des r&eacute;gulateurs de l'&eacute;nergie : actualit&eacute;s et publications.","it":"Agenzia per la cooperazione fra i regolatori dell'energia: notizie e pubblicazioni.","nl":"Agentschap voor de samenwerking tussen energieregulators: nieuws en publicaties.","ca":"Ag&egrave;ncia de Cooperaci&oacute; dels Reguladors de l'Energia: not&iacute;cies i publicacions."},
 "berec":{"es":"Reguladores de las comunicaciones electr&oacute;nicas: noticias, eventos, publicaciones.","fr":"R&eacute;gulateurs des communications &eacute;lectroniques : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Regolatori delle comunicazioni elettroniche: notizie, eventi, pubblicazioni.","nl":"Regulators voor elektronische communicatie: nieuws, evenementen, publicaties.","ca":"Reguladors de les comunicacions electr&ograve;niques: not&iacute;cies, esdeveniments, publicacions."},
 "cedefop":{"es":"Agencia de formaci&oacute;n profesional: noticias, eventos, publicaciones.","fr":"Agence pour la formation professionnelle : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Agenzia per la formazione professionale: notizie, eventi, pubblicazioni.","nl":"Agentschap voor beroepsopleiding: nieuws, evenementen, publicaties.","ca":"Ag&egrave;ncia de formaci&oacute; professional: not&iacute;cies, esdeveniments, publicacions."},
 "cpvo":{"es":"Oficina Comunitaria de Variedades Vegetales: noticias, eventos, publicaciones.","fr":"Office communautaire des vari&eacute;t&eacute;s v&eacute;g&eacute;tales : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Ufficio comunitario delle variet&agrave; vegetali: notizie, eventi, pubblicazioni.","nl":"Communautair Bureau voor plantenrassen: nieuws, evenementen, publicaties.","ca":"Oficina Comunit&agrave;ria de Varietats Vegetals: not&iacute;cies, esdeveniments, publicacions."},
 "ecdc":{"es":"Prevenci&oacute;n y control de enfermedades: noticias, publicaciones y temas de vigilancia.","fr":"Pr&eacute;vention et contr&ocirc;le des maladies : actualit&eacute;s, publications et sujets de surveillance.","it":"Prevenzione e controllo delle malattie: notizie, pubblicazioni e temi di sorveglianza.","nl":"Ziektepreventie en -bestrijding: nieuws, publicaties en surveillancethema's.","ca":"Prevenci&oacute; i control de malalties: not&iacute;cies, publicacions i temes de vigil&agrave;ncia."},
 "echa":{"es":"Agencia Europea de Sustancias Qu&iacute;micas: noticias y la Lista de Candidatas SVHC de REACH.","fr":"Agence europ&eacute;enne des produits chimiques : actualit&eacute;s et la liste des substances candidates SVHC de REACH.","it":"Agenzia europea per le sostanze chimiche: notizie e l'elenco delle sostanze candidate SVHC di REACH.","nl":"Europees Agentschap voor chemische stoffen: nieuws en de REACH-kandidatenlijst van SVHC's.","ca":"Ag&egrave;ncia Europea de Subst&agrave;ncies Qu&iacute;miques: not&iacute;cies i la Llista de Candidates SVHC de REACH."},
 "eea":{"es":"Agencia Europea de Medio Ambiente: noticias, eventos e indicadores ambientales.","fr":"Agence europ&eacute;enne pour l'environnement : actualit&eacute;s, &eacute;v&eacute;nements et indicateurs environnementaux.","it":"Agenzia europea dell'ambiente: notizie, eventi e indicatori ambientali.","nl":"Europees Milieuagentschap: nieuws, evenementen en milieu-indicatoren.","ca":"Ag&egrave;ncia Europea de Medi Ambient: not&iacute;cies, esdeveniments i indicadors ambientals."},
 "efsa":{"es":"Seguridad alimentaria: noticias, publicaciones, sustancias OpenFoodTox y plantas hospedantes de Xylella.","fr":"S&eacute;curit&eacute; alimentaire : actualit&eacute;s, publications, substances OpenFoodTox et plantes h&ocirc;tes de Xylella.","it":"Sicurezza alimentare: notizie, pubblicazioni, sostanze OpenFoodTox e piante ospiti di Xylella.","nl":"Voedselveiligheid: nieuws, publicaties, OpenFoodTox-stoffen en Xylella-waardplanten.","ca":"Seguretat aliment&agrave;ria: not&iacute;cies, publicacions, subst&agrave;ncies OpenFoodTox i plantes hostes de Xylella."},
 "eige":{"es":"Igualdad de g&eacute;nero: noticias, eventos, publicaciones.","fr":"&Eacute;galit&eacute; des genres : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Parit&agrave; di genere: notizie, eventi, pubblicazioni.","nl":"Gendergelijkheid: nieuws, evenementen, publicaties.","ca":"Igualtat de g&egrave;nere: not&iacute;cies, esdeveniments, publicacions."},
 "eit":{"es":"Innovaci&oacute;n y tecnolog&iacute;a: noticias y eventos.","fr":"Innovation et technologie : actualit&eacute;s et &eacute;v&eacute;nements.","it":"Innovazione e tecnologia: notizie ed eventi.","nl":"Innovatie en technologie: nieuws en evenementen.","ca":"Innovaci&oacute; i tecnologia: not&iacute;cies i esdeveniments."},
 "ema":{"es":"Agencia Europea de Medicamentos: medicamentos, designaciones hu&eacute;rfanas y pedi&aacute;tricas, LMR, desabastecimientos, remisiones, PSUSA, medicamentos a base de plantas, DHPC y posautorizaci&oacute;n.","fr":"Agence europ&eacute;enne des m&eacute;dicaments : m&eacute;dicaments, d&eacute;signations orphelines et p&eacute;diatriques, LMR, ruptures, saisines, PSUSA, m&eacute;dicaments &agrave; base de plantes, DHPC et post-autorisation.","it":"Agenzia europea per i medicinali: medicinali, designazioni orfane e pediatriche, LMR, carenze, deferimenti, PSUSA, medicinali a base di erbe, DHPC e post-autorizzazione.","nl":"Europees Geneesmiddelenbureau: geneesmiddelen, wees- en pediatrische aanwijzingen, MRL's, tekorten, verwijzingen, PSUSA, kruidengeneesmiddelen, DHPC's en post-autorisatie.","ca":"Ag&egrave;ncia Europea de Medicaments: medicaments, designacions &ograve;rfenes i pedi&agrave;triques, LMR, desproveximents, remissions, PSUSA, medicaments a base de plantes, DHPC i postautoritzaci&oacute;."},
 "enisa":{"es":"Agencia de Ciberseguridad: noticias y publicaciones.","fr":"Agence pour la cybers&eacute;curit&eacute; : actualit&eacute;s et publications.","it":"Agenzia per la cibersicurezza: notizie e pubblicazioni.","nl":"Agentschap voor cyberbeveiliging: nieuws en publicaties.","ca":"Ag&egrave;ncia de Ciberseguretat: not&iacute;cies i publicacions."},
 "eu-lisa":{"es":"Grandes sistemas inform&aacute;ticos: noticias, eventos, publicaciones.","fr":"Grands syst&egrave;mes informatiques : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Grandi sistemi informatici: notizie, eventi, pubblicazioni.","nl":"Grootschalige IT-systemen: nieuws, evenementen, publicaties.","ca":"Grans sistemes inform&agrave;tics: not&iacute;cies, esdeveniments, publicacions."},
 "eu-osha":{"es":"Seguridad y salud en el trabajo: noticias, eventos, publicaciones.","fr":"S&eacute;curit&eacute; et sant&eacute; au travail : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Sicurezza e salute sul lavoro: notizie, eventi, pubblicazioni.","nl":"Veiligheid en gezondheid op het werk: nieuws, evenementen, publicaties.","ca":"Seguretat i salut en el treball: not&iacute;cies, esdeveniments, publicacions."},
 "euaa":{"es":"Agencia de Asilo de la UE: noticias.","fr":"Agence de l'UE pour l'asile : actualit&eacute;s.","it":"Agenzia dell'UE per l'asilo: notizie.","nl":"EU-Asielagentschap: nieuws.","ca":"Ag&egrave;ncia d'Asil de la UE: not&iacute;cies."},
 "euda":{"es":"Agencia de la UE sobre Drogas: noticias, eventos, publicaciones.","fr":"Agence de l'UE sur les drogues : actualit&eacute;s, &eacute;v&eacute;nements, publications.","it":"Agenzia dell'UE sulle droghe: notizie, eventi, pubblicazioni.","nl":"EU-Drugsagentschap: nieuws, evenementen, publicaties.","ca":"Ag&egrave;ncia de la UE sobre Drogues: not&iacute;cies, esdeveniments, publicacions."},
 "euipo":{"es":"Propiedad intelectual: noticias, eventos y marcas de la UE.","fr":"Propri&eacute;t&eacute; intellectuelle : actualit&eacute;s, &eacute;v&eacute;nements et marques de l'UE.","it":"Propriet&agrave; intellettuale: notizie, eventi e marchi dell'UE.","nl":"Intellectuele eigendom: nieuws, evenementen en EU-merken.","ca":"Propietat intel&middot;lectual: not&iacute;cies, esdeveniments i marques de la UE."},
 "fra":{"es":"Derechos fundamentales: jurisprudencia y Charterpedia.","fr":"Droits fondamentaux : jurisprudence et Charterpedia.","it":"Diritti fondamentali: giurisprudenza e Charterpedia.","nl":"Grondrechten: jurisprudentie en Charterpedia.","ca":"Drets fonamentals: jurisprud&egrave;ncia i Charterpedia."},
}

# Nav chrome (headers + start-here/reference/external link labels) per language.
NAVC = {
 "es":{"starthere":"Empiece aqu&iacute;","intro":"Introducci&oacute;n","fullref":"<strong>Referencia completa de la API</strong> &mdash; los 469 endpoints","auth":"Autenticaci&oacute;n","env":"Sobre de respuesta","err":"Errores","rate":"L&iacute;mites de uso","reference":"Referencia","external":"Externo","institutions":"Instituciones de la UE cubiertas","glossary":"Glosario","usecases":"Casos de uso por perfil","changelog":"Historial de cambios","openapi":"Especificaci&oacute;n OpenAPI (JSON)"},
 "fr":{"starthere":"Commencez ici","intro":"Introduction","fullref":"<strong>R&eacute;f&eacute;rence compl&egrave;te de l'API</strong> &mdash; les 469 endpoints","auth":"Authentification","env":"Enveloppe de r&eacute;ponse","err":"Erreurs","rate":"Limites de d&eacute;bit","reference":"R&eacute;f&eacute;rence","external":"Externe","institutions":"Institutions de l'UE couvertes","glossary":"Glossaire","usecases":"Cas d'usage par profil","changelog":"Journal des modifications","openapi":"Sp&eacute;cification OpenAPI (JSON)"},
 "it":{"starthere":"Inizia qui","intro":"Introduzione","fullref":"<strong>Riferimento API completo</strong> &mdash; tutti i 469 endpoint","auth":"Autenticazione","env":"Busta di risposta","err":"Errori","rate":"Limiti di frequenza","reference":"Riferimento","external":"Esterno","institutions":"Istituzioni dell'UE coperte","glossary":"Glossario","usecases":"Casi d'uso per ruolo","changelog":"Registro modifiche","openapi":"Specifica OpenAPI (JSON)"},
 "nl":{"starthere":"Begin hier","intro":"Inleiding","fullref":"<strong>Volledige API-referentie</strong> &mdash; alle 469 endpoints","auth":"Authenticatie","env":"Response-envelop","err":"Fouten","rate":"Rate-limieten","reference":"Referentie","external":"Extern","institutions":"Gedekte EU-instellingen","glossary":"Woordenlijst","usecases":"Use cases per rol","changelog":"Wijzigingslogboek","openapi":"OpenAPI-specificatie (JSON)"},
 "ca":{"starthere":"Comenceu aqu&iacute;","intro":"Introducci&oacute;","fullref":"<strong>Refer&egrave;ncia completa de l'API</strong> &mdash; els 469 endpoints","auth":"Autenticaci&oacute;","env":"Sobre de resposta","err":"Errors","rate":"L&iacute;mits de crides","reference":"Refer&egrave;ncia","external":"Extern","institutions":"Institucions de la UE cobertes","glossary":"Glossari","usecases":"Casos d'&uacute;s per perfil","changelog":"Hist&ograve;ric de canvis","openapi":"Especificaci&oacute; OpenAPI (JSON)"},
}

LANG_OPT_LABELS = [("/api/docs/","English"),("/api/docs/es.html","Espa&ntilde;ol"),("/api/docs/fr.html","Fran&ccedil;ais"),
 ("/api/docs/it.html","Italiano"),("/api/docs/nl.html","Nederlands"),("/api/docs/ca.html","Catal&agrave;")]

def title_for(slug, lang):
    if slug in AGENCY_SLUGS:
        return AGENCY[slug]
    return TITLE[slug][lang]

def nav_label(slug, lang):
    if slug in AGENCY_SLUGS:
        lab = AGENCY[slug]
        if slug in COUNT: lab += f" ({COUNT[slug]})"
        return lab
    lab = TITLE[slug][lang]
    if slug in COUNT: lab += f" ({COUNT[slug]})"
    return lab

def build_switcher(lang):
    opts=[]
    for val,label in LANG_OPT_LABELS:
        sel=' selected' if val==("/api/docs/"+ (lang+".html")) or (lang=="en" and val=="/api/docs/") else ''
        # current lang's own option:
        sel=' selected' if val==f"/api/docs/{lang}.html" else ''
        opts.append(f'    <option value="{val}"{sel}>{label}</option>')
    return ('  <select class="sidebar__lang" onchange="if(this.value)window.location.href=this.value" aria-label="Language" '
            'style="width:100%;margin:10px 0 16px;padding:7px 9px;border:1px solid #d9def0;border-radius:8px;background:#fff;'
            'font-family:inherit;font-size:13px;color:#1a1a2e;cursor:pointer;">\n' + '\n'.join(opts) + '\n  </select>')

def build_nav(lang):
    nc=NAVC[lang]; L=LANGS[lang]; sec=L["sections"]
    out=['<aside class="sidebar">',
      '  <a href="/api/" class="sidebar__brand">',
      '    <img src="/assets/brubru_mainlogo.png" alt="">',
      '    <span class="sidebar__brand-text">Brubru API</span>',
      '  </a>','', build_switcher(lang),'',
      f'  <h3>{nc["starthere"]}</h3>','  <ul>',
      f'    <li><a href="/api/docs/" class="active">{nc["intro"]}</a></li>',
      f'    <li><a href="/api/docs/reference.html">{nc["fullref"]}</a></li>',
      f'    <li><a href="/api/docs/authentication.html">{nc["auth"]}</a></li>',
      f'    <li><a href="/api/docs/envelope.html">{nc["env"]}</a></li>',
      f'    <li><a href="/api/docs/errors.html">{nc["err"]}</a></li>',
      f'    <li><a href="/api/docs/rate-limits.html">{nc["rate"]}</a></li>','  </ul>']
    for key, slugs in ORDER_SECTIONS:
        out.append(f'\n  <h3>{sec[key]}</h3>')
        out.append('  <ul>')
        for s in slugs:
            out.append(f'    <li><a href="/api/docs/endpoints.html#{s}">{nav_label(s,lang)}</a></li>')
        out.append('  </ul>')
    out += [f'\n  <h3>{nc["reference"]}</h3>','  <ul>',
      f'    <li><a href="/api/docs/institutions.html">{nc["institutions"]}</a></li>',
      f'    <li><a href="/api/docs/glossary.html">{nc["glossary"]}</a></li>',
      f'    <li><a href="/api/docs/use-cases.html">{nc["usecases"]}</a></li>',
      f'    <li><a href="/api/docs/changelog.html">{nc["changelog"]}</a></li>','  </ul>',
      f'\n  <h3>{nc["external"]}</h3>','  <ul>',
      f'    <li><a href="https://brubru-production.up.railway.app/api/openapi.json" target="_blank" rel="noopener">{nc["openapi"]}</a></li>','  </ul>',
      '</aside>']
    return '\n'.join(out)

def build_cards(lang):
    L=LANGS[lang]; sec=L["sections"]
    fo,fm=L["folder_one"],L["folder_many"]
    rows=[]
    for key, slugs in ORDER_SECTIONS:
        n=len(slugs)
        word=fm if n!=1 else fo
        rows.append(f'\n<h3 style="margin-top:28px;">{sec[key]} <span style="font-weight:400;color:var(--text-mut);font-size:0.7em;">({n} {word})</span></h3>')
        rows.append('<div class="toc-grid">')
        for s in slugs:
            rows.append(f'<a class="toc-card" href="/api/docs/endpoints.html#{s}">\n  <div class="toc-card__title">{title_for(s,lang)}</div>\n  <div class="toc-card__desc">{DESC[s][lang]}</div>\n</a>')
        rows.append('</div>')
    return '\n'.join(rows)

# Cadence table rows per language: (cadence-label, coverage-text). 2 columns.
# Verified against backend/config/sync_cadence.json tier mappings.
CAD = {
 "es":[
   ("Cada 6 horas","Leyes adoptadas, procedimientos legislativos, textos y votaciones del Pleno, el Registro de la Comisi&oacute;n, notas de prensa institucionales, el calendario"),
   ("Cada 12 horas","Trabajo en comisi&oacute;n, enmiendas, informes, investigaci&oacute;n EPRS, documentos del Consejo, retransmisiones web"),
   ("A diario","Consultas, preguntas parlamentarias, comitolog&iacute;a, sanciones, medidas de defensa comercial, notificaciones TRIS, licitaciones, infracciones, convocatorias de financiaci&oacute;n; adem&aacute;s del BCE, las instituciones financieras de la UE, el MEDE, las 18 agencias descentralizadas, los datos abiertos y las publicaciones generales"),
   ("Semanal","Indicaciones geogr&aacute;ficas, agendas de los Comisarios, dict&aacute;menes del RSB, investigaci&oacute;n EPRS / STOA / JRC, proyectos financiados por la UE"),
   ("Mensual","Funcionarios y departamentos de la UE (la reingesta masiva del Who Is Who)"),
   ("En vivo (tiempo real)","Perfiles de eurodiputados, casos de competencia de la DG COMP, la Nomenclatura Combinada, los resolvedores de texto legal y de citas"),
   ("Al publicar","La capa propia de Brubru: gu&iacute;as de conocimiento, an&aacute;lisis del EU Canon, traducciones al catal&aacute;n"),
 ],
 "fr":[
   ("Toutes les 6 heures","Actes adopt&eacute;s, proc&eacute;dures l&eacute;gislatives, textes et votes en pl&eacute;ni&egrave;re, le Registre de la Commission, communiqu&eacute;s institutionnels, le calendrier"),
   ("Toutes les 12 heures","Travaux en commission, amendements, rapports, recherche EPRS, documents du Conseil, webstreams"),
   ("Quotidien","Consultations, questions parlementaires, comitologie, sanctions, mesures de d&eacute;fense commerciale, notifications TRIS, appels d'offres, infractions, appels &agrave; financement&nbsp;; ainsi que la BCE, les institutions financi&egrave;res de l'UE, le MES, les 18 agences d&eacute;centralis&eacute;es, les donn&eacute;es ouvertes et les publications g&eacute;n&eacute;rales"),
   ("Hebdomadaire","Indications g&eacute;ographiques, agendas des commissaires, avis du CER, recherche EPRS / STOA / JRC, projets financ&eacute;s par l'UE"),
   ("Mensuel","Fonctionnaires et d&eacute;partements de l'UE (la r&eacute;-ing&eacute;rement en masse du Who Is Who)"),
   ("En direct (temps r&eacute;el)","Profils des d&eacute;put&eacute;s, affaires de concurrence de la DG COMP, la Nomenclature combin&eacute;e, les r&eacute;solveurs de texte juridique et de citations"),
   ("&Agrave; la publication","La couche propri&eacute;taire de Brubru&nbsp;: guides de connaissances, analyses du EU Canon, traductions en catalan"),
 ],
 "it":[
   ("Ogni 6 ore","Atti adottati, procedure legislative, testi e votazioni in plenaria, il Registro della Commissione, comunicati istituzionali, il calendario"),
   ("Ogni 12 ore","Lavori in commissione, emendamenti, relazioni, ricerca EPRS, documenti del Consiglio, webstream"),
   ("Giornaliero","Consultazioni, interrogazioni parlamentari, comitatologia, sanzioni, misure di difesa commerciale, notifiche TRIS, gare, infrazioni, inviti a finanziamento; oltre alla BCE, le istituzioni finanziarie dell'UE, il MES, le 18 agenzie decentrate, i dati aperti e le pubblicazioni generali"),
   ("Settimanale","Indicazioni geografiche, agende dei commissari, pareri del RSB, ricerca EPRS / STOA / JRC, progetti finanziati dall'UE"),
   ("Mensile","Funzionari e dipartimenti dell'UE (la reingestione di massa del Who Is Who)"),
   ("In tempo reale","Profili dei deputati, casi di concorrenza della DG COMP, la Nomenclatura combinata, i resolver di testo giuridico e citazioni"),
   ("Alla pubblicazione","Lo strato proprietario di Brubru: guide di conoscenza, approfondimenti del EU Canon, traduzioni in catalano"),
 ],
 "nl":[
   ("Elke 6 uur","Vastgestelde wetten, wetgevingsprocedures, plenaire teksten en stemmingen, het Commissieregister, institutionele persberichten, de kalender"),
   ("Elke 12 uur","Commissiewerk, amendementen, verslagen, EPRS-onderzoek, Raadsdocumenten, webstreams"),
   ("Dagelijks","Consultaties, parlementaire vragen, comitologie, sancties, handelsbeschermingsmaatregelen, TRIS-kennisgevingen, aanbestedingen, inbreuken, financieringsoproepen; plus de ECB, de financi&euml;le instellingen van de EU, het ESM, de 18 gedecentraliseerde agentschappen, open data en algemene publicaties"),
   ("Wekelijks","Geografische aanduidingen, agenda's van de commissarissen, RSB-adviezen, EPRS- / STOA- / JRC-onderzoek, door de EU gefinancierde projecten"),
   ("Maandelijks","EU-ambtenaren en -afdelingen (de bulk-herinname van Who Is Who)"),
   ("Live (realtime)","Ledenprofielen, DG COMP-mededingingszaken, de Gecombineerde Nomenclatuur, de wetstekst- en citatie-resolvers"),
   ("Bij publicatie","De Brubru-eigen laag: kennisgidsen, EU Canon-analyses, Catalaanse vertalingen"),
 ],
 "ca":[
   ("Cada 6 hores","Lleis adoptades, procediments legislatius, textos i votacions del Ple, el Registre de la Comissi&oacute;, notes de premsa institucionals, el calendari"),
   ("Cada 12 hores","Treball en comissi&oacute;, esmenes, informes, recerca EPRS, documents del Consell, retransmissions web"),
   ("Diari","Consultes, preguntes parlament&agrave;ries, comitologia, sancions, mesures de defensa comercial, notificacions TRIS, licitacions, infraccions, convocat&ograve;ries de finan&ccedil;ament; a m&eacute;s del BCE, les institucions financeres de la UE, el MEDE, les 18 ag&egrave;ncies descentralitzades, les dades obertes i les publicacions generals"),
   ("Setmanal","Indicacions geogr&agrave;fiques, agendes dels comissaris, dict&agrave;mens del RSB, recerca EPRS / STOA / JRC, projectes finan&ccedil;ats per la UE"),
   ("Mensual","Funcionaris i departaments de la UE (la reingesti&oacute; massiva del Who Is Who)"),
   ("En directe (temps real)","Perfils d'eurodiputats, casos de compet&egrave;ncia de la DG COMP, la Nomenclatura Combinada, els resoluts de text legal i de cites"),
   ("En publicar","La capa pr&ograve;pia de Brubru: guies de coneixement, an&agrave;lisis de l'EU Canon, traduccions al catal&agrave;"),
 ],
}

def build_cadence(lang):
    L=LANGS[lang]; th=L["ds_th"]
    out=['<table>', f'<thead><tr><th>{th[0]}</th><th>{th[1]}</th></tr></thead>','<tbody>']
    for cad,cover in CAD[lang]:
        out.append(f'<tr><td>{cad}</td><td>{cover}</td></tr>')
    out += ['</tbody>','</table>']
    return '\n'.join(out)

PAGE = '''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" type="image/png" href="/assets/brubru_mainlogo.png">
<link rel="stylesheet" href="/api/docs/_assets/docs.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css">
<link rel="alternate" hreflang="en" href="https://brubru.beresol.eu/api/docs/">
<link rel="alternate" hreflang="es" href="https://brubru.beresol.eu/api/docs/es.html">
<link rel="alternate" hreflang="fr" href="https://brubru.beresol.eu/api/docs/fr.html">
<link rel="alternate" hreflang="it" href="https://brubru.beresol.eu/api/docs/it.html">
<link rel="alternate" hreflang="nl" href="https://brubru.beresol.eu/api/docs/nl.html">
<link rel="alternate" hreflang="ca" href="https://brubru.beresol.eu/api/docs/ca.html">
<link rel="alternate" hreflang="x-default" href="https://brubru.beresol.eu/api/docs/">
</head>
<body>
<div id="brubru-paywall-banner" style="position:sticky;top:0;z-index:50;background:linear-gradient(90deg,#0693e3 0%,#047dbe 100%);color:#fff;padding:12px 20px;text-align:center;font-family:'Adobe Caslon Pro',Georgia,serif;font-size:15px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
  <span>{pw_text}</span>
  <a href="/subscription" style="color:#fff;font-weight:700;text-decoration:underline;">{pw_trial}</a>
  <span>{pw_or}</span>
  <a href="mailto:hello@beresol.eu" style="color:#fff;font-weight:700;text-decoration:underline;">{pw_sales}</a>
  <button onclick="document.getElementById('brubru-paywall-banner').style.display='none';sessionStorage.setItem('brubru_paywall_dismissed','1');" style="float:right;background:transparent;border:none;color:#fff;font-size:18px;cursor:pointer;padding:0 8px;" aria-label="Dismiss">&times;</button>
</div>
<script>
(function(){{
  var m = document.cookie.match(/brubru_tier=([^;]+)/);
  if (m && m[1] === 'blue') {{ var b = document.getElementById('brubru-paywall-banner'); if (b) b.style.display = 'none'; }}
  if (sessionStorage.getItem('brubru_paywall_dismissed') === '1') {{ var b = document.getElementById('brubru-paywall-banner'); if (b) b.style.display = 'none'; }}
}})();
</script>

<div class="shell">
{nav}

<main class="main">

<div class="main__eyebrow">{eyebrow}</div>
<h1>{h1}</h1>
<p class="main__lede">
{lede}
</p>
<p style="margin:1.25rem 0 0;padding:1rem 1.25rem;background:#f3f5fb;border:1px solid #d9def0;border-radius:10px;">
{box}
</p>

<div class="callout callout--ok">
<p><strong>{callout_q}</strong>{callout_b}</p>
</div>

<h2>{wyg_h}</h2>
<p>{wyg_p}</p>
{cards}

<h2>{ds_h}</h2>
<p>{ds_p}</p>
{cadence}

<h2>{auth_h}</h2>
<p>{auth_p}</p>

<pre><code>curl -H "Authorization: Bearer brubru_live_..." \\
  "https://brubru.beresol.eu/api/v2/legislative/eur-lex/laws?q=artificial+intelligence&amp;limit=5"</code></pre>

<p>{auth_full}</p>

<h2>{env_h}</h2>
<p>{env_p}</p>

<pre><code>{{
  "total": 139,
  "returned": 20,
  "pages": 7,
  "page": 1,
  "limit": 50,
  "has_more": true,
  "next_page": 2,
  "remaining_pages": 6,
  "coverage_complete": true,
  "published_from": "2026-01-01",
  "published_to": "2026-01-31",
  "published_end": "2026-01-31",
  "detail_level": "Full",
  "data": [ ... ]
}}</code></pre>

<p>{env_hdr_p}</p>
<pre><code>X-Powered-By: Brubru
X-Source: brubru.beresol.eu
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 58
X-RateLimit-Tier: free</code></pre>

<p>{env_full}</p>

<h2>{qs_h}</h2>

<p>{qs1}</p>

<p>{qs2}</p>

<pre><code>curl "https://brubru.beresol.eu/health"</code></pre>

<p>{qs2resp}</p>

<pre><code>{{
  "status": "ok",
  "service": "brubru-data-provider",
  "time": "2026-04-20T15:00:00Z"
}}</code></pre>

<p>{qs3}</p>

<pre><code>curl -H "Authorization: Bearer $BRUBRU_API_KEY" \\
  "https://brubru.beresol.eu/api/v2/legislative/eur-lex/laws?q=artificial+intelligence&amp;limit=3"</code></pre>

<p>{qs3_after}</p>

<h2>{lim_h}</h2>
<ul>
{lim_items}
</ul>

<h2>{next_h}</h2>
<div class="toc-grid">
{next_cards}
</div>

<footer>
{footer}
<a href="/api/">{footer_back}</a> &middot;
<a href="/api/openapi.json">OpenAPI</a> &middot;
<a href="mailto:hello@beresol.eu">hello@beresol.eu</a>
</footer>
</main>
</div>
</body>
</html>
'''

for lang, L in LANGS.items():
    lim_items='\n'.join(f'<li>{x}</li>' for x in L["lim"])
    next_cards='\n'.join(
        f'<a class="toc-card" href="{href}">\n  <div class="toc-card__title">{t}</div>\n  <div class="toc-card__desc">{d}</div>\n</a>'
        for href,t,d in L["next"])
    html = PAGE.format(
        lang=L["lang"], title=L["title"], desc=L["desc"],
        pw_text=L["pw_text"], pw_trial=L["pw_trial"], pw_or=L["pw_or"], pw_sales=L["pw_sales"],
        nav=build_nav(lang), eyebrow=L["eyebrow"], h1=L["h1"], lede=L["lede"], box=L["box"],
        callout_q=L["callout_q"], callout_b=L["callout_b"], wyg_h=L["wyg_h"], wyg_p=L["wyg_p"],
        cards=build_cards(lang), ds_h=L["ds_h"], ds_p=L["ds_p"], cadence=build_cadence(lang),
        auth_h=L["auth_h"], auth_p=L["auth_p"], auth_full=L["auth_full"],
        env_h=L["env_h"], env_p=L["env_p"], env_hdr_p=L["env_hdr_p"], env_full=L["env_full"],
        qs_h=L["qs_h"], qs1=L["qs1"], qs2=L["qs2"], qs2resp=L["qs2resp"], qs3=L["qs3"], qs3_after=L["qs3_after"],
        lim_h=L["lim_h"], lim_items=lim_items, next_h=L["next_h"], next_cards=next_cards,
        footer=L["footer"], footer_back=L["footer_back"],
    )
    (DOCS / f"{lang}.html").write_text(html, encoding="utf-8")
    print(f"wrote {lang}.html  ({len(html)} bytes)  v1={'/api/v1' in html or 'API v1' in html}")
print("done")
