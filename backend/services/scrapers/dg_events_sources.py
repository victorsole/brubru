"""
Registry of European Commission DG / agency event-page URLs to ingest into
My EU Calendar (from docs/new_format/prompt_new_format.md, lines 418-468).

Each entry: url, institution (calendar InstitutionEnum value), dg (canonical
Commission DG code or None), kind, and an optional agency code for provenance.

kind:
  oe_event   - EC Drupal "What's on" event list (ecl-content-item). The bulk;
               normal HTTP (browser UA), no WAF. High yield.
  eurostat   - Eurostat events / release calendar (own markup).
  dataeuropa - data.europa.eu open-data-portal events.
  agenda     - College tentative agenda / minutes (documents-register SPA).
               Already ingested by the ec_tentative_agenda source -> skipped here.
  college_calendar - President & Commissioners calendar page.
  lobby      - transparency-initiative lobby-meeting register (SPA; a "who met
               whom" log, not public events) -> best-effort, usually 0.
  expert_group - expert-groups register meeting (SPA) -> best-effort.
"""

# institution defaults to COMMISSION unless noted. dg = canonical DG code.
DG_EVENT_SOURCES = [
    # --- Agendas / transparency (SPA) ---
    {"url": "https://ec.europa.eu/transparency/documents-register/search?query=eyJjYXRlZ29yeU9iamVjdHMiOltdLCJjYXRlZ29yaWVzIjpbXSwidHlwZU9iamVjdHMiOlt7ImlkIjoiVEVOVEFUX0FHRU5EQV9DT01fTUVFVElORyIsInR5cGUiOiJUWVBFIn1dLCJ0eXBlcyI6WyJURU5UQVRfQUdFTkRBX0NPTV9NRUVUSU5HIl0sImRlcGFydG1lbnRPYmplY3RzIjpbXSwiZGVwYXJ0bWVudHMiOltdLCJsYW5ndWFnZSI6ImVuIiwia2V5d29yZHNTZWFyY2hUeXBlIjoiQVRfTEVBU1RfT05FIiwidGFyZ2V0IjoiVElUTEVfQU5EX0NPTlRFTlQiLCJzb3J0QnkiOiJET0NVTUVOVF9EQVRFX0RFU0MiLCJpc1JlZ3VsYXIiOnRydWUsInBhZ2UiOjF9", "institution": "COMMISSION", "dg": None, "kind": "agenda"},
    {"url": "https://ec.europa.eu/transparency/documents-register/search?query=eyJjYXRlZ29yeU9iamVjdHMiOlt7ImlkIjoiUFYiLCJ0eXBlIjoiQ0FURUdPUlkifV0sImNhdGVnb3JpZXMiOlsiUFYiXSwidHlwZU9iamVjdHMiOltdLCJ0eXBlcyI6W10sImRlcGFydG1lbnRPYmplY3RzIjpbXSwiZGVwYXJ0bWVudHMiOltdLCJsYW5ndWFnZSI6ImVuIiwia2V5d29yZHNTZWFyY2hUeXBlIjoiQVRfTEVBU1RfT05FIiwidGFyZ2V0IjoiVElUTEVfQU5EX0NPTlRFTlQiLCJzb3J0QnkiOiJET0NVTUVOVF9EQVRFX0RFU0MiLCJpc1JlZ3VsYXIiOnRydWUsInBhZ2UiOjF9", "institution": "COMMISSION", "dg": None, "kind": "agenda"},
    {"url": "https://commission.europa.eu/about/organisation/college-commissioners/calendar-items-president-and-commissioners_en", "institution": "COMMISSION", "dg": None, "kind": "college_calendar"},

    # --- DG event pages (oe_event) ---
    {"url": "https://agriculture.ec.europa.eu/media/events_en?f%5B0%5D=oe_event_status%3Aupcoming", "institution": "COMMISSION", "dg": "AGRI", "kind": "oe_event"},
    {"url": "https://agriculture.ec.europa.eu/media/events_en", "institution": "COMMISSION", "dg": "AGRI", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=d41e42be-7ff1-4635-bb4f-e47d38f886ed", "institution": "COMMISSION", "dg": "AGRI", "kind": "lobby"},
    {"url": "https://climate.ec.europa.eu/news-your-voice/events_en?f[0]=oe_event_status%3Apast&f[1]=oe_event_status%3Aupcoming", "institution": "COMMISSION", "dg": "CLIMA", "kind": "oe_event"},
    {"url": "https://climate.ec.europa.eu/citizens-stakeholders/events_en", "institution": "COMMISSION", "dg": "CLIMA", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=2aac00d9-fbaf-425f-af65-c697a37d51bb", "institution": "COMMISSION", "dg": "CLIMA", "kind": "lobby"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=aae7124c-b839-4139-9ffe-ad5660fe9404", "institution": "COMMISSION", "dg": "CNECT", "kind": "lobby"},
    {"url": "https://digital-strategy.ec.europa.eu/en/events", "institution": "COMMISSION", "dg": "CNECT", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=ffdb1b81-84a9-4ce1-8974-164aa26ce7e8", "institution": "COMMISSION", "dg": "CNECT", "kind": "lobby"},
    {"url": "https://ec.europa.eu/transparency/expert-groups-register/screen/expert-groups/consult?lang=en&groupId=3904&fromMeetings=true&meetingId=67755", "institution": "COMMISSION", "dg": "CNECT", "kind": "expert_group"},
    {"url": "https://digital-markets-act.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "COMP", "kind": "oe_event"},
    {"url": "https://digital-markets-act.ec.europa.eu/events/workshops_en", "institution": "COMMISSION", "dg": "COMP", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=3c3c8b28-6aa7-4b6b-b3d1-c06e22e002b4", "institution": "COMMISSION", "dg": "COMP", "kind": "lobby"},
    {"url": "https://defence-industry-space.ec.europa.eu/newsroom/events_en", "institution": "COMMISSION", "dg": "DEFIS", "kind": "oe_event"},
    {"url": "https://eu-space.europa.eu/explore-euspace/events/recent", "institution": "COMMISSION", "dg": "DEFIS", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=06fb3b80-76a8-43f1-b1a5-e703cfe8d625", "institution": "COMMISSION", "dg": "DEFIS", "kind": "lobby"},
    {"url": "https://ec.europa.eu/transparency-initiative/meetings/meeting.do?host=e2ac53f7-cf9c-4aa7-a7fd-06a355c8b361", "institution": "COMMISSION", "dg": "ECFIN", "kind": "lobby"},
    {"url": "https://economy-finance.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "ECFIN", "kind": "oe_event"},
    {"url": "https://employment-social-affairs.ec.europa.eu/events-1_en", "institution": "COMMISSION", "dg": "EMPL", "kind": "oe_event"},
    {"url": "https://energy.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "ENER", "kind": "oe_event"},
    {"url": "https://ec.europa.eu/environment/all-events_en", "institution": "COMMISSION", "dg": "ENV", "kind": "oe_event"},
    {"url": "https://anti-fraud.ec.europa.eu/media-corner/events_en", "institution": "COMMISSION", "dg": "OLAF", "kind": "oe_event"},
    {"url": "https://civil-protection-humanitarian-aid.ec.europa.eu/news-stories/events_en", "institution": "COMMISSION", "dg": "ECHO", "kind": "oe_event"},

    # --- Executive agencies (institution COMMISSION; no DG; provenance via agency) ---
    {"url": "https://cinea.ec.europa.eu/news-events/events_en", "institution": "COMMISSION", "dg": None, "agency": "CINEA", "kind": "oe_event"},
    {"url": "https://www.eacea.ec.europa.eu/news-events/events_en", "institution": "COMMISSION", "dg": None, "agency": "EACEA", "kind": "oe_event"},
    {"url": "https://hadea.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": None, "agency": "HADEA", "kind": "oe_event"},
    {"url": "https://eismea.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": None, "agency": "EISMEA", "kind": "oe_event"},
    {"url": "https://erc.europa.eu/news-events/events", "institution": "COMMISSION", "dg": None, "agency": "ERCEA", "kind": "oe_event"},
    {"url": "https://rea.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": None, "agency": "REA", "kind": "oe_event"},

    # --- Eurostat ---
    {"url": "https://ec.europa.eu/eurostat/web/main/news/events-webinars", "institution": "COMMISSION", "dg": "ESTAT", "kind": "eurostat"},
    {"url": "https://ec.europa.eu/eurostat/web/main/news/release-calendar", "institution": "COMMISSION", "dg": "ESTAT", "kind": "eurostat"},

    # --- More DGs ---
    {"url": "https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/health-emergency-preparedness-and-response-hera-events_en?f%5B0%5D=topic_topic%3A198&f%5B1%5D=topic_topic%3A199&f%5B2%5D=topic_topic%3A200&f%5B3%5D=topic_topic%3A205&f%5B4%5D=topic_topic%3A223&f%5B5%5D=topic_topic%3A233&f%5B6%5D=topic_topic%3A235&f%5B7%5D=topic_topic%3A238", "institution": "COMMISSION", "dg": "HERA", "kind": "oe_event"},
    {"url": "https://single-market-economy.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "GROW", "kind": "oe_event"},
    {"url": "https://single-market-economy.ec.europa.eu/single-market/chief-economist-business-intelligence-unit/event-activities_en", "institution": "COMMISSION", "dg": "GROW", "kind": "oe_event"},
    {"url": "https://international-partnerships.ec.europa.eu/news-and-events/events_en", "institution": "COMMISSION", "dg": "INTPA", "kind": "oe_event"},
    {"url": "https://joint-research-centre.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "JRC", "kind": "oe_event"},
    {"url": "https://oceans-and-fisheries.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "MARE", "kind": "oe_event"},
    {"url": "https://home-affairs.ec.europa.eu/whats-new/events_en", "institution": "COMMISSION", "dg": "HOME", "kind": "oe_event"},
    {"url": "https://transport.ec.europa.eu/news-events/events_en", "institution": "COMMISSION", "dg": "MOVE", "kind": "oe_event"},
    {"url": "https://transport.ec.europa.eu/news-events/main-events_en", "institution": "COMMISSION", "dg": "MOVE", "kind": "oe_event"},
    {"url": "https://research-and-innovation.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "RTD", "kind": "oe_event"},
    {"url": "https://taxation-customs.ec.europa.eu/about-us/events_en", "institution": "COMMISSION", "dg": "TAXUD", "kind": "oe_event"},
    {"url": "https://policy.trade.ec.europa.eu/events_en", "institution": "COMMISSION", "dg": "TRADE", "kind": "oe_event"},
    {"url": "https://translation.ec.europa.eu/news-and-events/events_en", "institution": "COMMISSION", "dg": "DGT", "kind": "oe_event"},

    # --- data.europa.eu (Publications Office open-data portal) ---
    {"url": "https://data.europa.eu/en/news-events/events?field_type_value=internal&title=&filter_option=in_progress_and_upcoming&sort_by=start_date&sort_order=ASC&items_per_page=10", "institution": "COMMISSION", "dg": None, "agency": "OP", "kind": "dataeuropa"},
    {"url": "https://data.europa.eu/en/news-events/events", "institution": "COMMISSION", "dg": None, "agency": "OP", "kind": "dataeuropa"},
]
