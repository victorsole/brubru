"""
Reference Data Service

Fast in-memory access to reference data (calendars, institutions).
Provides optimized lookup methods for AI context building.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from .knowledge_loader import get_knowledge_loader, KnowledgeLoader

logger = logging.getLogger(__name__)


class ReferenceDataService:
    """
    Fast access to reference data.

    Optimized for common queries:
    - "When is the next plenary session?"
    - "Who is the Agriculture Commissioner?"
    - "What does ENVI committee cover?"
    """

    def __init__(self, knowledge_loader: Optional[KnowledgeLoader] = None):
        """
        Initialize reference data service.

        Args:
            knowledge_loader: Knowledge loader instance
        """
        self.loader = knowledge_loader or get_knowledge_loader()
        logger.info("Initialized ReferenceDataService")

    # =========================================================================
    # Calendar Queries
    # =========================================================================

    def get_upcoming_plenary_sessions(
        self,
        from_date: Optional[date] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming EP plenary sessions.

        Args:
            from_date: Start date (default: today)
            limit: Maximum number of sessions to return

        Returns:
            List of plenary sessions with dates and info
        """
        if from_date is None:
            from_date = date.today()

        sessions = []

        # Check both 2025 and 2026 calendars
        for year in [2025, 2026]:
            calendar_key = f"ep_calendar_{year}"
            if calendar_key not in self.loader.calendars:
                continue

            calendar = self.loader.calendars[calendar_key]
            months = calendar.get("months", {})

            for month_name, month_data in months.items():
                for week in month_data.get("weeks", []):
                    if week.get("activity_type") == "plenary_session":
                        # Parse dates
                        dates_str = week.get("dates", "")
                        # Extract start date (format: "2025-01-13 to 2025-01-19")
                        start_date_str = dates_str.split(" to ")[0] if " to " in dates_str else dates_str

                        try:
                            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

                            if start_date >= from_date:
                                sessions.append({
                                    "start_date": start_date_str,
                                    "dates_range": dates_str,
                                    "week_number": week.get("week_number"),
                                    "year": year,
                                    "month": month_name,
                                    "session_days": week.get("session_days", [])
                                })
                        except ValueError:
                            logger.warning(f"Could not parse date: {start_date_str}")
                            continue

        # Sort by date and limit
        sessions.sort(key=lambda x: x["start_date"])
        return sessions[:limit]

    def get_calendar_week(
        self,
        year: int,
        week_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get calendar information for a specific week.

        Args:
            year: Calendar year
            week_number: Week number (1-52)

        Returns:
            Week information or None
        """
        calendar_key = f"ep_calendar_{year}"
        if calendar_key not in self.loader.calendars:
            return None

        calendar = self.loader.calendars[calendar_key]
        months = calendar.get("months", {})

        for month_name, month_data in months.items():
            for week in month_data.get("weeks", []):
                if week.get("week_number") == week_number:
                    return {
                        **week,
                        "year": year,
                        "month": month_name
                    }

        return None

    # =========================================================================
    # Institution Queries
    # =========================================================================

    def find_commissioner_by_portfolio(self, portfolio_keyword: str) -> Optional[Dict[str, Any]]:
        """
        Find commissioner by portfolio keyword.

        Args:
            portfolio_keyword: Keyword like "agriculture", "digital", "trade"

        Returns:
            Commissioner information or None
        """
        return self.loader.find_commissioner(portfolio_keyword)

    def find_dg_by_name(self, dg_name_or_acronym: str) -> Optional[Dict[str, Any]]:
        """
        Find Directorate-General by name or acronym.

        Args:
            dg_name_or_acronym: DG name or acronym (e.g., "AGRI", "agriculture")

        Returns:
            DG information or None
        """
        ec_dg_data = self.loader.institutions.get("ec_dg", {})
        dgs = ec_dg_data.get("directorates_general", [])

        query_lower = dg_name_or_acronym.lower()
        query_upper = dg_name_or_acronym.upper()

        for dg in dgs:
            # Match acronym
            if dg.get("acronym") == query_upper:
                return dg
            # Match name
            dg_name = dg.get("name", {})
            if isinstance(dg_name, dict):
                # Multi-language name
                for lang, name in dg_name.items():
                    if query_lower in name.lower():
                        return dg
            elif isinstance(dg_name, str):
                if query_lower in dg_name.lower():
                    return dg

        return None

    def find_committee(self, committee_name_or_acronym: str) -> Optional[Dict[str, Any]]:
        """
        Find EP committee by name or acronym.

        Args:
            committee_name_or_acronym: Committee acronym (e.g., "ENVI") or partial name

        Returns:
            Committee information or None
        """
        return self.loader.find_committee(committee_name_or_acronym)

    def list_committees_by_policy_area(self, policy_keyword: str) -> List[Dict[str, Any]]:
        """
        Find committees by policy area keyword.

        Args:
            policy_keyword: Policy keyword (e.g., "environment", "digital", "trade")

        Returns:
            List of matching committees
        """
        ep_structure = self.loader.institutions.get("ep_organisational_structure", {})
        committees_data = ep_structure.get("parliamentary_committees", {})

        query_lower = policy_keyword.lower()
        matches = []

        # Search in categories
        for category in committees_data.get("categories", []):
            for committee in category.get("committees", []):
                # Check policy areas
                policy_areas = committee.get("policy_areas", [])
                policy_text = " ".join(policy_areas).lower()

                # Check full name
                full_name = committee.get("full_name", "").lower()

                if query_lower in policy_text or query_lower in full_name:
                    matches.append(committee)

        return matches

    def get_political_group(self, group_acronym: str) -> Optional[Dict[str, Any]]:
        """
        Get political group information by acronym.

        Args:
            group_acronym: Group acronym (e.g., "EPP", "S&D", "Renew")

        Returns:
            Political group information or None
        """
        ep_structure = self.loader.institutions.get("ep_organisational_structure", {})
        political_groups = ep_structure.get("political_groups", {})

        for group in political_groups.get("groups", []):
            if group.get("acronym") == group_acronym.upper():
                return group

        return None

    def find_permanent_representation(self, country: str) -> Optional[Dict[str, Any]]:
        """
        Find Permanent Representation by country name or code.

        Args:
            country: Country name or ISO code (e.g., "Germany", "DE")

        Returns:
            PermRep information or None
        """
        permreps_data = self.loader.institutions.get("permreps", {})
        permreps = permreps_data.get("permanent_representations", [])

        query_lower = country.lower()
        query_upper = country.upper()

        for permrep in permreps:
            # Match country code
            if permrep.get("country_code") == query_upper:
                return permrep
            # Match country name
            if query_lower in permrep.get("country", "").lower():
                return permrep

        return None

    # =========================================================================
    # Organigramme Queries
    # =========================================================================

    def find_commission_official(self, name: str) -> Optional[str]:
        """
        Find Commission official and return formatted context.

        Args:
            name: Person's name

        Returns:
            Formatted context string or None
        """
        matches = self.loader.find_person_in_commission(name)

        if matches:
            context = f"**Commission Officials matching '{name}':**\n\n"
            for match in matches[:5]:  # Limit to 5 results
                context += f"- **{match['name']}** - {match['position']}\n"
                context += f"  DG: {match['dg_name']} ({match['dg']})\n"
                if match.get('area'):
                    context += f"  Area: {match['area']}\n"
                if match.get('directorate'):
                    context += f"  Directorate: {match['directorate']}\n"
                if match.get('unit'):
                    context += f"  Unit: {match['unit']}\n"
                context += "\n"
            return context

        return None

    def get_dg_info(self, dg_code: str) -> Optional[str]:
        """
        Get DG structure information as formatted context.

        Args:
            dg_code: DG code (e.g., "CLIMA", "AGRI")

        Returns:
            Formatted context string or None
        """
        summary = self.loader.get_dg_structure_summary(dg_code)

        if summary:
            context = f"**{summary['full_name']} ({summary['dg_code']})**\n\n"
            if summary.get('commissioner'):
                context += f"- Commissioner: {summary['commissioner']}\n"
            if summary.get('director_general'):
                context += f"- Director-General: {summary['director_general']}\n"
            if summary.get('deputy_dg'):
                context += f"- Deputy Director-General: {summary['deputy_dg']}\n"
            context += f"- Structure: {summary['num_directorates']} Directorates, {summary['num_units']} Units\n"
            return context

        return None

    def find_unit_info(self, unit_query: str, dg_code: Optional[str] = None) -> Optional[str]:
        """
        Find Commission units and return formatted context.

        Args:
            unit_query: Unit name or keyword
            dg_code: Optional DG code to narrow search

        Returns:
            Formatted context string or None
        """
        matches = self.loader.find_unit_by_name(unit_query, dg_code)

        if matches:
            context = f"**Units matching '{unit_query}':**\n\n"
            for match in matches[:10]:  # Limit to 10 results
                context += f"- **{match['unit_name']}** ({match.get('unit_code', 'N/A')})\n"
                context += f"  DG: {match['dg_name']} ({match['dg']})\n"
                context += f"  Directorate: {match.get('directorate', 'N/A')}\n"
                if match.get('head'):
                    context += f"  Head: {match['head']}\n"
                context += "\n"
            return context

        return None

    # =========================================================================
    # Context Building Helpers
    # =========================================================================

    def build_calendar_context(self, query: str) -> Optional[str]:
        """
        Build calendar context for AI from query.

        Args:
            query: User query (e.g., "when is next plenary")

        Returns:
            Formatted context string or None
        """
        query_lower = query.lower()

        # Detect plenary session queries
        if "plenary" in query_lower or "session" in query_lower:
            sessions = self.get_upcoming_plenary_sessions(limit=3)
            if sessions:
                context = "📅 **Upcoming EP Plenary Sessions:**\n\n"
                for session in sessions:
                    context += f"- **{session['start_date']}** ({session['dates_range']})\n"
                    if session.get('session_days'):
                        context += f"  Days: {', '.join(session['session_days'])}\n"
                return context

        # Could add more calendar query patterns here
        return None

    def build_institution_context(self, query: str) -> Optional[str]:
        """
        Build institution context for AI from query.

        Args:
            query: User query

        Returns:
            Formatted context string or None
        """
        query_lower = query.lower()

        # Check for DG queries (e.g., "DG CLIMA", "DG Climate")
        dg_patterns = [
            "dg clima", "dg climate", "dg agri", "dg agriculture", "dg connect",
            "dg digital", "dg env", "dg environment", "dg trade", "dg energy",
            "dg comp", "dg competition", "dg grow", "dg employment", "dg empl"
        ]

        for pattern in dg_patterns:
            if pattern in query_lower:
                # Extract DG code
                if "clima" in pattern or "climate" in pattern:
                    dg_info = self.get_dg_info("CLIMA")
                    if dg_info:
                        return dg_info
                elif "agri" in pattern or "agriculture" in pattern:
                    dg_info = self.get_dg_info("AGRI")
                    if dg_info:
                        return dg_info
                elif "connect" in pattern or "digital" in pattern:
                    dg_info = self.get_dg_info("CONNECT")
                    if dg_info:
                        return dg_info
                # Add more DG mappings as needed

        # Check for person name queries (contains capital letters suggesting name)
        words = query.split()
        for i, word in enumerate(words):
            # Look for capitalized words that might be names
            if len(word) > 3 and word[0].isupper() and i + 1 < len(words) and words[i+1][0].isupper():
                # Potential name (e.g., "Kurt Vandenberghe")
                potential_name = f"{word} {words[i+1]}"
                official_info = self.find_commission_official(potential_name)
                if official_info:
                    return official_info

        # Check for unit queries
        if "unit" in query_lower:
            # Extract potential unit name
            for keyword in ["climate", "digital", "energy", "trade", "environment"]:
                if keyword in query_lower:
                    unit_info = self.find_unit_info(keyword)
                    if unit_info:
                        return unit_info

        # Commissioner queries
        if "commissioner" in query_lower:
            # Try to extract policy area
            for keyword in ["agriculture", "trade", "digital", "competition", "energy", "environment"]:
                if keyword in query_lower:
                    commissioner = self.find_commissioner_by_portfolio(keyword)
                    if commissioner:
                        context = f"**Commissioner for {commissioner.get('portfolio', '')}:**\n"
                        context += f"- Name: {commissioner.get('name', '')}\n"
                        context += f"- Country: {commissioner.get('country', '')}\n"
                        if commissioner.get('dg_oversight'):
                            context += f"- DG Oversight: {', '.join(commissioner['dg_oversight'])}\n"
                        return context

        # Committee queries
        if "committee" in query_lower or any(acronym in query.upper() for acronym in ["ENVI", "AGRI", "ITRE", "ECON", "LIBE"]):
            # Try to find committee mention
            words = query.split()
            for word in words:
                committee = self.find_committee(word)
                if committee:
                    context = f"**{committee.get('full_name', '')} ({committee.get('acronym', '')})**\n"
                    context += f"- Type: {committee.get('type', '')}\n"
                    if committee.get('policy_areas'):
                        context += f"- Policy areas: {', '.join(committee['policy_areas'])}\n"
                    if committee.get('url'):
                        context += f"- URL: {committee['url']}\n"
                    return context

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get reference data statistics"""
        return self.loader.get_stats()


# Global singleton
_reference_data_service: Optional[ReferenceDataService] = None


def get_reference_data_service(
    knowledge_loader: Optional[KnowledgeLoader] = None
) -> ReferenceDataService:
    """
    Get global reference data service instance.

    Args:
        knowledge_loader: Knowledge loader instance

    Returns:
        ReferenceDataService instance
    """
    global _reference_data_service

    if _reference_data_service is None:
        _reference_data_service = ReferenceDataService(knowledge_loader)

    return _reference_data_service
