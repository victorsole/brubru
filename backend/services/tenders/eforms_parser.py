"""
eForms XML Parser

Parses EU procurement notices in eForms XML format.
Also supports legacy TED XML format for historical notices.

Based on eForms SDK v1.14 field definitions.
Reference: https://docs.ted.europa.eu/eforms/latest/index.html

UBL Namespaces (eForms):
- cac: urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2
- cbc: urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2
- ext: urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2
- efac: http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1
- efbc: http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1

Legacy TED XML Namespaces:
- ted: http://publications.europa.eu/resource/schema/ted/R2.0.9/reception
"""

import logging
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from pathlib import Path
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# XML Namespaces for eForms (new format)
EFORMS_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "efac": "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1",
    "efbc": "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1",
    "efext": "http://data.europa.eu/p27/eforms-ubl-extensions/1",
    "pin": "urn:oasis:names:specification:ubl:schema:xsd:PriorInformationNotice-2",
    "cn": "urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2",
    "can": "urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2",
}

# XML Namespaces for Legacy TED format (pre-eForms)
LEGACY_TED_NS = {
    "ted": "http://publications.europa.eu/resource/schema/ted/R2.0.9/reception",
    "n2016": "http://publications.europa.eu/resource/schema/ted/2016/nuts",
    "n2021": "http://publications.europa.eu/resource/schema/ted/2021/nuts",
}


