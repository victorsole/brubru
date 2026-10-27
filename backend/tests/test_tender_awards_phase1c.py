"""Phase 1 C of the funding standard: TED contract awards whose buyer is an EU body (26 Oct 2026).

On 21 Oct a partner search for a DG CNECT tender was answered by TED's award notices, queried at TED:
Brubru held 104 result notices and no winner. Covered here: which buyer counts as an EU body (TED's
own label does not: half of the notices it labels are national), the winners read from the eForms
XML (the search API's flat lists stop lining up when a lot has several winners), the VAT shape that
lets a TED company id join the CORDIS and FTS VAT numbers, the loader, /funding/tender-awards and
the awards inside /funding/partners.

The notice below is made up (no real company or person): two buyers (an EU one, a review body that
is not a buyer), a joint tender, a two-rank cascade, a ranked tender no contract was concluded with,
a lot closed without a winner.
"""
import importlib
import pathlib
import re
import sys
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402
from services.funding.countries import alpha3_code, vat_number  # noqa: E402
from services.scrapers import ted_awards  # noqa: E402

NS = ('xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2" '
      'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
      'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
      'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
      'xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1" '
      'xmlns:efbc="http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1" '
      'xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1"')


def _org(ref, name, country, website=None, email=None, company_id=None, size=None, city="Town"):
    return f"""<efac:Organization><efac:Company>
        {f'<cbc:WebsiteURI>{website}</cbc:WebsiteURI>' if website else ''}
        <cac:PartyIdentification><cbc:ID>{ref}</cbc:ID></cac:PartyIdentification>
        <cac:PartyName><cbc:Name languageID="ENG">{name}</cbc:Name></cac:PartyName>
        <cac:PostalAddress><cbc:CityName>{city}</cbc:CityName><cac:Country><cbc:IdentificationCode listName="country">{country}</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
        {f'<cac:PartyLegalEntity><cbc:CompanyID>{company_id}</cbc:CompanyID></cac:PartyLegalEntity>' if company_id else ''}
        {f'<cac:Contact><cbc:ElectronicMail>{email}</cbc:ElectronicMail></cac:Contact>' if email else ''}
        {f'<efbc:CompanySizeCode>{size}</efbc:CompanySizeCode>' if size else ''}
    </efac:Company></efac:Organization>"""


def _tender(ref, tpa, lot, value=None, rank=None):
    return f"""<efac:LotTender><cbc:ID schemeName="tender">{ref}</cbc:ID>
        {f'<cbc:RankCode>{rank}</cbc:RankCode>' if rank else ''}
        {f'<cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="EUR">{value}</cbc:PayableAmount></cac:LegalMonetaryTotal>' if value else ''}
        <efac:TenderingParty><cbc:ID>{tpa}</cbc:ID></efac:TenderingParty><efac:TenderLot><cbc:ID>{lot}</cbc:ID></efac:TenderLot>
    </efac:LotTender>"""


def _contract(ref, tender, reference, signed):
    return f"""<efac:SettledContract><cbc:ID>{ref}</cbc:ID><cbc:AwardDate>2025-02-01+01:00</cbc:AwardDate>
        <cbc:IssueDate>{signed}+01:00</cbc:IssueDate><efac:ContractReference><cbc:ID>{reference}</cbc:ID></efac:ContractReference>
        <efac:LotTender><cbc:ID>{tender}</cbc:ID></efac:LotTender></efac:SettledContract>"""


def _lot_result(ref, code, lot, tenders, received=None):
    stats = (f'<efac:ReceivedSubmissionsStatistics><efbc:StatisticsCode listName="received-submission-type">tenders'
             f'</efbc:StatisticsCode><efbc:StatisticsNumeric>{received}</efbc:StatisticsNumeric></efac:ReceivedSubmissionsStatistics>'
             if received is not None else "")
    refs = "".join(f"<efac:LotTender><cbc:ID>{t}</cbc:ID></efac:LotTender>" for t in tenders)
    return (f'<efac:LotResult><cbc:ID>{ref}</cbc:ID><cbc:TenderResultCode listName="winner-selection-status">{code}'
            f'</cbc:TenderResultCode>{refs}{stats}<efac:TenderLot><cbc:ID>{lot}</cbc:ID></efac:TenderLot></efac:LotResult>')


def _lot(ref, title):
    return (f"<cac:ProcurementProjectLot><cbc:ID>{ref}</cbc:ID><cac:ProcurementProject>"
            f'<cbc:Name languageID="ENG">{title}</cbc:Name></cac:ProcurementProject></cac:ProcurementProjectLot>')


