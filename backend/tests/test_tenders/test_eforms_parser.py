"""
eForms Parser Unit Tests

Tests for parsing EU procurement notices in both eForms and legacy TED XML formats.
"""

import pytest
from datetime import datetime

from backend.services.tenders.eforms_parser import EFormsParser


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def parser():
    """Create an eForms parser instance"""
    return EFormsParser()


@pytest.fixture
def sample_eforms_xml():
    """Sample eForms XML (simplified)"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2"
                    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:ID>CN-001</cbc:ID>
        <cbc:UUID>12345-abcde-67890</cbc:UUID>
        <cbc:IssueDate>2024-01-15</cbc:IssueDate>
        <cbc:NoticeTypeCode>cn-standard</cbc:NoticeTypeCode>
        <cac:ContractingParty>
            <cac:Party>
                <cac:PartyName>
                    <cbc:Name>City of Brussels</cbc:Name>
                </cac:PartyName>
                <cac:Country>
                    <cbc:IdentificationCode>BE</cbc:IdentificationCode>
                </cac:Country>
            </cac:Party>
        </cac:ContractingParty>
        <cac:ProcurementProject>
            <cbc:Name>IT Infrastructure Upgrade</cbc:Name>
            <cbc:Description>Upgrade of IT infrastructure for municipal offices</cbc:Description>
            <cbc:ProcurementTypeCode>services</cbc:ProcurementTypeCode>
            <cac:MainCommodityClassification>
                <cbc:ItemClassificationCode>72000000</cbc:ItemClassificationCode>
            </cac:MainCommodityClassification>
            <cac:RequestedTenderTotal>
                <cbc:EstimatedOverallContractAmount currencyID="EUR">500000</cbc:EstimatedOverallContractAmount>
            </cac:RequestedTenderTotal>
        </cac:ProcurementProject>
        <cac:TenderingProcess>
            <cbc:ProcedureCode>open</cbc:ProcedureCode>
            <cac:TenderSubmissionDeadlinePeriod>
                <cbc:EndDate>2024-03-15</cbc:EndDate>
                <cbc:EndTime>12:00:00</cbc:EndTime>
            </cac:TenderSubmissionDeadlinePeriod>
        </cac:TenderingProcess>
    </ContractNotice>
    """


@pytest.fixture
def sample_legacy_xml():
    """Sample legacy TED XML (F02 Contract Notice)"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception">
        <DOC_ID>2024-12345</DOC_ID>
        <NO_DOC_OJS>12345-2024</NO_DOC_OJS>
        <FORM_SECTION>
            <F02_2014>
                <CONTRACTING_BODY>
                    <OFFICIALNAME>Ville de Paris</OFFICIALNAME>
                    <TOWN>Paris</TOWN>
                    <POSTAL_CODE>75001</POSTAL_CODE>
                    <COUNTRY VALUE="FR"/>
                    <E_MAIL>procurement@paris.fr</E_MAIL>
                </CONTRACTING_BODY>
                <OBJECT_CONTRACT>
                    <TITLE><P>Public Transport System Modernization</P></TITLE>
                    <SHORT_DESCR><P>Modernization of the public transport ticketing system</P></SHORT_DESCR>
                    <TYPE_CONTRACT CTYPE="SERVICES"/>
                    <CPV_MAIN>
                        <CPV_CODE CODE="63712100"/>
                    </CPV_MAIN>
                    <CPV_ADDITIONAL>
                        <CPV_CODE CODE="72000000"/>
                    </CPV_ADDITIONAL>
                    <NUTS CODE="FR101"/>
                </OBJECT_CONTRACT>
                <PROCEDURE>
                    <PT_OPEN/>
                </PROCEDURE>
                <VAL_ESTIMATED_TOTAL CURRENCY="EUR">2500000</VAL_ESTIMATED_TOTAL>
                <DATE_RECEIPT_TENDERS>2024-04-30</DATE_RECEIPT_TENDERS>
                <TIME_RECEIPT_TENDERS>14:00</TIME_RECEIPT_TENDERS>
            </F02_2014>
        </FORM_SECTION>
    </TED_EXPORT>
    """


