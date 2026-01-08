"""
Tender Service

Main orchestrator for the Tenderator feature.
Coordinates TED data fetching, parsing, matching, and persistence.

Usage:
    service = TenderService(db_session)

    # Fetch new tenders
    await service.fetch_new_tenders()

    # Match tenders to users
    await service.match_tenders_to_users()

    # Get tenders for a user
    matches = await service.get_user_matches(user_id)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
from pathlib import Path
import uuid as uuid_lib

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from .ted_client import TEDClient, NoticeType, ProcedureType
from .ted_sparql_client import TEDSPARQLClient
from .eforms_parser import EFormsParser
from .sme_scorer import SMEScorer, SMEProfile, SMECategory
from ...models.tender import Tender, TenderProfile, TenderMatch, TenderFetchJob

logger = logging.getLogger(__name__)


class TenderService:
    """
    Main service for Tenderator operations.

    Responsibilities:
    - Fetch tenders from TED (REST API and SPARQL)
    - Parse eForms XML content
    - Store tenders in database
    - Match tenders to user profiles
    - Provide tender search and retrieval
    """

    def __init__(
        self,
        db: Session,
        fields_path: Optional[str] = None
    ):
        """
        Initialize the tender service.

        Args:
            db: SQLAlchemy database session
            fields_path: Path to eForms fields.json (optional)
        """
        self.db = db
        self.parser = EFormsParser(fields_path=fields_path)
        self.sme_scorer = SMEScorer()

        # Default path to eForms fields
        if fields_path is None:
            default_path = Path("backend/knowledge_base/tenders/eforms/fields.json")
            if default_path.exists():
                self.parser = EFormsParser(fields_path=str(default_path))

    async def fetch_new_tenders(
        self,
        days_back: int = 7,
        countries: Optional[List[str]] = None,
        cpv_codes: Optional[List[str]] = None,
        max_value: float = 5_000_000,
        source: str = "ted_api"
    ) -> TenderFetchJob:
        """
        Fetch new tenders from TED and store in database.

        Args:
            days_back: Number of days to look back
            countries: Filter by countries (ISO codes)
            cpv_codes: Filter by CPV codes
            max_value: Maximum tender value for SME filtering
            source: Data source ("ted_api" or "ted_sparql")

        Returns:
            TenderFetchJob with results summary
        """
        # Create fetch job record
        job = TenderFetchJob(
            job_id=str(uuid_lib.uuid4())[:8],
            job_type="scheduled",
            source=source,
            query_params={
                "days_back": days_back,
                "countries": countries,
                "cpv_codes": cpv_codes,
                "max_value": max_value
            },
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(job)
        self.db.commit()

        tenders_found = 0
        tenders_new = 0
        tenders_updated = 0
        errors = []

        try:
            if source == "ted_api":
                results = await self._fetch_from_rest_api(
                    days_back=days_back,
                    countries=countries,
                    cpv_codes=cpv_codes,
                    max_value=max_value
                )
            else:
                results = await self._fetch_from_sparql(
                    days_back=days_back,
                    countries=countries
                )

            tenders_found = len(results)

            # Process each tender
            for notice_data in results:
                try:
                    is_new = await self._process_notice(notice_data)
                    if is_new:
                        tenders_new += 1
                    else:
                        tenders_updated += 1
                except Exception as e:
                    errors.append(f"Error processing notice: {str(e)}")
                    logger.error(f"Error processing notice: {e}")

            job.status = "completed"

        except Exception as e:
            job.status = "failed"
            errors.append(f"Fetch failed: {str(e)}")
            logger.error(f"Tender fetch failed: {e}")

        # Update job record
        job.tenders_found = tenders_found
        job.tenders_new = tenders_new
        job.tenders_updated = tenders_updated
        job.errors = errors if errors else None
        job.completed_at = datetime.utcnow()
        job.duration_seconds = (job.completed_at - job.started_at).total_seconds()

        self.db.commit()

        logger.info(
            f"Fetch job {job.job_id} completed: "
            f"{tenders_found} found, {tenders_new} new, {tenders_updated} updated"
        )

        return job

    async def _fetch_from_rest_api(
        self,
        days_back: int,
        countries: Optional[List[str]],
        cpv_codes: Optional[List[str]],
        max_value: float
    ) -> List[Dict[str, Any]]:
        """Fetch tenders using TED REST API"""
        all_notices = []

        async with TEDClient() as client:
            # Use SME-friendly search
            result = await client.search_sme_friendly(
                cpv_codes=cpv_codes,
                countries=countries,
                max_value=max_value,
                min_deadline_days=14,  # At least 2 weeks to deadline
                page_size=100
            )

            notices = result.get("notices", [])
            all_notices.extend(notices)

            # Fetch additional pages if needed
            total_pages = result.get("total_pages", 1)
            for page in range(2, min(total_pages + 1, 11)):  # Max 10 pages
                result = await client.search_sme_friendly(
                    cpv_codes=cpv_codes,
                    countries=countries,
                    max_value=max_value,
                    min_deadline_days=14,
                    page=page,
                    page_size=100
                )
                notices = result.get("notices", [])
                if not notices:
                    break
                all_notices.extend(notices)

        return all_notices

    async def _fetch_from_sparql(
        self,
        days_back: int,
        countries: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Fetch tenders using TED SPARQL endpoint"""
        all_notices = []

        date_from = date.today() - timedelta(days=days_back)
        date_to = date.today()

        async with TEDSPARQLClient() as client:
            if countries:
                # Map country codes to names
                country_names = self._get_country_names(countries)
                for country in country_names:
                    notices = await client.get_tenders_by_country(
                        country=country,
                        limit=500
                    )
                    all_notices.extend(notices)
            else:
                notices = await client.get_tenders_by_date_range(
                    date_from=date_from,
                    date_to=date_to,
                    limit=1000
                )
                all_notices.extend(notices)

        return all_notices

    async def _process_notice(self, notice_data: Dict[str, Any]) -> bool:
        """
        Process a single notice and store in database.

        Args:
            notice_data: Notice data from API

        Returns:
            True if new tender was created, False if existing was updated
        """
        publication_number = notice_data.get("publicationNumber") or notice_data.get("publication_number")

        if not publication_number:
            logger.warning("Notice missing publication number")
            return False

        # Check if tender already exists
        existing = self.db.query(Tender).filter(
            Tender.publication_number == publication_number
        ).first()

        if existing:
            # Update existing tender
            self._update_tender(existing, notice_data)
            return False
        else:
            # Create new tender
            tender = self._create_tender(notice_data, publication_number)
            self.db.add(tender)
            self.db.commit()
            return True

    def _create_tender(
        self,
        notice_data: Dict[str, Any],
        publication_number: str
    ) -> Tender:
        """Create a new Tender from notice data"""
        tender = Tender(
            publication_number=publication_number,
            notice_id=notice_data.get("noticeId"),
            title=notice_data.get("title", ""),
            official_name=notice_data.get("buyerName") or notice_data.get("official_name"),
            buyer_country=notice_data.get("countryCode") or notice_data.get("buyer_country"),
            procedure_type=notice_data.get("procedureType"),
            cpv_main=notice_data.get("cpvCode"),
            publication_date=self._parse_date(notice_data.get("publicationDate")),
            submission_deadline=self._parse_date(notice_data.get("deadline")),
            status="open",
            source="ted_api",
            ted_url=self._build_ted_url(publication_number),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Calculate SME suitability score
        sme_analysis = self._calculate_sme_score(notice_data)
        tender.sme_suitability_score = sme_analysis.get("sme_suitability_score")
        tender.sme_score_breakdown = sme_analysis.get("score_breakdown")

        return tender

    def _update_tender(self, tender: Tender, notice_data: Dict[str, Any]):
        """Update existing tender with new data"""
        if notice_data.get("title"):
            tender.title = notice_data["title"]

        if notice_data.get("deadline"):
            tender.submission_deadline = self._parse_date(notice_data["deadline"])

        tender.updated_at = datetime.utcnow()
        tender.last_synced_at = datetime.utcnow()

    async def fetch_and_parse_xml(self, publication_number: str) -> Optional[Tender]:
        """
        Fetch XML for a tender and parse full details.

        Args:
            publication_number: TED publication number

        Returns:
            Updated Tender or None if not found
        """
        async with TEDClient() as client:
            xml_content = await client.get_notice_xml(publication_number)

            if not xml_content:
                return None

            # Parse XML
            tender_data = self.parser.parse_to_tender_dict(xml_content, publication_number)

            # Find or create tender
            tender = self.db.query(Tender).filter(
                Tender.publication_number == publication_number
            ).first()

            if not tender:
                tender = Tender(publication_number=publication_number)
                self.db.add(tender)

            # Update with parsed data
            for key, value in tender_data.items():
                if value is not None and hasattr(tender, key):
                    setattr(tender, key, value)

            tender.ted_url = self._build_ted_url(publication_number)
            tender.updated_at = datetime.utcnow()

            self.db.commit()
            return tender

    async def match_tenders_to_users(self) -> int:
        """
        Match open tenders to active user profiles.

        Returns:
            Number of new matches created
        """
        # Get active profiles
        profiles = self.db.query(TenderProfile).filter(
            TenderProfile.is_active == True
        ).all()

        # Get open tenders with deadline in the future
        open_tenders = self.db.query(Tender).filter(
            and_(
                Tender.status == "open",
                or_(
                    Tender.submission_deadline == None,
                    Tender.submission_deadline > datetime.utcnow()
                )
            )
        ).all()

        matches_created = 0

        for profile in profiles:
            for tender in open_tenders:
                # Check if match already exists
                existing = self.db.query(TenderMatch).filter(
                    and_(
                        TenderMatch.profile_id == profile.id,
                        TenderMatch.tender_id == tender.id
                    )
                ).first()

                if existing:
                    continue

                # Calculate match score
                score, reasons = self._calculate_match_score(tender, profile)

                # Only create match if score is above threshold
                if score >= 50:
                    match = TenderMatch(
                        tender_id=tender.id,
                        profile_id=profile.id,
                        user_id=profile.user_id,
                        match_score=score,
                        match_reasons=reasons,
                        created_at=datetime.utcnow()
                    )
                    self.db.add(match)
                    matches_created += 1

        self.db.commit()
        logger.info(f"Created {matches_created} new tender matches")

        return matches_created

    def _calculate_match_score(
        self,
        tender: Tender,
        profile: TenderProfile
    ) -> tuple[float, Dict[str, float]]:
        """
        Calculate match score between a tender and user profile.

        Returns:
            Tuple of (overall_score, reason_scores)
        """
        scores = {}
        weights = {
            "cpv_match": 0.35,
            "country_match": 0.20,
            "value_match": 0.20,
            "procedure_match": 0.15,
            "deadline_match": 0.10
        }

        # CPV code matching
        if tender.cpv_codes and profile.cpv_codes:
            matching_cpv = set(tender.cpv_codes) & set(profile.cpv_codes)
            scores["cpv_match"] = len(matching_cpv) / len(profile.cpv_codes) if profile.cpv_codes else 0
        elif tender.cpv_main and profile.cpv_categories:
            # Check if main CPV starts with any category
            for cat in profile.cpv_categories:
                if tender.cpv_main.startswith(cat):
                    scores["cpv_match"] = 0.8
                    break
            else:
                scores["cpv_match"] = 0
        else:
            scores["cpv_match"] = 0.5  # Neutral if no CPV info

        # Country matching
        if tender.buyer_country and profile.countries_of_interest:
            scores["country_match"] = 1.0 if tender.buyer_country in profile.countries_of_interest else 0.2
        elif profile.eu_wide:
            scores["country_match"] = 0.8
        else:
            scores["country_match"] = 0.5

        # Value matching
        if tender.estimated_value is not None:
            if profile.min_tender_value and tender.estimated_value < profile.min_tender_value:
                scores["value_match"] = 0.2
            elif profile.max_tender_value and tender.estimated_value > profile.max_tender_value:
                scores["value_match"] = 0.2
            else:
                scores["value_match"] = 1.0
        else:
            scores["value_match"] = 0.5  # Unknown value

        # Procedure type matching
        if tender.procedure_type and profile.preferred_procedures:
            scores["procedure_match"] = 1.0 if tender.procedure_type in profile.preferred_procedures else 0.3
        else:
            scores["procedure_match"] = 0.7  # Open procedure is usually SME-friendly

        # Deadline matching
        if tender.submission_deadline:
            days_until = (tender.submission_deadline - datetime.utcnow()).days
            min_days = profile.min_deadline_days or 30

            if days_until < min_days:
                scores["deadline_match"] = 0.2
            elif days_until < min_days * 2:
                scores["deadline_match"] = 0.7
            else:
                scores["deadline_match"] = 1.0
        else:
            scores["deadline_match"] = 0.5

        # Calculate weighted average
        total_score = sum(
            scores.get(key, 0) * weight
            for key, weight in weights.items()
        ) * 100  # Convert to 0-100 scale

        return total_score, scores

    def get_user_matches(
        self,
        user_id: str,
        include_dismissed: bool = False,
        saved_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[TenderMatch]:
        """
        Get tender matches for a user.

        Args:
            user_id: User UUID
            include_dismissed: Include dismissed matches
            saved_only: Only return saved matches
            limit: Maximum results
            offset: Result offset

        Returns:
            List of TenderMatch objects
        """
        query = self.db.query(TenderMatch).filter(
            TenderMatch.user_id == user_id
        )

        if not include_dismissed:
            query = query.filter(TenderMatch.is_dismissed == False)

        if saved_only:
            query = query.filter(TenderMatch.is_saved == True)

        query = query.order_by(desc(TenderMatch.match_score))
        query = query.offset(offset).limit(limit)

        return query.all()

    def search_tenders(
        self,
        query: Optional[str] = None,
        countries: Optional[List[str]] = None,
        cpv_codes: Optional[List[str]] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        status: str = "open",
        limit: int = 50,
        offset: int = 0
    ) -> List[Tender]:
        """
        Search stored tenders.

        Args:
            query: Text search query
            countries: Filter by countries
            cpv_codes: Filter by CPV codes
            min_value: Minimum value
            max_value: Maximum value
            status: Tender status
            limit: Maximum results
            offset: Result offset

        Returns:
            List of matching Tender objects
        """
        db_query = self.db.query(Tender)

        if status:
            db_query = db_query.filter(Tender.status == status)

        if countries:
            db_query = db_query.filter(Tender.buyer_country.in_(countries))

        if cpv_codes:
            # Match any of the provided CPV codes
            db_query = db_query.filter(
                Tender.cpv_codes.overlap(cpv_codes)
            )

        if min_value is not None:
            db_query = db_query.filter(Tender.estimated_value >= min_value)

        if max_value is not None:
            db_query = db_query.filter(Tender.estimated_value <= max_value)

        if query:
            # Simple text search on title
            db_query = db_query.filter(
                Tender.title.ilike(f"%{query}%")
            )

        db_query = db_query.order_by(desc(Tender.publication_date))
        db_query = db_query.offset(offset).limit(limit)

        return db_query.all()

    def get_tender(self, tender_id: int) -> Optional[Tender]:
        """Get a single tender by ID"""
        return self.db.query(Tender).filter(Tender.id == tender_id).first()

    def get_tender_by_publication(self, publication_number: str) -> Optional[Tender]:
        """Get a tender by publication number"""
        return self.db.query(Tender).filter(
            Tender.publication_number == publication_number
        ).first()

    def save_match(self, match_id: int, user_id: str) -> Optional[TenderMatch]:
        """Save a tender match for a user"""
        match = self.db.query(TenderMatch).filter(
            and_(
                TenderMatch.id == match_id,
                TenderMatch.user_id == user_id
            )
        ).first()

        if match:
            match.is_saved = True
            match.updated_at = datetime.utcnow()
            self.db.commit()

        return match

    def dismiss_match(self, match_id: int, user_id: str) -> Optional[TenderMatch]:
        """Dismiss a tender match"""
        match = self.db.query(TenderMatch).filter(
            and_(
                TenderMatch.id == match_id,
                TenderMatch.user_id == user_id
            )
        ).first()

        if match:
            match.is_dismissed = True
            match.updated_at = datetime.utcnow()
            self.db.commit()

        return match

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None

        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

        try:
            # Try YYYYMMDD format
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            pass

        return None

    def _build_ted_url(self, publication_number: str) -> str:
        """Build TED website URL for a notice"""
        return f"https://ted.europa.eu/udl?uri=TED:NOTICE:{publication_number}:TEXT:EN:HTML"

    def _get_country_names(self, country_codes: List[str]) -> List[str]:
        """Map ISO country codes to full names"""
        code_to_name = {
            "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
            "CY": "Cyprus", "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia",
            "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
            "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia",
            "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
            "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
            "SI": "Slovenia", "ES": "Spain", "SE": "Sweden"
        }
        return [code_to_name.get(code.upper(), code) for code in country_codes]

    def _calculate_sme_score(
        self,
        tender_data: Dict[str, Any],
        sme_profile: Optional[SMEProfile] = None
    ) -> Dict[str, Any]:
        """
        Calculate SME suitability score for a tender.

        Args:
            tender_data: Tender information dictionary
            sme_profile: Optional SME profile for personalized scoring

        Returns:
            Dictionary with SME analysis results
        """
        # Transform data to SME scorer format
        scorer_data = {
            "estimated_value": tender_data.get("estimatedValue", {}).get("amount")
                              if isinstance(tender_data.get("estimatedValue"), dict)
                              else tender_data.get("estimated_value"),
            "procedure_type": tender_data.get("procedureType") or tender_data.get("procedure_type"),
            "submission_deadline": tender_data.get("deadline") or tender_data.get("submission_deadline"),
            "has_lots": tender_data.get("hasLots", False) or tender_data.get("has_lots", False),
            "lot_count": tender_data.get("lotCount", 0) or tender_data.get("lot_count", 0),
            "cpv_codes": tender_data.get("cpvCodes") or tender_data.get("cpv_codes"),
            "buyer_country": tender_data.get("countryCode") or tender_data.get("buyer_country"),
            "is_framework": tender_data.get("isFramework", False) or tender_data.get("is_framework", False),
            "is_joint_procurement": tender_data.get("isJoint", False) or tender_data.get("is_joint_procurement", False),
            "selection_criteria": tender_data.get("selectionCriteria") or tender_data.get("selection_criteria"),
            "minimum_requirements": tender_data.get("minimumRequirements") or tender_data.get("minimum_requirements")
        }

        return self.sme_scorer.get_sme_analysis(scorer_data, sme_profile)

    def get_sme_score_for_tender(
        self,
        tender_id: int,
        company_size: str = "small",
        annual_turnover: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get personalized SME suitability score for a specific tender.

        Args:
            tender_id: Tender database ID
            company_size: "micro", "small", or "medium"
            annual_turnover: Company's annual turnover in EUR

        Returns:
            SME analysis dictionary or None if tender not found
        """
        tender = self.get_tender(tender_id)
        if not tender:
            return None

        # Build SME profile
        size_map = {
            "micro": SMECategory.MICRO,
            "small": SMECategory.SMALL,
            "medium": SMECategory.MEDIUM
        }

        profile = SMEProfile(
            size=size_map.get(company_size, SMECategory.SMALL),
            annual_turnover=annual_turnover
        )

        # Build tender data dict from model
        tender_data = {
            "estimated_value": tender.estimated_value,
            "procedure_type": tender.procedure_type,
            "submission_deadline": tender.submission_deadline.isoformat() if tender.submission_deadline else None,
            "has_lots": tender.has_lots,
            "lot_count": tender.lot_count,
            "cpv_codes": tender.cpv_codes,
            "buyer_country": tender.buyer_country,
            "is_framework": tender.is_framework,
            "is_joint_procurement": tender.is_joint_procurement,
            "selection_criteria": tender.selection_criteria,
            "minimum_requirements": tender.minimum_requirements
        }

        return self.sme_scorer.get_sme_analysis(tender_data, profile)

    def batch_score_sme_suitability(
        self,
        tender_ids: Optional[List[int]] = None,
        recalculate: bool = False
    ) -> int:
        """
        Calculate SME suitability scores for multiple tenders.

        Args:
            tender_ids: Specific tender IDs to score (None = all unscored)
            recalculate: Force recalculation even if score exists

        Returns:
            Number of tenders scored
        """
        if tender_ids:
            query = self.db.query(Tender).filter(Tender.id.in_(tender_ids))
        elif recalculate:
            query = self.db.query(Tender)
        else:
            query = self.db.query(Tender).filter(Tender.sme_suitability_score == None)

        tenders = query.all()
        scored_count = 0

        for tender in tenders:
            tender_data = {
                "estimated_value": tender.estimated_value,
                "procedure_type": tender.procedure_type,
                "submission_deadline": tender.submission_deadline.isoformat() if tender.submission_deadline else None,
                "has_lots": tender.has_lots,
                "lot_count": tender.lot_count,
                "cpv_codes": tender.cpv_codes,
                "buyer_country": tender.buyer_country,
                "is_framework": tender.is_framework,
                "is_joint_procurement": tender.is_joint_procurement,
                "selection_criteria": tender.selection_criteria,
                "minimum_requirements": tender.minimum_requirements
            }

            analysis = self.sme_scorer.get_sme_analysis(tender_data)
            tender.sme_suitability_score = analysis.get("sme_suitability_score")
            tender.sme_score_breakdown = analysis.get("score_breakdown")
            tender.updated_at = datetime.utcnow()
            scored_count += 1

        self.db.commit()
        logger.info(f"Scored {scored_count} tenders for SME suitability")

        return scored_count