def _notice(buyer_website="https://example-dg.ec.europa.eu/funding", buyer_email="dg-tenders@ec.europa.eu",
            buyer_type="eu-ins-bod-ag", version="01", changes=""):
    orgs = "".join([
        _org("ORG-0001", "European Commission, DG EXAMPLE - Example Policy", "BEL", buyer_website, buyer_email),
        _org("ORG-0002", "Court of Justice of the European Union", "LUX", "https://curia.europa.eu"),
        _org("ORG-0003", "Alpha Studies\nSL", "ESP", company_id="VAT ESB12345678", size="sme"),
        _org("ORG-0004", "Beta Research GmbH", "DEU", company_id="DE123456789", size="large"),
        _org("ORG-0005", "Gamma Analytics", "GRC", company_id="GR094000001", size="small"),
        _org("ORG-0006", "Delta Consult", "DNK", company_id="29200000", size="micro"),
        _org("ORG-0007", "Epsilon Loser Ltd", "IRL", company_id="1234567T", size="sme"),
    ])
    result = "".join([
        "<efac:NoticeResult>",
        '<cbc:TotalAmount currencyID="EUR">900000</cbc:TotalAmount>',
        _lot_result("RES-0001", "selec-w", "LOT-0001", ["TEN-0001"], received=3),
        _lot_result("RES-0002", "selec-w", "LOT-0002", ["TEN-0002", "TEN-0003", "TEN-0004"]),
        _lot_result("RES-0003", "clos-nw", "LOT-0003", [], received=0),
        _tender("TEN-0001", "TPA-0001", "LOT-0001", value=500000),
        _tender("TEN-0002", "TPA-0002", "LOT-0002", value=400000, rank=1),
        _tender("TEN-0003", "TPA-0003", "LOT-0002", value=0, rank=2),
        _tender("TEN-0004", "TPA-0004", "LOT-0002", value=0, rank=3),
        _contract("CON-0001", "TEN-0001", "EX/2025/001", "2025-03-14"),
        _contract("CON-0002", "TEN-0002", "EX/2025/002-1", "2025-03-20"),
        _contract("CON-0003", "TEN-0003", "EX/2025/002-2", "2025-03-21"),
        "<efac:TenderingParty><cbc:ID>TPA-0001</cbc:ID>"
        "<efac:Tenderer><cbc:ID>ORG-0003</cbc:ID><efbc:GroupLeadIndicator>true</efbc:GroupLeadIndicator></efac:Tenderer>"
        "<efac:Tenderer><cbc:ID>ORG-0004</cbc:ID></efac:Tenderer>"
        "<efac:SubContractor><cbc:ID>ORG-0007</cbc:ID></efac:SubContractor></efac:TenderingParty>",
        "<efac:TenderingParty><cbc:ID>TPA-0002</cbc:ID><efac:Tenderer><cbc:ID>ORG-0005</cbc:ID></efac:Tenderer></efac:TenderingParty>",
        "<efac:TenderingParty><cbc:ID>TPA-0003</cbc:ID><efac:Tenderer><cbc:ID>ORG-0006</cbc:ID></efac:Tenderer></efac:TenderingParty>",
        "<efac:TenderingParty><cbc:ID>TPA-0004</cbc:ID><efac:Tenderer><cbc:ID>ORG-0007</cbc:ID></efac:Tenderer></efac:TenderingParty>",
        "</efac:NoticeResult>",
    ])
    return f"""<?xml version="1.0" encoding="UTF-8"?><ContractAwardNotice {NS}>
    <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent><efext:EformsExtension>
      {changes}{result}<efac:Organizations>{orgs}</efac:Organizations>
      <efac:Publication><efbc:NoticePublicationID>00999999-2025</efbc:NoticePublicationID><efbc:PublicationDate>2025-06-02+01:00</efbc:PublicationDate></efac:Publication>
    </efext:EformsExtension></ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
    <cbc:ID schemeName="notice-id">aaaaaaaa-0000-0000-0000-000000000001</cbc:ID>
    <cbc:ContractFolderID>bbbbbbbb-0000-0000-0000-000000000002</cbc:ContractFolderID>
    <cbc:IssueDate>2025-05-28+01:00</cbc:IssueDate><cbc:VersionID>{version}</cbc:VersionID>
    <cbc:NoticeTypeCode listName="result">can-standard</cbc:NoticeTypeCode>
    <cac:ContractingParty><cac:ContractingPartyType><cbc:PartyTypeCode listName="buyer-legal-type">{buyer_type}</cbc:PartyTypeCode></cac:ContractingPartyType>
      <cac:Party><cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification></cac:Party></cac:ContractingParty>
    <cac:TenderingProcess><cbc:ProcedureCode listName="procurement-procedure-type">open</cbc:ProcedureCode></cac:TenderingProcess>
    <cac:ProcurementProject><cbc:Name languageID="ENG">Study on example\n policies</cbc:Name>
      <cbc:Description languageID="ENG">A study of example policies.</cbc:Description>
      <cbc:ProcurementTypeCode listName="contract-nature">services</cbc:ProcurementTypeCode>
      <cac:MainCommodityClassification><cbc:ItemClassificationCode listName="cpv">79311000</cbc:ItemClassificationCode></cac:MainCommodityClassification>
      <cac:AdditionalCommodityClassification><cbc:ItemClassificationCode listName="cpv">73210000</cbc:ItemClassificationCode></cac:AdditionalCommodityClassification>
    </cac:ProcurementProject>
    {_lot("LOT-0001", "Lot one")}{_lot("LOT-0002", "Lot two")}{_lot("LOT-0003", "Lot three")}
    </ContractAwardNotice>"""