@pytest.fixture
def sample_legacy_with_lots_xml():
    """Sample legacy TED XML with lots"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception">
        <FORM_SECTION>
            <F02_2014>
                <CONTRACTING_BODY>
                    <OFFICIALNAME>European Commission</OFFICIALNAME>
                    <COUNTRY VALUE="BE"/>
                </CONTRACTING_BODY>
                <OBJECT_CONTRACT>
                    <TITLE><P>IT Framework Contract</P></TITLE>
                    <TYPE_CONTRACT CTYPE="SERVICES"/>
                    <CPV_MAIN>
                        <CPV_CODE CODE="72000000"/>
                    </CPV_MAIN>
                    <OBJECT_DESCR>
                        <LOT_NO>1</LOT_NO>
                        <TITLE><P>Software Development</P></TITLE>
                        <SHORT_DESCR><P>Custom software development services</P></SHORT_DESCR>
                        <CPV_MAIN>
                            <CPV_CODE CODE="72200000"/>
                        </CPV_MAIN>
                        <VAL_OBJECT CURRENCY="EUR">1000000</VAL_OBJECT>
                    </OBJECT_DESCR>
                    <OBJECT_DESCR>
                        <LOT_NO>2</LOT_NO>
                        <TITLE><P>IT Consulting</P></TITLE>
                        <SHORT_DESCR><P>IT consulting and advisory services</P></SHORT_DESCR>
                        <CPV_MAIN>
                            <CPV_CODE CODE="72220000"/>
                        </CPV_MAIN>
                        <VAL_OBJECT CURRENCY="EUR">500000</VAL_OBJECT>
                    </OBJECT_DESCR>
                </OBJECT_CONTRACT>
                <PROCEDURE>
                    <PT_RESTRICTED/>
                </PROCEDURE>
            </F02_2014>
        </FORM_SECTION>
    </TED_EXPORT>
    """


# ============================================================================
# Format Detection Tests
# ============================================================================

class TestFormatDetection:
    """Tests for XML format detection"""

    def test_detect_eforms_format(self, parser, sample_eforms_xml):
        """Test detection of eForms XML format"""
        assert not parser._is_legacy_format(sample_eforms_xml)

    def test_detect_legacy_format(self, parser, sample_legacy_xml):
        """Test detection of legacy TED XML format"""
        assert parser._is_legacy_format(sample_legacy_xml)

    def test_detect_legacy_by_ted_export(self, parser):
        """Test detection by TED_EXPORT tag"""
        xml = '<TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception"></TED_EXPORT>'
        assert parser._is_legacy_format(xml)

    def test_detect_legacy_by_form_section(self, parser):
        """Test detection by FORM_SECTION tag"""
        xml = '<root><FORM_SECTION><F02_2014></F02_2014></FORM_SECTION></root>'
        assert parser._is_legacy_format(xml)


# ============================================================================
# eForms Parsing Tests
# ============================================================================

class TestEFormsParsing:
    """Tests for eForms XML parsing"""

    def test_parse_eforms_basic(self, parser, sample_eforms_xml):
        """Test basic eForms parsing"""
        result = parser.parse(sample_eforms_xml)

        assert result["notice_type"] == "competition"
        assert result["notice_id"] == "CN-001"
        assert result["uuid"] == "12345-abcde-67890"

    def test_parse_eforms_buyer(self, parser, sample_eforms_xml):
        """Test buyer extraction from eForms"""
        result = parser.parse(sample_eforms_xml)

        assert result["official_name"] == "City of Brussels"
        assert result["buyer_country"] == "BE"

    def test_parse_eforms_procedure(self, parser, sample_eforms_xml):
        """Test procedure extraction from eForms"""
        result = parser.parse(sample_eforms_xml)

        assert result["procedure_type"] == "open"

    def test_parse_eforms_cpv(self, parser, sample_eforms_xml):
        """Test CPV code extraction from eForms"""
        result = parser.parse(sample_eforms_xml)

        assert result["cpv_main"] == "72000000"
        assert "72000000" in result["cpv_codes"]

    def test_parse_eforms_value(self, parser, sample_eforms_xml):
        """Test value extraction from eForms"""
        result = parser.parse(sample_eforms_xml)

        assert result["estimated_value"] == 500000
        assert result["estimated_value_currency"] == "EUR"

    def test_parse_eforms_dates(self, parser, sample_eforms_xml):
        """Test date extraction from eForms"""
        result = parser.parse(sample_eforms_xml)

        assert result["submission_deadline_date"] == "2024-03-15"
        assert result["submission_deadline_time"] == "12:00:00"