class EFormsParser:
    """
    Parser for eForms XML notices.

    Extracts structured data from EU procurement notices following
    the eForms specification (eForms SDK 1.14).

    Example usage:
        parser = EFormsParser()
        tender_data = parser.parse(xml_content)

        # Or with fields reference
        parser = EFormsParser(fields_path="backend/knowledge_base/tenders/eforms/fields.json")
    """

    def __init__(self, fields_path: Optional[str] = None):
        """
        Initialize the eForms parser.

        Args:
            fields_path: Path to fields.json from eForms SDK (optional)
        """
        self.fields = None
        self.fields_by_id = {}

        if fields_path:
            self._load_fields(fields_path)

    def _load_fields(self, fields_path: str):
        """Load field definitions from eForms SDK"""
        try:
            path = Path(fields_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.fields = data.get("fields", [])

                    # Index by field ID for quick lookup
                    for field in self.fields:
                        self.fields_by_id[field.get("id")] = field

                    logger.info(f"Loaded {len(self.fields_by_id)} eForms field definitions")
        except Exception as e:
            logger.error(f"Failed to load eForms fields: {e}")

    def _is_legacy_format(self, xml_content: str) -> bool:
        """Check if XML is in legacy TED format (pre-eForms)."""
        # Legacy TED notices have different namespaces and structure
        legacy_indicators = [
            "publications.europa.eu/resource/schema/ted",
            "TED_EXPORT",
            "<FORM_SECTION>",
            "<F02_2014>",  # Contract Notice form
            "<F03_2014>",  # Contract Award Notice form
            "<F01_2014>",  # Prior Information Notice
        ]
        return any(indicator in xml_content for indicator in legacy_indicators)

    def parse(self, xml_content: str) -> Dict[str, Any]:
        """
        Parse XML content and extract tender data.
        Automatically detects eForms vs legacy TED format.

        Args:
            xml_content: Raw XML string

        Returns:
            Dictionary with extracted tender information
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            return {}

        # Check if this is legacy TED format
        if self._is_legacy_format(xml_content):
            logger.debug("Detected legacy TED XML format")
            return self._parse_legacy(root, xml_content)

        # eForms format (standard path)
        logger.debug("Detected eForms XML format")

        # Determine notice type from root element
        root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        notice_type = self._determine_notice_type(root_tag)

        # Extract all fields
        result = {
            "notice_type": notice_type,
            "raw_root_tag": root.tag,
        }

        # Core identifiers
        result.update(self._extract_identifiers(root))

        # Buyer/Contracting authority
        result.update(self._extract_buyer(root))

        # Procedure information
        result.update(self._extract_procedure(root))

        # Value and financial info
        result.update(self._extract_values(root))

        # Dates and deadlines
        result.update(self._extract_dates(root))

        # CPV codes and classification
        result.update(self._extract_classification(root))

        # Award criteria
        result.update(self._extract_award_criteria(root))

        # Lots (if any)
        result["lots"] = self._extract_lots(root)
        result["has_lots"] = len(result["lots"]) > 0
        result["lot_count"] = len(result["lots"])

        # Selection criteria and requirements
        result.update(self._extract_requirements(root))

        # Document references
        result.update(self._extract_documents(root))

        return result

    def _determine_notice_type(self, root_tag: str) -> str:
        """Determine the notice type from root element"""
        type_map = {
            "ContractNotice": "competition",
            "PriorInformationNotice": "planning",
            "ContractAwardNotice": "result",
            "ContractModificationNotice": "modification",
        }
        return type_map.get(root_tag, "unknown")

    def _find_text(
        self,
        element: ET.Element,
        xpath: str,
        default: Optional[str] = None
    ) -> Optional[str]:
        """Find text value at xpath"""
        found = element.find(xpath, EFORMS_NS)
        if found is not None and found.text:
            return found.text.strip()
        return default

    def _find_all_text(
        self,
        element: ET.Element,
        xpath: str
    ) -> List[str]:
        """Find all text values at xpath"""
        results = []
        for found in element.findall(xpath, EFORMS_NS):
            if found.text:
                results.append(found.text.strip())
        return results

    def _extract_identifiers(self, root: ET.Element) -> Dict[str, Any]:
        """Extract notice identifiers"""
        return {
            "notice_id": self._find_text(root, ".//cbc:ID"),
            "uuid": self._find_text(root, ".//cbc:UUID"),
            "issue_date": self._find_text(root, ".//cbc:IssueDate"),
            "issue_time": self._find_text(root, ".//cbc:IssueTime"),
            "notice_type_code": self._find_text(root, ".//cbc:NoticeTypeCode"),
            "regulatory_domain": self._find_text(root, ".//cbc:RegulatoryDomain"),
        }

    def _extract_buyer(self, root: ET.Element) -> Dict[str, Any]:
        """Extract contracting authority/buyer information"""
        buyer = {}

        # Find contracting party
        contracting_party = root.find(".//cac:ContractingParty", EFORMS_NS)
        if contracting_party is not None:
            party = contracting_party.find("cac:Party", EFORMS_NS)
            if party is not None:
                # Organization name
                org_name = party.find(".//cac:PartyName/cbc:Name", EFORMS_NS)
                if org_name is not None:
                    buyer["official_name"] = org_name.text.strip()

                # Country
                country = party.find(".//cac:Country/cbc:IdentificationCode", EFORMS_NS)
                if country is not None:
                    buyer["buyer_country"] = country.text.strip()

                # Address
                address = party.find(".//cac:PostalAddress", EFORMS_NS)
                if address is not None:
                    buyer["buyer_address"] = {
                        "street": self._find_text(address, "cbc:StreetName"),
                        "city": self._find_text(address, "cbc:CityName"),
                        "postal_code": self._find_text(address, "cbc:PostalZone"),
                        "country": self._find_text(address, "cac:Country/cbc:IdentificationCode"),
                    }

                # Contact
                contact = party.find(".//cac:Contact", EFORMS_NS)
                if contact is not None:
                    buyer["buyer_contact"] = {
                        "name": self._find_text(contact, "cbc:Name"),
                        "email": self._find_text(contact, "cbc:ElectronicMail"),
                        "phone": self._find_text(contact, "cbc:Telephone"),
                    }

            # Buyer type
            buyer_type = contracting_party.find(
                ".//cac:ContractingPartyType/cbc:PartyTypeCode",
                EFORMS_NS
            )
            if buyer_type is not None:
                buyer["buyer_type"] = buyer_type.text

            # Main activity
            activity = contracting_party.find(
                ".//cac:ContractingActivity/cbc:ActivityTypeCode",
                EFORMS_NS
            )
            if activity is not None:
                buyer["buyer_activity"] = activity.text

        return buyer

    def _extract_procedure(self, root: ET.Element) -> Dict[str, Any]:
        """Extract procedure information"""
        result = {}

        # Tendering process
        process = root.find(".//cac:TenderingProcess", EFORMS_NS)
        if process is not None:
            proc_type = process.find("cbc:ProcedureCode", EFORMS_NS)
            if proc_type is not None:
                result["procedure_type"] = proc_type.text

            # Framework agreement
            framework = process.find(".//cbc:ContractingSystemTypeCode", EFORMS_NS)
            if framework is not None:
                result["is_framework"] = framework.text == "framework-agreement"

        # Tendering terms
        terms = root.find(".//cac:TenderingTerms", EFORMS_NS)
        if terms is not None:
            # Electronic submission
            electronic = terms.find(".//cbc:SubmissionMethodCode", EFORMS_NS)
            if electronic is not None:
                result["submission_method"] = electronic.text

            # Variants
            variants = terms.find(".//cbc:VariantConstraintIndicator", EFORMS_NS)
            if variants is not None:
                result["variants_allowed"] = variants.text.lower() == "true"

        # Legal basis
        legal_doc = root.find(".//cac:ContractingParty//cac:LegalForm/cbc:CompanyLegalFormCode", EFORMS_NS)
        if legal_doc is not None:
            result["legal_basis"] = legal_doc.text

        return result

    def _extract_values(self, root: ET.Element) -> Dict[str, Any]:
        """Extract estimated value and financial information"""
        result = {}

        # Procedure-level estimated value
        proc_project = root.find(".//cac:ProcurementProject", EFORMS_NS)
        if proc_project is not None:
            total = proc_project.find(".//cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount", EFORMS_NS)
            if total is not None:
                result["estimated_value"] = float(total.text) if total.text else None
                result["estimated_value_currency"] = total.get("currencyID", "EUR")

        # Budget amount
        budget = root.find(".//cac:BudgetAmount/cbc:EstimatedOverallContractAmount", EFORMS_NS)
        if budget is not None and "estimated_value" not in result:
            result["estimated_value"] = float(budget.text) if budget.text else None
            result["estimated_value_currency"] = budget.get("currencyID", "EUR")

        return result

    def _extract_dates(self, root: ET.Element) -> Dict[str, Any]:
        """Extract dates and deadlines"""
        result = {}

        # Submission deadline
        tender_deadline = root.find(".//cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate", EFORMS_NS)
        if tender_deadline is not None and tender_deadline.text:
            result["submission_deadline_date"] = tender_deadline.text

        tender_deadline_time = root.find(".//cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndTime", EFORMS_NS)
        if tender_deadline_time is not None and tender_deadline_time.text:
            result["submission_deadline_time"] = tender_deadline_time.text

        # Combine date and time
        if "submission_deadline_date" in result:
            time_part = result.get("submission_deadline_time", "23:59:59")
            try:
                dt_str = f"{result['submission_deadline_date']}T{time_part}"
                result["submission_deadline"] = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Contract duration
        duration = root.find(".//cac:ProcurementProject/cac:PlannedPeriod/cbc:DurationMeasure", EFORMS_NS)
        if duration is not None and duration.text:
            result["contract_duration_value"] = int(duration.text)
            result["contract_duration_unit"] = duration.get("unitCode", "MON")

            # Convert to months
            if result["contract_duration_unit"] == "MON":
                result["contract_duration_months"] = result["contract_duration_value"]
            elif result["contract_duration_unit"] == "DAY":
                result["contract_duration_months"] = result["contract_duration_value"] // 30
            elif result["contract_duration_unit"] == "YEAR":
                result["contract_duration_months"] = result["contract_duration_value"] * 12

        # Start date
        start_date = root.find(".//cac:ProcurementProject/cac:PlannedPeriod/cbc:StartDate", EFORMS_NS)
        if start_date is not None and start_date.text:
            result["contract_start_date"] = start_date.text

        return result

    def _extract_classification(self, root: ET.Element) -> Dict[str, Any]:
        """Extract CPV codes and NUTS regions"""
        result = {}

        # Main CPV code
        main_cpv = root.find(".//cac:ProcurementProject/cac:MainCommodityClassification/cbc:ItemClassificationCode", EFORMS_NS)
        if main_cpv is not None:
            result["cpv_main"] = main_cpv.text

        # Additional CPV codes
        additional_cpv = []
        for cpv in root.findall(".//cac:ProcurementProject/cac:AdditionalCommodityClassification/cbc:ItemClassificationCode", EFORMS_NS):
            if cpv.text:
                additional_cpv.append(cpv.text)

        # Combine all CPV codes
        all_cpv = []
        if result.get("cpv_main"):
            all_cpv.append(result["cpv_main"])
        all_cpv.extend(additional_cpv)
        result["cpv_codes"] = all_cpv

        # Contract nature
        nature = root.find(".//cac:ProcurementProject/cbc:ProcurementTypeCode", EFORMS_NS)
        if nature is not None:
            nature_map = {
                "works": "works",
                "supplies": "supplies",
                "services": "services",
            }
            result["contract_nature"] = nature_map.get(nature.text.lower(), nature.text)

        # NUTS codes (place of performance)
        nuts_codes = []
        for region in root.findall(".//cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode", EFORMS_NS):
            if region.text:
                nuts_codes.append(region.text)
        result["nuts_codes"] = nuts_codes

        return result

    def _extract_award_criteria(self, root: ET.Element) -> Dict[str, Any]:
        """Extract award criteria from eForms XML.

        eForms uses nested structure with SubordinateAwardingCriterion elements
        containing the actual criteria types and weights.
        """
        result = {}
        criteria = []

        # Find all AwardingCriterion elements (may be in lot or procedure level)
        for awarding_criterion in root.findall(".//cac:AwardingCriterion", EFORMS_NS):
            # Check for SubordinateAwardingCriterion elements (eForms structure)
            subordinates = awarding_criterion.findall("cac:SubordinateAwardingCriterion", EFORMS_NS)

            if subordinates:
                # eForms format with subordinate criteria
                for sub in subordinates:
                    criterion_data = {}

                    # Type code (e.g., "quality", "price", "cost")
                    type_code = sub.find("cbc:AwardingCriterionTypeCode", EFORMS_NS)
                    if type_code is not None:
                        criterion_data["type"] = type_code.text

                    # Name/description
                    name = sub.find("cbc:Name", EFORMS_NS)
                    if name is not None:
                        criterion_data["name"] = name.text

                    desc = sub.find("cbc:Description", EFORMS_NS)
                    if desc is not None:
                        criterion_data["description"] = desc.text

                    # Weight (may be in a nested AwardingCriterionParameter)
                    weight = sub.find(".//cbc:WeightNumeric", EFORMS_NS)
                    if weight is not None:
                        try:
                            criterion_data["weight"] = float(weight.text)
                        except (ValueError, TypeError):
                            pass

                    # Alternative weight fields
                    weight_pct = sub.find(".//efbc:ParameterNumeric", EFORMS_NS)
                    if weight_pct is not None and "weight" not in criterion_data:
                        try:
                            criterion_data["weight"] = float(weight_pct.text)
                        except (ValueError, TypeError):
                            pass

                    if criterion_data:
                        criteria.append(criterion_data)
            else:
                # Legacy/simple format - direct criteria
                criterion_data = {}

                type_code = awarding_criterion.find("cbc:AwardingCriterionTypeCode", EFORMS_NS)
                if type_code is not None:
                    criterion_data["type"] = type_code.text

                name = awarding_criterion.find("cbc:Name", EFORMS_NS)
                if name is not None:
                    criterion_data["name"] = name.text

                weight = awarding_criterion.find(".//cbc:WeightNumeric", EFORMS_NS)
                if weight is not None:
                    try:
                        criterion_data["weight"] = float(weight.text)
                    except (ValueError, TypeError):
                        pass

                desc = awarding_criterion.find("cbc:Description", EFORMS_NS)
                if desc is not None:
                    criterion_data["description"] = desc.text

                if criterion_data:
                    criteria.append(criterion_data)

        # Also check for efac:AwardCriterion elements (alternative eForms structure)
        for efac_criterion in root.findall(".//efac:AwardCriterion", EFORMS_NS):
            criterion_data = {}

            type_code = efac_criterion.find("efbc:AwardCriterionTypeCode", EFORMS_NS)
            if type_code is not None:
                criterion_data["type"] = type_code.text

            desc = efac_criterion.find("efbc:AwardCriterionDescription", EFORMS_NS)
            if desc is not None:
                criterion_data["description"] = desc.text

            weight = efac_criterion.find("efbc:AwardCriterionWeight", EFORMS_NS)
            if weight is not None:
                try:
                    criterion_data["weight"] = float(weight.text)
                except (ValueError, TypeError):
                    pass

            if criterion_data:
                criteria.append(criterion_data)

        if criteria:
            result["award_criteria"] = criteria
            # Determine primary criterion type
            types = [c.get("type", "").lower() for c in criteria if c.get("type")]
            if "price" in types and len(set(types)) == 1:
                result["award_criteria_type"] = "price"
            elif "quality" in types:
                result["award_criteria_type"] = "quality"
            elif "cost" in types:
                result["award_criteria_type"] = "cost"
            else:
                result["award_criteria_type"] = "best-value"  # Default for mixed criteria

        return result

    def _extract_lots(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract lot information"""
        lots = []

        for lot in root.findall(".//cac:ProcurementProjectLot", EFORMS_NS):
            lot_data = {}

            # Lot ID
            lot_id = lot.find("cbc:ID", EFORMS_NS)
            if lot_id is not None:
                scheme = lot_id.get("schemeName")
                if scheme == "Lot":
                    lot_data["lot_id"] = lot_id.text

                    # Title
                    title = lot.find(".//cac:ProcurementProject/cbc:Name", EFORMS_NS)
                    if title is not None:
                        lot_data["title"] = title.text

                    # Description
                    desc = lot.find(".//cac:ProcurementProject/cbc:Description", EFORMS_NS)
                    if desc is not None:
                        lot_data["description"] = desc.text

                    # CPV
                    cpv = lot.find(".//cac:ProcurementProject/cac:MainCommodityClassification/cbc:ItemClassificationCode", EFORMS_NS)
                    if cpv is not None:
                        lot_data["cpv_code"] = cpv.text

                    # Estimated value
                    value = lot.find(".//cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount", EFORMS_NS)
                    if value is not None and value.text:
                        lot_data["estimated_value"] = float(value.text)
                        lot_data["currency"] = value.get("currencyID", "EUR")

                    lots.append(lot_data)

        return lots

    def _extract_requirements(self, root: ET.Element) -> Dict[str, Any]:
        """Extract selection criteria and requirements"""
        result = {}
        selection_criteria = []
        exclusion_grounds = []

        # Selection criteria from TenderingTerms
        for criterion in root.findall(".//cac:TenderingTerms//cac:TendererQualificationRequest", EFORMS_NS):
            criterion_data = {}

            # Type
            type_code = criterion.find("cbc:CompanyLegalFormCode", EFORMS_NS)
            if type_code is not None:
                criterion_data["type"] = type_code.text

            # Description
            desc = criterion.find("cbc:Description", EFORMS_NS)
            if desc is not None:
                criterion_data["description"] = desc.text

            # Specific requirement
            req = criterion.find(".//cac:SpecificTendererRequirement", EFORMS_NS)
            if req is not None:
                req_type = req.find("cbc:TendererRequirementTypeCode", EFORMS_NS)
                if req_type is not None:
                    criterion_data["requirement_type"] = req_type.text

            if criterion_data:
                selection_criteria.append(criterion_data)

        if selection_criteria:
            result["selection_criteria"] = selection_criteria

        # Minimum requirements (turnover, experience, etc.)
        min_requirements = {}

        # Technical/professional ability
        tech_req = root.find(".//cac:TenderingTerms//cac:TechnicalEvaluationCriterion", EFORMS_NS)
        if tech_req is not None:
            tech_desc = tech_req.find("cbc:Description", EFORMS_NS)
            if tech_desc is not None:
                min_requirements["technical_ability"] = tech_desc.text

        # Economic requirements
        econ_req = root.find(".//cac:TenderingTerms//cac:EconomicOperatorShortList", EFORMS_NS)
        if econ_req is not None:
            turnover = econ_req.find(".//cbc:MinimumAmount", EFORMS_NS)
            if turnover is not None and turnover.text:
                min_requirements["minimum_turnover"] = float(turnover.text)
                min_requirements["turnover_currency"] = turnover.get("currencyID", "EUR")

        if min_requirements:
            result["minimum_requirements"] = min_requirements

        return result

    def _extract_documents(self, root: ET.Element) -> Dict[str, Any]:
        """Extract document references and links"""
        result = {}

        # Tender documents URL
        for doc_ref in root.findall(".//cac:AdditionalDocumentReference", EFORMS_NS):
            doc_type = doc_ref.find("cbc:DocumentTypeCode", EFORMS_NS)
            attachment = doc_ref.find("cac:Attachment/cac:ExternalReference/cbc:URI", EFORMS_NS)

            if attachment is not None:
                url = attachment.text
                if doc_type is not None:
                    if doc_type.text == "procurement-document":
                        result["documents_url"] = url
                    elif doc_type.text == "submissions":
                        result["submission_url"] = url

        # Contract folder ID (for constructing TED URL)
        folder_id = root.find(".//cac:AdditionalDocumentReference/cbc:ID", EFORMS_NS)
        if folder_id is not None:
            result["contract_folder_id"] = folder_id.text

        return result

    def parse_to_tender_dict(self, xml_content: str, publication_number: str) -> Dict[str, Any]:
        """
        Parse XML and return a dictionary ready for Tender model.

        Args:
            xml_content: Raw XML string
            publication_number: TED publication number

        Returns:
            Dictionary matching Tender model fields
        """
        parsed = self.parse(xml_content)

        # Map parsed fields to Tender model
        return {
            "publication_number": publication_number,
            "notice_id": parsed.get("uuid") or parsed.get("notice_id"),
            "form_type": parsed.get("notice_type"),
            "notice_subtype": parsed.get("notice_type_code"),
            "title": parsed.get("title", ""),
            "description": parsed.get("description"),
            "official_name": parsed.get("official_name"),
            "buyer_country": parsed.get("buyer_country"),
            "procedure_type": parsed.get("procedure_type"),
            "cpv_codes": parsed.get("cpv_codes", []),
            "cpv_main": parsed.get("cpv_main"),
            "nuts_codes": parsed.get("nuts_codes", []),
            "contract_nature": parsed.get("contract_nature"),
            "estimated_value": parsed.get("estimated_value"),
            "estimated_value_currency": parsed.get("estimated_value_currency", "EUR"),
            "submission_deadline": parsed.get("submission_deadline"),
            "contract_duration_months": parsed.get("contract_duration_months"),
            "award_criteria_type": parsed.get("award_criteria_type"),
            "award_criteria": parsed.get("award_criteria"),
            "selection_criteria": parsed.get("selection_criteria"),
            "minimum_requirements": parsed.get("minimum_requirements"),
            "has_lots": parsed.get("has_lots", False),
            "lot_count": parsed.get("lot_count", 0),
            "lots": parsed.get("lots"),
            "documents_url": parsed.get("documents_url"),
            "submission_url": parsed.get("submission_url"),
            "is_framework": parsed.get("is_framework", False),
            "xml_content": xml_content,
            "raw_json": parsed,
        }

    def _parse_legacy(self, root: ET.Element, xml_content: str) -> Dict[str, Any]:
        """
        Parse legacy TED XML format (pre-eForms, 2014-2022).

        Legacy TED notices use form-based structure (F01, F02, F03, etc.)
        with different namespaces than eForms.

        Args:
            root: Parsed XML root element
            xml_content: Raw XML string (for pattern matching)

        Returns:
            Dictionary with extracted tender information
        """
        result = {
            "notice_type": "legacy",
            "raw_root_tag": root.tag,
        }

        # Detect form type from XML structure
        form_type = self._detect_legacy_form_type(xml_content)
        result["form_type"] = form_type

        # Find the main form section (F01, F02, F03, etc.)
        form_section = self._find_legacy_form_section(root)
        if form_section is None:
            logger.warning("Could not find form section in legacy TED XML")
            return result

        # Extract core identifiers
        result.update(self._extract_legacy_identifiers(root))

        # Extract contracting authority (buyer)
        result.update(self._extract_legacy_buyer(form_section))

        # Extract object of contract
        result.update(self._extract_legacy_object(form_section))

        # Extract procedure information
        result.update(self._extract_legacy_procedure(form_section))

        # Extract value information
        result.update(self._extract_legacy_values(form_section))

        # Extract dates
        result.update(self._extract_legacy_dates(form_section))

        # Extract CPV codes
        result.update(self._extract_legacy_cpv(form_section))

        # Extract lots
        lots = self._extract_legacy_lots(form_section)
        result["lots"] = lots
        result["has_lots"] = len(lots) > 0
        result["lot_count"] = len(lots)

        return result

    def _detect_legacy_form_type(self, xml_content: str) -> str:
        """Detect the form type from legacy TED XML"""
        form_patterns = {
            "<F01_2014>": "F01",  # Prior Information Notice
            "<F02_2014>": "F02",  # Contract Notice
            "<F03_2014>": "F03",  # Contract Award Notice
            "<F04_2014>": "F04",  # Periodic Indicative Notice - Utilities
            "<F05_2014>": "F05",  # Contract Notice - Utilities
            "<F06_2014>": "F06",  # Contract Award Notice - Utilities
            "<F07_2014>": "F07",  # Qualification System - Utilities
            "<F08_2014>": "F08",  # Notice on buyer profile
            "<F12_2014>": "F12",  # Design Contest Notice
            "<F13_2014>": "F13",  # Design Contest Results
            "<F14_2014>": "F14",  # Corrigendum
            "<F15_2014>": "F15",  # Voluntary ex ante transparency
            "<F20_2014>": "F20",  # Modification notice
            "<F21_2014>": "F21",  # Social and specific services - Contract
            "<F22_2014>": "F22",  # Social and specific services - Award
            "<F23_2014>": "F23",  # Social and specific services - Concession
            "<F24_2014>": "F24",  # Concession Notice
            "<F25_2014>": "F25",  # Concession Award Notice
        }
        for pattern, form_type in form_patterns.items():
            if pattern in xml_content:
                return form_type
        return "unknown"

    def _find_legacy_form_section(self, root: ET.Element) -> Optional[ET.Element]:
        """Find the main form section in legacy TED XML"""
        # Try to find FORM_SECTION first
        form_section = root.find(".//FORM_SECTION")
        if form_section is not None:
            # Find the actual form (F01, F02, etc.)
            for child in form_section:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag.startswith('F') and '_2014' in tag:
                    return child
            # If no form found, return the section itself
            return form_section

        # Direct children might be the form
        for child in root:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag.startswith('F') and ('_2014' in tag or '_2016' in tag):
                return child

        return root

    def _extract_legacy_identifiers(self, root: ET.Element) -> Dict[str, Any]:
        """Extract identifiers from legacy TED format"""
        result = {}

        # TED_EXPORT level identifiers
        doc_id = root.find(".//DOC_ID")
        if doc_id is not None and doc_id.text:
            result["notice_id"] = doc_id.text

        no_doc_ojs = root.find(".//NO_DOC_OJS")
        if no_doc_ojs is not None and no_doc_ojs.text:
            result["publication_number"] = no_doc_ojs.text

        # Edition number
        no_oj = root.find(".//NO_OJ")
        if no_oj is not None and no_oj.text:
            result["oj_edition"] = no_oj.text

        return result

    def _extract_legacy_buyer(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract contracting authority from legacy format"""
        result = {}

        # Find CONTRACTING_BODY or CONTRACTING_AUTHORITY
        buyer = form_section.find(".//CONTRACTING_BODY")
        if buyer is None:
            buyer = form_section.find(".//CONTRACTING_AUTHORITY")

        if buyer is not None:
            # Official name
            name = buyer.find(".//OFFICIALNAME")
            if name is not None and name.text:
                result["official_name"] = name.text.strip()

            # Address
            town = buyer.find(".//TOWN")
            if town is not None and town.text:
                result["buyer_city"] = town.text.strip()

            postal_code = buyer.find(".//POSTAL_CODE")
            if postal_code is not None and postal_code.text:
                result["buyer_postal_code"] = postal_code.text.strip()

            # Country
            country = buyer.find(".//COUNTRY")
            if country is not None:
                country_code = country.get("VALUE")
                if country_code:
                    result["buyer_country"] = country_code

            # URL
            url = buyer.find(".//URL_GENERAL")
            if url is not None and url.text:
                result["buyer_url"] = url.text.strip()

            # Contact
            contact = buyer.find(".//CONTACT_POINT")
            if contact is not None and contact.text:
                result["buyer_contact"] = contact.text.strip()

            email = buyer.find(".//E_MAIL")
            if email is not None and email.text:
                result["buyer_email"] = email.text.strip()

        return result

    def _extract_legacy_object(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract object of contract from legacy format"""
        result = {}

        # Find OBJECT_CONTRACT section
        obj = form_section.find(".//OBJECT_CONTRACT")
        if obj is not None:
            # Title
            title = obj.find(".//TITLE")
            if title is not None:
                # May have P elements
                p = title.find("P")
                if p is not None and p.text:
                    result["title"] = p.text.strip()
                elif title.text:
                    result["title"] = title.text.strip()

            # Short description
            desc = obj.find(".//SHORT_DESCR")
            if desc is not None:
                p = desc.find("P")
                if p is not None and p.text:
                    result["description"] = p.text.strip()
                elif desc.text:
                    result["description"] = desc.text.strip()

            # Contract type (works, supplies, services)
            type_contract = obj.find(".//TYPE_CONTRACT")
            if type_contract is not None:
                ctype = type_contract.get("CTYPE")
                if ctype:
                    result["contract_nature"] = ctype.lower()

            # Reference number
            ref = obj.find(".//REFERENCE_NUMBER")
            if ref is not None and ref.text:
                result["reference_number"] = ref.text.strip()

        return result

    def _extract_legacy_procedure(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract procedure information from legacy format"""
        result = {}

        # Find PROCEDURE section
        proc = form_section.find(".//PROCEDURE")
        if proc is not None:
            # Procedure type - check for specific elements
            if proc.find(".//PT_OPEN") is not None:
                result["procedure_type"] = "open"
            elif proc.find(".//PT_RESTRICTED") is not None:
                result["procedure_type"] = "restricted"
            elif proc.find(".//PT_COMPETITIVE_NEGOTIATION") is not None:
                result["procedure_type"] = "neg-w-call"
            elif proc.find(".//PT_COMPETITIVE_DIALOGUE") is not None:
                result["procedure_type"] = "comp-dial"
            elif proc.find(".//PT_INNOVATION_PARTNERSHIP") is not None:
                result["procedure_type"] = "innovation"
            elif proc.find(".//PT_NEGOTIATED_WITHOUT_CALL") is not None:
                result["procedure_type"] = "neg-wo-call"

            # Framework agreement
            framework = proc.find(".//FRAMEWORK")
            if framework is not None:
                result["is_framework"] = True

        return result

    def _extract_legacy_values(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract value information from legacy format"""
        result = {}

        # Look for VAL_TOTAL, VAL_ESTIMATED_TOTAL, or VAL_RANGE
        val_total = form_section.find(".//VAL_TOTAL")
        if val_total is not None and val_total.text:
            try:
                result["estimated_value"] = float(val_total.text.strip())
                currency = val_total.get("CURRENCY")
                if currency:
                    result["estimated_value_currency"] = currency
            except ValueError:
                pass

        if "estimated_value" not in result:
            val_estimated = form_section.find(".//VAL_ESTIMATED_TOTAL")
            if val_estimated is not None and val_estimated.text:
                try:
                    result["estimated_value"] = float(val_estimated.text.strip())
                    currency = val_estimated.get("CURRENCY")
                    if currency:
                        result["estimated_value_currency"] = currency
                except ValueError:
                    pass

        # Value range
        val_range_low = form_section.find(".//VAL_RANGE_TOTAL/LOW")
        val_range_high = form_section.find(".//VAL_RANGE_TOTAL/HIGH")
        if val_range_low is not None and val_range_low.text:
            try:
                result["value_range_low"] = float(val_range_low.text.strip())
            except ValueError:
                pass
        if val_range_high is not None and val_range_high.text:
            try:
                result["value_range_high"] = float(val_range_high.text.strip())
            except ValueError:
                pass

        return result

    def _extract_legacy_dates(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract dates from legacy format"""
        result = {}

        # Submission deadline
        date_receipt = form_section.find(".//DATE_RECEIPT_TENDERS")
        if date_receipt is not None and date_receipt.text:
            try:
                result["submission_deadline_date"] = date_receipt.text.strip()
                # Try to parse ISO format
                dt = datetime.fromisoformat(date_receipt.text.strip())
                result["submission_deadline"] = dt
            except ValueError:
                pass

        time_receipt = form_section.find(".//TIME_RECEIPT_TENDERS")
        if time_receipt is not None and time_receipt.text:
            result["submission_deadline_time"] = time_receipt.text.strip()

        # Duration
        duration = form_section.find(".//DURATION")
        if duration is not None:
            months = duration.find(".//MONTHS")
            if months is not None and months.text:
                try:
                    result["contract_duration_months"] = int(months.text.strip())
                except ValueError:
                    pass
            days = duration.find(".//DAYS")
            if days is not None and days.text:
                try:
                    result["contract_duration_months"] = int(days.text.strip()) // 30
                except ValueError:
                    pass

        # Contract start date
        start = form_section.find(".//DATE_START")
        if start is not None and start.text:
            result["contract_start_date"] = start.text.strip()

        return result

    def _extract_legacy_cpv(self, form_section: ET.Element) -> Dict[str, Any]:
        """Extract CPV codes from legacy format"""
        result = {}
        cpv_codes = []

        # Main CPV
        main_cpv = form_section.find(".//CPV_MAIN/CPV_CODE")
        if main_cpv is not None:
            code = main_cpv.get("CODE")
            if code:
                result["cpv_main"] = code
                cpv_codes.append(code)

        # Additional CPV codes
        for cpv in form_section.findall(".//CPV_ADDITIONAL/CPV_CODE"):
            code = cpv.get("CODE")
            if code and code not in cpv_codes:
                cpv_codes.append(code)

        result["cpv_codes"] = cpv_codes

        # NUTS codes
        nuts_codes = []
        for nuts in form_section.findall(".//NUTS"):
            code = nuts.get("CODE")
            if code:
                nuts_codes.append(code)
        result["nuts_codes"] = nuts_codes

        return result

    def _extract_legacy_lots(self, form_section: ET.Element) -> List[Dict[str, Any]]:
        """Extract lot information from legacy format"""
        lots = []

        for lot in form_section.findall(".//OBJECT_DESCR"):
            lot_data = {}

            # Lot number
            lot_no = lot.find(".//LOT_NO")
            if lot_no is not None and lot_no.text:
                lot_data["lot_id"] = lot_no.text.strip()

            # Title
            title = lot.find(".//TITLE")
            if title is not None:
                p = title.find("P")
                if p is not None and p.text:
                    lot_data["title"] = p.text.strip()
                elif title.text:
                    lot_data["title"] = title.text.strip()

            # Description
            desc = lot.find(".//SHORT_DESCR")
            if desc is not None:
                p = desc.find("P")
                if p is not None and p.text:
                    lot_data["description"] = p.text.strip()
                elif desc.text:
                    lot_data["description"] = desc.text.strip()

            # CPV for lot
            cpv = lot.find(".//CPV_MAIN/CPV_CODE")
            if cpv is not None:
                code = cpv.get("CODE")
                if code:
                    lot_data["cpv_code"] = code

            # Value
            val = lot.find(".//VAL_OBJECT")
            if val is not None and val.text:
                try:
                    lot_data["estimated_value"] = float(val.text.strip())
                    currency = val.get("CURRENCY")
                    if currency:
                        lot_data["currency"] = currency
                except ValueError:
                    pass

            if lot_data:
                lots.append(lot_data)

        return lots