# --- which buyer is an EU body ----------------------------------------------------------------------- #

def test_an_eu_body_is_known_by_its_own_address_not_by_teds_label():
    eu = ted_awards.is_eu_body_address
    assert eu("https://ec.europa.eu/environment/funding") and eu("env-tenders@ec.europa.eu") and eu("www.eea.europa.eu")
    assert eu("https://www.eib.org/en/") and eu("procurement@eif.org") and eu("https://www.sesarju.eu")
    assert not eu("https://www.gov.si/") and not eu("dzp@usk.poznan.pl") and not eu(None) and not eu("")
    assert not eu("user@enotices.ted.europa.eu")                       # TED's eNotices service files, it does not buy
    assert not eu("https://noteuropa.eu") and not eu("https://europa.eu.example.com")


def test_a_notice_whose_buyer_is_national_is_not_kept_whatever_its_label():
    assert ted_awards.parse_award(_notice(buyer_website="https://www.gov.si/", buyer_email="gp@gov.si"), "1-2025") is None
    assert ted_awards.parse_award(_notice(buyer_website=None, buyer_email="x@enotices.ted.europa.eu"), "1-2025") is None
    # An EU body labelled otherwise by TED (body-pl, int-org) is kept.
    kept = ted_awards.parse_award(_notice(buyer_type="body-pl"), "1-2025")
    assert kept is not None and kept["buyer_legal_type"] == "body-pl"
    assert ted_awards.parse_award("<not-xml", "1-2025") is None


# --- the winners, read from the XML ------------------------------------------------------------------ #

def test_the_winners_are_the_organisations_of_the_tenders_a_contract_was_concluded_with():
    n = ted_awards.parse_award(_notice(), "999999-2025")
    rows = [(w["lot_id"], w["tender_id"], w["org_ref"], w["name"], w["is_group_lead"], w["group_size"], w["rank"])
            for w in n["winners"]]
    assert rows == [
        ("LOT-0001", "TEN-0001", "ORG-0003", "Alpha Studies SL", True, 2, None),        # a joint tender: both members,
        ("LOT-0001", "TEN-0001", "ORG-0004", "Beta Research GmbH", False, 2, None),    # its subcontractor is not one
        ("LOT-0002", "TEN-0002", "ORG-0005", "Gamma Analytics", False, 1, 1),         # a cascade: ranks 1 and 2,
        ("LOT-0002", "TEN-0003", "ORG-0006", "Delta Consult", False, 1, 2),           # rank 3 had no contract
    ]
    first = n["winners"][0]
    assert (first["tender_value"], first["tender_value_currency"], first["contract_reference"]) == (500000.0, "EUR", "EX/2025/001")
    assert (first["contract_date"], first["award_date"], first["lot_title"]) == ("2025-03-14", "2025-02-01", "Lot one")
    assert [(w["country"], w["vat_key"]) for w in n["winners"]] == [
        ("ES", "ESB12345678"), ("DE", "DE123456789"), ("EL", "EL094000001"), ("DK", "DK29200000")]


def test_a_party_named_without_its_organisation_is_the_notices_organisation_of_that_name():
    xml = _notice().replace(
        "<efac:TenderingParty><cbc:ID>TPA-0002</cbc:ID><efac:Tenderer><cbc:ID>ORG-0005</cbc:ID></efac:Tenderer></efac:TenderingParty>",
        "<efac:TenderingParty><cbc:ID>TPA-0002</cbc:ID><cbc:Name>GAMMA\n Analytics</cbc:Name></efac:TenderingParty>").replace(
        "<efac:TenderingParty><cbc:ID>TPA-0003</cbc:ID><efac:Tenderer><cbc:ID>ORG-0006</cbc:ID></efac:Tenderer></efac:TenderingParty>",
        "<efac:TenderingParty><cbc:ID>TPA-0003</cbc:ID><cbc:Name>European Commission, DG EXAMPLE - Example Policy</cbc:Name></efac:TenderingParty>")
    rows = [(w["tender_id"], w["org_ref"], w["name"], w["is_group_lead"], w["group_size"], w["vat_key"])
            for w in ted_awards.parse_award(xml, "999999-2025")["winners"] if w["lot_id"] == "LOT-0002"]
    # Gamma by its name; the buyer's own name never makes it a winner.
    assert rows == [("TEN-0002", "ORG-0005", "Gamma Analytics", False, 1, "EL094000001")]