# ============================================================================
# Legacy TED Parsing Tests
# ============================================================================

class TestLegacyTEDParsing:
    """Tests for legacy TED XML parsing"""

    def test_parse_legacy_basic(self, parser, sample_legacy_xml):
        """Test basic legacy TED parsing"""
        result = parser.parse(sample_legacy_xml)

        assert result["notice_type"] == "legacy"
        assert result["form_type"] == "F02"

    def test_parse_legacy_identifiers(self, parser, sample_legacy_xml):
        """Test identifier extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["notice_id"] == "2024-12345"
        assert result["publication_number"] == "12345-2024"

    def test_parse_legacy_buyer(self, parser, sample_legacy_xml):
        """Test buyer extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["official_name"] == "Ville de Paris"
        assert result["buyer_country"] == "FR"
        assert result["buyer_city"] == "Paris"
        assert result["buyer_postal_code"] == "75001"
        assert result["buyer_email"] == "procurement@paris.fr"

    def test_parse_legacy_object(self, parser, sample_legacy_xml):
        """Test object extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["title"] == "Public Transport System Modernization"
        assert "Modernization" in result["description"]
        assert result["contract_nature"] == "services"

    def test_parse_legacy_procedure(self, parser, sample_legacy_xml):
        """Test procedure extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["procedure_type"] == "open"

    def test_parse_legacy_cpv(self, parser, sample_legacy_xml):
        """Test CPV extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["cpv_main"] == "63712100"
        assert "63712100" in result["cpv_codes"]
        assert "72000000" in result["cpv_codes"]

    def test_parse_legacy_nuts(self, parser, sample_legacy_xml):
        """Test NUTS extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert "FR101" in result["nuts_codes"]

    def test_parse_legacy_value(self, parser, sample_legacy_xml):
        """Test value extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["estimated_value"] == 2500000
        assert result["estimated_value_currency"] == "EUR"

    def test_parse_legacy_dates(self, parser, sample_legacy_xml):
        """Test date extraction from legacy TED"""
        result = parser.parse(sample_legacy_xml)

        assert result["submission_deadline_date"] == "2024-04-30"
        assert result["submission_deadline_time"] == "14:00"


# ============================================================================
# Lots Parsing Tests
# ============================================================================

class TestLotsParsing:
    """Tests for lot extraction"""

    def test_parse_legacy_lots(self, parser, sample_legacy_with_lots_xml):
        """Test lot extraction from legacy TED"""
        result = parser.parse(sample_legacy_with_lots_xml)

        assert result["has_lots"] is True
        assert result["lot_count"] == 2
        assert len(result["lots"]) == 2

    def test_parse_legacy_lot_details(self, parser, sample_legacy_with_lots_xml):
        """Test lot detail extraction"""
        result = parser.parse(sample_legacy_with_lots_xml)
        lots = result["lots"]

        # First lot
        lot1 = lots[0]
        assert lot1["lot_id"] == "1"
        assert lot1["title"] == "Software Development"
        assert lot1["cpv_code"] == "72200000"
        assert lot1["estimated_value"] == 1000000

        # Second lot
        lot2 = lots[1]
        assert lot2["lot_id"] == "2"
        assert lot2["title"] == "IT Consulting"
        assert lot2["estimated_value"] == 500000


# ============================================================================
# Form Type Detection Tests
# ============================================================================

class TestFormTypeDetection:
    """Tests for legacy form type detection"""

    def test_detect_f01(self, parser):
        """Test F01 detection"""
        xml = "<root><F01_2014></F01_2014></root>"
        assert parser._detect_legacy_form_type(xml) == "F01"

    def test_detect_f02(self, parser):
        """Test F02 detection"""
        xml = "<root><F02_2014></F02_2014></root>"
        assert parser._detect_legacy_form_type(xml) == "F02"

    def test_detect_f03(self, parser):
        """Test F03 detection"""
        xml = "<root><F03_2014></F03_2014></root>"
        assert parser._detect_legacy_form_type(xml) == "F03"

    def test_detect_f14_corrigendum(self, parser):
        """Test F14 (Corrigendum) detection"""
        xml = "<root><F14_2014></F14_2014></root>"
        assert parser._detect_legacy_form_type(xml) == "F14"

    def test_detect_f20_modification(self, parser):
        """Test F20 (Modification) detection"""
        xml = "<root><F20_2014></F20_2014></root>"
        assert parser._detect_legacy_form_type(xml) == "F20"

    def test_detect_unknown_form(self, parser):
        """Test unknown form type"""
        xml = "<root><UNKNOWN></UNKNOWN></root>"
        assert parser._detect_legacy_form_type(xml) == "unknown"


# ============================================================================
# Procedure Type Tests
# ============================================================================

class TestProcedureTypeExtraction:
    """Tests for procedure type extraction"""

    def test_legacy_open_procedure(self, parser):
        """Test open procedure detection"""
        xml = """<TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception">
            <FORM_SECTION><F02_2014>
                <CONTRACTING_BODY><COUNTRY VALUE="BE"/></CONTRACTING_BODY>
                <PROCEDURE><PT_OPEN/></PROCEDURE>
            </F02_2014></FORM_SECTION>
        </TED_EXPORT>"""
        result = parser.parse(xml)
        assert result["procedure_type"] == "open"

    def test_legacy_restricted_procedure(self, parser):
        """Test restricted procedure detection"""
        xml = """<TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception">
            <FORM_SECTION><F02_2014>
                <CONTRACTING_BODY><COUNTRY VALUE="BE"/></CONTRACTING_BODY>
                <PROCEDURE><PT_RESTRICTED/></PROCEDURE>
            </F02_2014></FORM_SECTION>
        </TED_EXPORT>"""
        result = parser.parse(xml)
        assert result["procedure_type"] == "restricted"

    def test_legacy_competitive_dialogue(self, parser):
        """Test competitive dialogue detection"""
        xml = """<TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/reception">
            <FORM_SECTION><F02_2014>
                <CONTRACTING_BODY><COUNTRY VALUE="BE"/></CONTRACTING_BODY>
                <PROCEDURE><PT_COMPETITIVE_DIALOGUE/></PROCEDURE>
            </F02_2014></FORM_SECTION>
        </TED_EXPORT>"""
        result = parser.parse(xml)
        assert result["procedure_type"] == "comp-dial"


# ============================================================================
# parse_to_tender_dict Tests
# ============================================================================

class TestParseTenderDict:
    """Tests for parse_to_tender_dict method"""

    def test_parse_to_tender_dict(self, parser, sample_eforms_xml):
        """Test conversion to Tender model dictionary"""
        result = parser.parse_to_tender_dict(sample_eforms_xml, "12345-2024")

        assert result["publication_number"] == "12345-2024"
        assert result["official_name"] == "City of Brussels"
        assert result["buyer_country"] == "BE"
        assert result["cpv_main"] == "72000000"
        assert result["xml_content"] == sample_eforms_xml
        assert "raw_json" in result


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling"""

    def test_invalid_xml(self, parser):
        """Test handling of invalid XML"""
        result = parser.parse("not valid xml")
        assert result == {}

    def test_empty_xml(self, parser):
        """Test handling of empty XML"""
        result = parser.parse("")
        assert result == {}

    def test_minimal_xml(self, parser):
        """Test handling of minimal valid XML"""
        result = parser.parse("<root></root>")
        assert result.get("notice_type") == "unknown"