def test_a_result_written_twice_or_a_member_listed_twice_gives_each_winner_once():
    base = ted_awards.parse_award(_notice(), "999999-2025")["winners"]
    twice = _lot_result("RES-0001", "selec-w", "LOT-0001", ["TEN-0001"], received=3)
    xml = _notice().replace(twice, twice + twice.replace("RES-0001", "RES-0004")).replace(
        "<efac:Tenderer><cbc:ID>ORG-0005</cbc:ID></efac:Tenderer>",
        "<efac:Tenderer><cbc:ID>ORG-0005</cbc:ID></efac:Tenderer><efac:Tenderer><cbc:ID>ORG-0005</cbc:ID>"
        "<efbc:GroupLeadIndicator>true</efbc:GroupLeadIndicator></efac:Tenderer>")
    winners = ted_awards.parse_award(xml, "999999-2025")["winners"]
    key = lambda w: (w["tender_id"], w["org_ref"], w["is_group_lead"], w["group_size"])  # noqa: E731
    assert [key(w) for w in winners] == [key(w) if w["org_ref"] != "ORG-0005" else ("TEN-0002", "ORG-0005", True, 1)
                                         for w in base]

def test_the_notice_carries_the_standards_tender_fields():
    n = ted_awards.parse_award(_notice(), "999999-2025")
    assert n["contracting_authority"] == "European Commission, DG EXAMPLE - Example Policy"
    assert [b["name"] for b in n["buyers"]] == [n["contracting_authority"]]            # the review body is not a buyer
    assert (n["buyer_country"], n["contract_nature"], n["procedure_type"]) == ("BE", "services", "open")
    assert (n["awarded_value"], n["awarded_value_currency"]) == (900000.0, "EUR")
    assert (n["cpv_main"], n["cpv_codes"]) == ("79311000", ["73210000", "79311000"])
    assert (n["title"], n["publication_date"], n["dispatch_date"]) == ("Study on example policies", "2025-06-02", "2025-05-28")
    assert (n["notice_uuid"], n["notice_version"], n["notice_subtype"]) == ("aaaaaaaa-0000-0000-0000-000000000001", "01", "can-standard")
    assert [(l["lot_id"], l["result"], l["tenders_received"]) for l in n["lots"]] == [
        ("LOT-0001", "selec-w", 3), ("LOT-0002", "selec-w", None), ("LOT-0003", "clos-nw", 0)]
    assert n["public_url"] == "https://ted.europa.eu/en/notice/-/detail/999999-2025"
    txt, page = ted_awards.compose_body(n)
    assert "Winner: Alpha Studies SL (ES), tender value 500,000.00 EUR, contract EX/2025/001, signed 2025-03-14" in txt
    assert "Result: closed, no winner chosen; tenders received: 0" in txt and "<h2>LOT-0003: Lot three</h2>" in page


LEGACY = """<?xml version="1.0" encoding="UTF-8"?><TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/publication" DOC_ID="888888-2024">
<CODED_DATA_SECTION><REF_OJS><DATE_PUB>20240223</DATE_PUB></REF_OJS></CODED_DATA_SECTION>
<FORM_SECTION>
<F03_2014 CATEGORY="ORIGINAL" FORM="F03" LG="FR"><CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY><OFFICIALNAME>Commission europeenne</OFFICIALNAME>
<COUNTRY VALUE="BE"/><URL_GENERAL>https://ec.europa.eu/info</URL_GENERAL></ADDRESS_CONTRACTING_BODY><CA_TYPE VALUE="EU_INSTITUTION"/></CONTRACTING_BODY>
<OBJECT_CONTRACT><TITLE><P>Etude</P></TITLE><CPV_MAIN><CPV_CODE CODE="79311000"/></CPV_MAIN><TYPE_CONTRACT CTYPE="SERVICES"/></OBJECT_CONTRACT>
<AWARD_CONTRACT ITEM="1"><AWARDED_CONTRACT><CONTRACTORS><CONTRACTOR><ADDRESS_CONTRACTOR><OFFICIALNAME>Zeta Partners</OFFICIALNAME><COUNTRY VALUE="FR"/></ADDRESS_CONTRACTOR></CONTRACTOR></CONTRACTORS></AWARDED_CONTRACT></AWARD_CONTRACT>
</F03_2014>
<F03_2014 CATEGORY="TRANSLATION" FORM="F03" LG="EN"><CONTRACTING_BODY><ADDRESS_CONTRACTING_BODY><OFFICIALNAME>European Commission, DG EXAMPLE</OFFICIALNAME>
<TOWN>Brussels</TOWN><COUNTRY VALUE="BE"/><E_MAIL>example@ec.europa.eu</E_MAIL><URL_GENERAL>https://ec.europa.eu/info</URL_GENERAL></ADDRESS_CONTRACTING_BODY>
<CA_TYPE VALUE="EU_INSTITUTION"/></CONTRACTING_BODY>
<OBJECT_CONTRACT><TITLE><P>Study on</P><P>examples</P></TITLE><CPV_MAIN><CPV_CODE CODE="79311000"/></CPV_MAIN><TYPE_CONTRACT CTYPE="SERVICES"/>
<SHORT_DESCR><P>First paragraph.</P><P>Second paragraph.</P></SHORT_DESCR><VAL_TOTAL CURRENCY="EUR">750000.00</VAL_TOTAL>
<OBJECT_DESCR ITEM="1"><LOT_NO>1</LOT_NO><TITLE><P>Lot one</P></TITLE><CPV_ADDITIONAL><CPV_CODE CODE="73210000"/></CPV_ADDITIONAL></OBJECT_DESCR></OBJECT_CONTRACT>
<PROCEDURE><PT_OPEN/></PROCEDURE>
<AWARD_CONTRACT ITEM="1"><CONTRACT_NO>EX/2024/001</CONTRACT_NO><LOT_NO>1</LOT_NO><AWARDED_CONTRACT><DATE_CONCLUSION_CONTRACT>2024-01-31</DATE_CONCLUSION_CONTRACT>
<TENDERS><NB_TENDERS_RECEIVED>4</NB_TENDERS_RECEIVED></TENDERS>
<CONTRACTORS><AWARDED_TO_GROUP/>
<CONTRACTOR><ADDRESS_CONTRACTOR><OFFICIALNAME>Zeta Partners</OFFICIALNAME><NATIONALID>FR12345678901</NATIONALID><TOWN>Paris</TOWN><COUNTRY VALUE="FR"/></ADDRESS_CONTRACTOR><SME/></CONTRACTOR>
<CONTRACTOR><ADDRESS_CONTRACTOR><OFFICIALNAME>Eta Ingenieria SL</OFFICIALNAME><NATIONALID>HRB 1234</NATIONALID><COUNTRY VALUE="ES"/></ADDRESS_CONTRACTOR><NO_SME/></CONTRACTOR>
</CONTRACTORS><VALUES><VAL_TOTAL CURRENCY="EUR">700000.00</VAL_TOTAL></VALUES></AWARDED_CONTRACT></AWARD_CONTRACT>
<AWARD_CONTRACT ITEM="2"><LOT_NO>2</LOT_NO><NO_AWARDED_CONTRACT><PROCUREMENT_UNSUCCESSFUL/></NO_AWARDED_CONTRACT></AWARD_CONTRACT>
<COMPLEMENTARY_INFO><DATE_DISPATCH_NOTICE>2024-02-20</DATE_DISPATCH_NOTICE></COMPLEMENTARY_INFO>
</F03_2014></FORM_SECTION></TED_EXPORT>"""


def test_the_legacy_award_forms_are_read_too():
    # EU bodies kept filing pre-eForms forms into 2024: 69 of 79 candidates in February 2024.
    n = ted_awards.parse_award(LEGACY, "888888-2024")
    assert (n["title"], n["description"]) == ("Study on examples", "First paragraph.\nSecond paragraph.")   # the English version
    assert (n["publication_date"], n["dispatch_date"], n["notice_subtype"]) == ("2024-02-23", "2024-02-20", "F03")
    assert (n["procedure_type"], n["contract_nature"], n["cpv_codes"]) == ("open", "services", ["73210000", "79311000"])
    assert (n["awarded_value"], n["buyer_legal_type"], n["contracting_authority"]) == (750000.0, "EU_INSTITUTION", "European Commission, DG EXAMPLE")
    assert [(l["lot_id"], l["title"], l["result"], l["tenders_received"]) for l in n["lots"]] == [
        ("1", "Lot one", "selec-w", 4), ("2", None, "clos-nw", None)]
    assert [(w["name"], w["country"], w["vat_key"], w["size"], w["group_size"], w["tender_value"], w["contract_date"],
             w["contract_reference"], w["org_ref"]) for w in n["winners"]] == [
        ("Zeta Partners", "FR", "FR12345678901", "sme", 2, 700000.0, "2024-01-31", "EX/2024/001", "AC-1-1"),
        ("Eta Ingenieria SL", "ES", None, "large", 2, 700000.0, "2024-01-31", "EX/2024/001", "AC-1-2")]
    national = LEGACY.replace("https://ec.europa.eu/info", "https://www.gov.si/").replace("example@ec.europa.eu", "x@gov.si")
    assert ted_awards.parse_award(national, "888888-2024") is None


def test_a_company_id_joins_the_vat_numbers_only_when_it_is_shaped_like_its_countrys_vat():
    assert vat_number("ESB67524405", "ES") == "ESB67524405" and vat_number("B67524405", "ES") == "ESB67524405"
    assert vat_number("FR 73 885 324 129", "FR") == "FR73885324129" and vat_number("29204055", "DK") == "DK29204055"
    assert vat_number("GR094014201", "GR") == "EL094014201" and vat_number("GB123456789", "UK") == "GB123456789"
    assert vat_number("NIP 5260250995", "PL") == "PL5260250995" and vat_number("12345678-2-41", "HU") == "HU12345678"
    for not_a_vat, cc in [("J03/610/2003", "RO"), ("Mercantile Register of Madrid, Volume 36", "ES"),
                          ("DE233022928", "FR"), ("6000138991", "UK"), ("12345", "DE"), (None, "DE"), ("DE123456789", None)]:
        assert vat_number(not_a_vat, cc) is None, not_a_vat
    assert [alpha3_code(c) for c in ("GRC", "GBR", "ESP", "ZZZ", None)] == ["EL", "UK", "ES", None, None]


def test_the_search_only_lists_candidates_with_an_eu_body_address():
    pages = [{"notices": [{"publication-number": "1-2025", "buyer-internet-address": ["https://www.gov.si/"]},
                          {"publication-number": "2-2025", "buyer-email": ["proc@eea.europa.eu"]}],
              "iterationNextToken": "t"},
             {"notices": [{"publication-number": "3-2025", "buyer-internet-address": ["https://www.eib.org"]}]}]
    sent = []

    class _Session:
        def post(self, url, json, timeout):
            sent.append(json)
            return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: pages[len(sent) - 1])

    assert list(ted_awards.search_awards(_Session(), date(2025, 1, 1), date(2025, 1, 31))) == ["2-2025", "3-2025"]
    assert "publication-date>=20250101 AND publication-date<=20250131" in sent[0]["query"]
    assert "buyer-legal-type=eu-ins-bod-ag" in sent[0]["query"] and 'buyer-email~"europa.eu"' in sent[0]["query"]
    assert sent[1]["iterationNextToken"] == "t"


# --- the loader -------------------------------------------------------------------------------------- #

class _Cur:
    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self):
        self.log, self.commits = [], 0

    def cursor(self):
        return _Cur(self.log)

    def commit(self):
        self.commits += 1


def test_the_loader_writes_the_notice_its_winners_and_drops_winners_no_longer_read(monkeypatch):
    sta = importlib.import_module("sync_ted_awards")
    batches = []
    monkeypatch.setattr(sta.psycopg2.extras, "execute_values", lambda cur, sql, rows: batches.append((sql, rows)))
    conn = _Conn()
    n = ted_awards.parse_award(_notice(), "999999-2025")
    sta.store(conn, n, {"eea.europa.eu": "eea"})
    (notice_sql, notice_params), (delete_sql, delete_params) = conn.log
    assert notice_sql.count("%s") == len(notice_params) == len(sta.NOTICE_COLUMNS) + 1
    values = dict(zip(("publication_number",) + sta.NOTICE_COLUMNS, notice_params))
    assert values["body_code"] == "commission" and values["winner_count"] == 4 and values["lot_count"] == 3
    assert "Winner: Delta Consult (DK)" in values["body_txt"]
    sql, rows = batches[0]
    assert len(rows) == 4 and all(len(r) == len(sta.WINNER_COLUMNS) + 3 for r in rows)
    assert "ON CONFLICT (publication_number, tender_id, org_ref)" in sql
    assert " ".join(delete_sql.split()) == ("DELETE FROM ted_award_winners WHERE publication_number = %s "
                                            "AND tender_id || '/' || org_ref <> ALL(%s)")
    assert delete_params == ("999999-2025", ["TEN-0001/ORG-0003", "TEN-0001/ORG-0004", "TEN-0002/ORG-0005", "TEN-0003/ORG-0006"])
    assert conn.commits == 1                                                            # one notice, one transaction


def test_the_buyer_is_named_as_a_brubru_body_from_its_web_address():
    sta = importlib.import_module("sync_ted_awards")
    by_host = {"eea.europa.eu": "eea", "hadea.ec.europa.eu": "hadea", "eib.org": "eib", "europarl.europa.eu": "parliament"}
    of = lambda site: sta.body_code_of({"buyers": [{"website": site}]}, by_host)  # noqa: E731
    assert of("https://www.eea.europa.eu/en") == "eea" and of("https://hadea.ec.europa.eu") == "hadea"
    assert of("http://ec.europa.eu/environment") == "commission" and of("https://joint-research-centre.ec.europa.eu") == "commission"
    assert of("https://www.eib.org") == "eib" and of("https://unknown.europa.eu") is None
    assert of("https://the-secretary-general.europarl.europa.eu/x") == "parliament"
    assert sta.body_code_of({"buyers": [{"website": None, "email": "procurement@eea.europa.eu"}]}, by_host) == "eea"
    # The lead buyer names the body, by its web address and else its e-mail; never a co-buyer.
    joint = {"buyers": [{"website": "https://industryportal.f4e.europa.eu/", "email": "tenders@f4e.europa.eu"},
                        {"website": None, "email": "procurement@eea.europa.eu"}]}
    assert sta.body_code_of(joint, dict(by_host, **sta.HOST_ALIASES)) == "f4e"
    assert sta.body_code_of({"buyers": joint["buyers"][:1] + joint["buyers"][1:]}, by_host) is None
    platform = {"buyers": [{"website": "https://s2c.mercell.com/buyer/1", "email": "COMM-B3@ec.europa.eu"}]}
    assert sta.body_code_of(platform, by_host) == "commission"
    aliases = sta.body_codes(SimpleNamespace(execute=lambda *a: None, fetchall=lambda: []))
    assert aliases["f4e.europa.eu"] == "f4e" and aliases["emcdda.europa.eu"] == "euda"
    assert sta.body_code_of({"buyers": [{"website": "www.emcdda.europa.eu"}]}, aliases) == "euda"
    # A later version of a notice supersedes the earlier one; the current one points nowhere.
    assert "DISTINCT ON (notice_uuid)" in sta.SUPERSEDE and "notice_version DESC" in sta.SUPERSEDE
    assert "nullif(l.publication_number, n.publication_number)" in sta.SUPERSEDE


# --- the routes -------------------------------------------------------------------------------------- #

class _Db:
    def __init__(self, notice=None):
        self.calls, self.notice = [], notice

    def execute(self, stmt, params=None):
        self.calls.append((str(stmt), dict(params or {})))
        sql = str(stmt)
        if "FROM ted_award_winners w LEFT JOIN funding_org_identities" in sql:
            rows = [{"publication_number": "999999-2025", "name": "Delta Consult", "country": "DK", "city": "Town",
                     "company_id": "29200000", "vat_key": "DK29200000", "size": "micro", "lot_id": "LOT-0002",
                     "lot_title": "Lot two", "rank": 2, "is_group_lead": False, "group_size": 1, "tender_value": 0,
                     "tender_value_currency": "EUR", "contract_reference": "EX/2025/002-2", "contract_title": None,
                     "contract_date": date(2025, 3, 21), "award_date": None, "pic": None, "slug": "delta-consult",
                     "is_partner": True},
                    {"publication_number": "999999-2025", "name": "Gamma Analytics", "country": "EL", "city": "Town",
                     "company_id": None, "vat_key": None, "size": None, "lot_id": "LOT-0002", "lot_title": None,
                     "rank": 1, "is_group_lead": False, "group_size": 1, "tender_value": None, "tender_value_currency": None,
                     "contract_reference": None, "contract_title": None, "contract_date": None, "award_date": None,
                     "pic": None, "slug": "gamma-analytics", "is_partner": True},
                    {"publication_number": "999999-2025", "name": "DOE Jane", "country": "BE", "city": "Town",
                     "company_id": None, "vat_key": None, "size": "micro", "lot_id": "LOT-0002", "lot_title": None,
                     "rank": 1, "is_group_lead": False, "group_size": 2, "tender_value": None, "tender_value_currency": None,
                     "contract_reference": None, "contract_title": None, "contract_date": None, "award_date": None,
                     "pic": None, "slug": "doe-jane", "is_partner": False}]
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))
        return SimpleNamespace(scalar=lambda: 0, fetchall=lambda: [], fetchone=lambda: self.notice)


def _client(db):
    from api.v2.funding import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_the_award_list_filters_on_the_notice_and_its_winners():
    db = _Db()
    r = _client(db).get("/api/v2/funding/tender-awards", params={
        "q": "example study", "contracting_authority": "CNECT", "winner": "Delta", "winner_country": "GR",
        "cpv_code": "7931", "since": "2025-01-01", "min_amount_eur": 100000, "body": "Commission"})
    assert r.status_code == 200, r.text
    sql, params = db.calls[-1]
    assert "n.superseded_by IS NULL" in sql and "websearch_to_tsquery('english', :q)" in sql
    assert "to_tsvector('english', coalesce(n.title, '') || ' ' || coalesce(n.description, ''))" in sql   # the index's expression
    assert params["ca"] == "%CNECT%" and params["winner"] == "%Delta%" and params["wc"] == "EL"
    assert params["cpv"] == "7931%" and params["start"] == date(2025, 1, 1) and params["body"] == "commission"
    assert "upper(n.awarded_value_currency) = 'EUR'" in sql
    assert _client(_Db()).get("/api/v2/funding/tender-awards", params={"order": "random"}).status_code == 400
    db = _Db()
    _client(db).get("/api/v2/funding/tender-awards", params={"include_superseded": "true"})
    assert "superseded_by IS NULL" not in db.calls[-1][0]


def test_an_award_item_lists_its_winners_with_their_partner_link():
    row = SimpleNamespace(publication_number="999999-2025", notice_uuid="u", notice_version="01", procedure_uuid="p",
                          notice_subtype="can-standard", superseded_by=None, publication_date=date(2025, 6, 2),
                          title="Study", description="A study.", contract_nature="services", procedure_type="open",
                          cpv_main="79311000", cpv_codes=["79311000"], body_code="commission", body_name="European Commission",
                          contracting_authority="European Commission, DG EXAMPLE", buyer_country="BE",
                          buyer_legal_type="eu-ins-bod-ag", awarded_value=900000, awarded_value_currency="EUR",
                          lots=[{"lot_id": "LOT-0002"}], lot_count=1, winner_count=2, public_url="https://ted.europa.eu/x",
                          first_seen=None, last_updated=None, body_txt="t", body_html="<p>t</p>")
    r = _client(_Db(notice=row)).get("/api/v2/funding/tender-awards/999999-2025")
    assert r.status_code == 200, r.text
    item = r.json()
    assert (item["id"], item["item_type"], item["form_type"], item["amount_eur"]) == ("999999-2025", "tender_award", "result", 900000.0)
    # A winner that may be an individual is listed as TED names it, with no partner link.
    assert [(o["partner"] or "").split("/partners/")[-1] for o in item["organisations"]] == [
        "vat:DK29200000", "name:el:gamma-analytics", ""]
    assert item["organisations"][0]["role"] == "contractor" and item["body_txt"] == "t"
    assert _client(_Db()).get("/api/v2/funding/tender-awards/1-2025").status_code == 404


def test_partners_take_the_awards_as_contractor_activities():
    from api.v2.funding import partners
    db = _Db()
    r = _client(db).get("/api/v2/funding/partners", params={"q": "legal translation", "dg": "CNECT", "since": "2025-01-01"})
    assert r.status_code == 200, r.text
    sql, params = db.calls[-1]
    assert "FROM ted_award_winners w JOIN ted_award_notices n" in sql and "n.superseded_by IS NULL" in sql
    assert f"n.superseded_by IS NULL AND {partners.AWARD_WINNER_IS_ORGANISATION}" in sql   # no person profiles
    assert "n.contracting_authority ILIKE :dg" in sql and "coalesce(w.contract_date, n.publication_date) >= :since" in sql
    assert "'award' AS kind" in sql and "count(DISTINCT ref) FILTER (WHERE kind = 'award') AS awards" in sql
    # An award has no programme, topic, activity type or SME flag: asking for one leaves the awards out.
    for extra in ({"programme": "LIFE"}, {"topic": "HORIZON"}, {"activity_type": "REC"}, {"is_sme": "true"}):
        db = _Db()
        _client(db).get("/api/v2/funding/partners", params={"q": "ai", **extra})
        assert "ted_award_winners" not in db.calls[-1][0], extra
    db = _Db()
    _client(db).get("/api/v2/funding/partners", params={"q": "ai", "source": "awards"})
    sql = db.calls[-1][0]
    assert "ted_award_winners" in sql and "FROM fts_commitments c" not in sql and "jsonb_array_elements(pr.organisations)" not in sql
    # The item route reaches an organisation's awards by its PIC, VAT number or name.
    db = _Db()
    _client(db).get("/api/v2/funding/partners/name:dk:delta-consult")
    assert "w.country = :key_cc AND regexp_replace(lower(w.name)" in db.calls[-1][0]
    db = _Db()
    _client(db).get("/api/v2/funding/partners/vat:DK29200000")
    assert "w.vat_key = :key_val" in db.calls[-1][0] and db.calls[-1][1]["key_val"] == "DK29200000"
    db = _Db()
    _client(db).get("/api/v2/funding/partners/pic:999991722")
    assert "w.vat_key IN (SELECT vat_key FROM funding_org_identities WHERE pic = :key_val)" in db.calls[-1][0]
    r = SimpleNamespace(key="vat:DK29200000", pic=None, vat="DK29200000", name="Delta Consult", short_name=None, country="DK",
                        city="Town", activity_type=None, is_sme=None, projects=0, coordinated=0, payments=0, contracts=0,
                        awards=1, eu_contribution=None, amount_eur=None, last_day=None, created=None, changed=None,
                        matches=[{"kind": "award", "id": "999999-2025", "title": "Study: Lot two", "role": "contractor",
                                  "programme": None, "date": "2025-03-21", "department": "European Commission, DG EXAMPLE",
                                  "eu_contribution": None, "amount_eur": None, "tender_value_eur": 0}])
    item = partners._item(r, "https://h")
    assert item.matches[0].self == "https://h/api/v2/funding/tender-awards/999999-2025" and item.awards == 1
    assert "Matching TED contract awards won: 1" in item.body_txt


def test_the_award_sync_runs_daily_and_is_recorded_by_the_tier():
    from api import cron
    assert "ted_awards" in cron._DAILY_TIER_RECORDED
    assert '"ted_awards", "scripts/sync_ted_awards.py", ["--apply"]' in pathlib.Path(cron.__file__).read_text()


def test_an_award_winner_is_a_partner_by_its_vat_number_or_its_legal_form():
    from api.v2.funding import partners
    from api.v2.funding import tender_awards
    rule = partners.AWARD_WINNER_IS_ORGANISATION
    assert "w.vat_key IN (SELECT vat_key FROM funding_org_identities)" in rule
    assert "beneficiary_type IS DISTINCT FROM 'Private Persons'" in rule
    assert tender_awards.AWARD_WINNER_IS_ORGANISATION is rule                     # one rule for both routes
    # The pattern is PostgreSQL's (\m, \M: a word's start and end); read here with Python's \b.
    form = re.compile(partners.AWARD_ORG_FORM.replace(r"\m", r"\b").replace(r"\M", r"\b"), re.I)
    organisations = ["Alpha Studies SL", "Beta Research GmbH", "Delta Consult", "Epsilon S.r.l.", "Zeta Institute",
                     "Eta Sp. z o.o.", "Theta B.V.", "Iota A/S", "Kappa University", "Lambda Foundation"]
    people = ["DOE Jane", "Jane Doe", "Maria Example Person", "SMITH JOHN ROBERT"]
    assert [n for n in organisations if not form.search(n)] == []
    assert [n for n in people if form.search(n)] == []
