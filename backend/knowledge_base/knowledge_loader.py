"""
Knowledge Base Loader

Loads and indexes internal knowledge base (calendars, institutions, templates)
for use in AI chat context.

Features:
- Load JSON reference data (calendars, institutions) into memory
- Index templates into ChromaDB for semantic search
- Provide unified query interface
- Hot-reload support for knowledge updates
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)


# Keyword triggers for guide matching
# Maps keywords (lowercase) to guide file stems that should be surfaced
# when those keywords appear in user queries
GUIDE_KEYWORD_TRIGGERS: Dict[str, List[str]] = {
    # Horizon Europe Grant Management
    'grant': ['horizon_europe_grant_management'],
    'mga': ['horizon_europe_grant_management'],
    'model grant agreement': ['horizon_europe_grant_management'],
    'consortium': ['horizon_europe_grant_management'],
    'horizon europe': ['horizon_europe_grant_management'],
    'gap process': ['horizon_europe_grant_management'],
    'eligible costs': ['horizon_europe_grant_management'],
    'lump sum': ['horizon_europe_grant_management'],
    'grant agreement preparation': ['horizon_europe_grant_management'],
    'form c': ['horizon_europe_grant_management'],

    # EU Financial Regulation Procurement
    'procurement': ['eu_financial_regulation_procurement'],
    'tender': ['eu_financial_regulation_procurement'],
    'framework contract': ['eu_financial_regulation_procurement'],
    'financial regulation': ['eu_financial_regulation_procurement', 'eu_budget_emu_law'],
    'evaluation committee': ['eu_financial_regulation_procurement'],
    'open procedure': ['eu_financial_regulation_procurement'],
    'restricted procedure': ['eu_financial_regulation_procurement'],
    'competitive dialogue': ['eu_financial_regulation_procurement'],
    'lafr': ['eu_financial_regulation_procurement'],
    'la fr': ['eu_financial_regulation_procurement'],
    'le rf': ['eu_financial_regulation_procurement'],
    'the fr': ['eu_financial_regulation_procurement'],
    'reglamento financiero': ['eu_financial_regulation_procurement'],
    'reglement financier': ['eu_financial_regulation_procurement'],

    # Competition Law Enforcement
    'antitrust': ['competition_law_enforcement'],
    'cartel': ['competition_law_enforcement'],
    'article 101': ['competition_law_enforcement'],
    'article 102': ['competition_law_enforcement'],
    'dawn raid': ['competition_law_enforcement'],
    'leniency': ['competition_law_enforcement'],
    'dg comp': ['competition_law_enforcement'],
    'dominance': ['competition_law_enforcement'],
    'merger control': ['competition_law_enforcement'],
    'statement of objections': ['competition_law_enforcement'],
    'fining guidelines': ['competition_law_enforcement'],

    # EU Budget and EMU Law
    'mff': ['eu_budget_emu_law'],
    'multiannual financial framework': ['eu_budget_emu_law'],
    'own resources': ['eu_budget_emu_law'],
    'esm': ['eu_budget_emu_law'],
    'olaf': ['eu_budget_emu_law', 'cohesion_policy_audit'],
    'eppo': ['eu_budget_emu_law'],
    'eib': ['eu_budget_emu_law'],
    'investeu': ['eu_budget_emu_law', 'knowledge_valorisation_tech_transfer'],
    'budget': ['eu_budget_emu_law'],
    'discharge': ['eu_budget_emu_law'],
    'stability and growth pact': ['eu_budget_emu_law'],

    # Employment and Future of Work
    'platform work': ['employment_future_of_work'],
    'right to disconnect': ['employment_future_of_work'],
    'youth guarantee': ['employment_future_of_work'],
    'esf+': ['employment_future_of_work', 'cohesion_policy_audit'],
    'algorithmic management': ['employment_future_of_work'],
    'just transition fund': ['employment_future_of_work', 'cohesion_policy_audit'],
    'pillar of social rights': ['employment_future_of_work'],
    'platform workers': ['employment_future_of_work'],
    'traineeships': ['employment_future_of_work'],

    # European Semester Communication
    'european semester': ['european_semester_communication'],
    'economic forecast': ['european_semester_communication'],
    'rrf': ['european_semester_communication', 'eu_budget_emu_law'],
    'recovery and resilience': ['european_semester_communication', 'eu_budget_emu_law'],
    'digital euro': ['european_semester_communication'],
    'csr': ['european_semester_communication'],
    'country report': ['european_semester_communication'],
    'country-specific recommendation': ['european_semester_communication'],
    'annual sustainable growth survey': ['european_semester_communication'],

    # Cohesion Policy Audit
    'cohesion': ['cohesion_policy_audit'],
    'audit': ['cohesion_policy_audit'],
    'erdf': ['cohesion_policy_audit'],
    'arachne': ['cohesion_policy_audit'],
    'error rate': ['cohesion_policy_audit'],
    'shared management': ['cohesion_policy_audit'],
    'managing authority': ['cohesion_policy_audit'],
    'audit authority': ['cohesion_policy_audit'],
    'financial corrections': ['cohesion_policy_audit'],
    'common provisions regulation': ['cohesion_policy_audit'],

    # Financial Supervision (EBA/MiCA/DORA)
    'eba': ['financial_supervision_eba'],
    'eiopa': ['financial_supervision_eba'],
    'esma': ['financial_supervision_eba'],
    'prudential': ['financial_supervision_eba'],
    'on-site inspection': ['financial_supervision_eba'],
    'supervisory college': ['financial_supervision_eba'],
    'ctpp': ['financial_supervision_eba'],
    'mica': ['financial_supervision_eba'],
    'dora': ['financial_supervision_eba'],
    'crypto-asset': ['financial_supervision_eba'],
    'significant token': ['financial_supervision_eba'],

    # Eurostat Statistics Production
    'eurostat': ['eurostat_statistics_production'],
    'itss': ['eurostat_statistics_production'],
    'fats': ['eurostat_statistics_production'],
    'fdi': ['eurostat_statistics_production'],
    'ebops': ['eurostat_statistics_production'],
    'statistics': ['eurostat_statistics_production'],
    'asymmetry': ['eurostat_statistics_production'],
    'data quality': ['eurostat_statistics_production'],
    'nsi': ['eurostat_statistics_production'],
    'trade in services': ['eurostat_statistics_production'],

    # Knowledge Valorisation and Technology Transfer
    'knowledge valorisation': ['knowledge_valorisation_tech_transfer'],
    'technology transfer': ['knowledge_valorisation_tech_transfer'],
    'trl': ['knowledge_valorisation_tech_transfer'],
    'ip management': ['knowledge_valorisation_tech_transfer'],
    'era': ['knowledge_valorisation_tech_transfer'],
    'eic': ['knowledge_valorisation_tech_transfer'],
    'eic pathfinder': ['knowledge_valorisation_tech_transfer'],
    'eic accelerator': ['knowledge_valorisation_tech_transfer'],
    'spin-off': ['knowledge_valorisation_tech_transfer'],
    'technology readiness': ['knowledge_valorisation_tech_transfer'],
    'valley of death': ['knowledge_valorisation_tech_transfer'],

    # Bioeconomy and Food Systems
    'bioeconomy': ['bioeconomy_food_systems'],
    'food2030': ['bioeconomy_food_systems'],
    'scar': ['bioeconomy_food_systems'],
    'alternative proteins': ['bioeconomy_food_systems'],
    'living labs': ['bioeconomy_food_systems'],
    'food systems': ['bioeconomy_food_systems'],
    'cellular agriculture': ['bioeconomy_food_systems'],
    'precision fermentation': ['bioeconomy_food_systems'],
    'novel food': ['bioeconomy_food_systems'],
    'biorefinery': ['bioeconomy_food_systems'],

    # EU Space Programme
    'galileo': ['eu_space_programme'],
    'copernicus': ['eu_space_programme'],
    'iris2': ['eu_space_programme'],
    'space act': ['eu_space_programme'],
    'space debris': ['eu_space_programme'],
    'euspa': ['eu_space_programme'],
    'autonomous access': ['eu_space_programme'],
    'ariane': ['eu_space_programme'],
    'sentinel': ['eu_space_programme'],
    'space programme': ['eu_space_programme'],
    'egnos': ['eu_space_programme'],

    # Road Safety, Autonomous Vehicles and ADAS
    'road safety': ['road_safety_autonomous_vehicles'],
    'adas': ['road_safety_autonomous_vehicles'],
    'autonomous vehicle': ['road_safety_autonomous_vehicles'],
    'automated driving': ['road_safety_autonomous_vehicles'],
    'self-driving': ['road_safety_autonomous_vehicles'],
    'vehicle safety': ['road_safety_autonomous_vehicles'],
    'type-approval': ['road_safety_autonomous_vehicles'],
    'type approval': ['road_safety_autonomous_vehicles'],
    'general safety regulation': ['road_safety_autonomous_vehicles'],
    'gsr': ['road_safety_autonomous_vehicles'],
    'emergency braking': ['road_safety_autonomous_vehicles'],
    'lane keeping': ['road_safety_autonomous_vehicles'],
    'speed assistance': ['road_safety_autonomous_vehicles'],
    'ecall': ['road_safety_autonomous_vehicles'],
    'euro ncap': ['road_safety_autonomous_vehicles'],
    'unece': ['road_safety_autonomous_vehicles'],
    'dg move': ['road_safety_autonomous_vehicles'],
    'vehicle autonom': ['road_safety_autonomous_vehicles'],
    'vehicule autonome': ['road_safety_autonomous_vehicles'],
    'seguretat viaria': ['road_safety_autonomous_vehicles'],
    'securite routiere': ['road_safety_autonomous_vehicles'],
    'seguridad vial': ['road_safety_autonomous_vehicles'],
    'driving licence': ['road_safety_autonomous_vehicles'],
    'connected vehicle': ['road_safety_autonomous_vehicles'],
    'cybersecurity vehicle': ['road_safety_autonomous_vehicles'],

    # REACH and Chemicals Regulation
    'reach': ['reach_chemicals_regulation'],
    'chemicals': ['reach_chemicals_regulation'],
    'chemical substances': ['reach_chemicals_regulation'],
    'echa': ['reach_chemicals_regulation'],
    'pfas': ['reach_chemicals_regulation'],
    'svhc': ['reach_chemicals_regulation'],
    'substances of very high concern': ['reach_chemicals_regulation'],
    'restriction proposal': ['reach_chemicals_regulation'],
    'annex xiv': ['reach_chemicals_regulation'],
    'annex xvii': ['reach_chemicals_regulation'],
    'authorisation list': ['reach_chemicals_regulation'],
    'candidate list': ['reach_chemicals_regulation'],
    'microplastics': ['reach_chemicals_regulation'],
    'bisphenol': ['reach_chemicals_regulation'],
    'clp regulation': ['reach_chemicals_regulation'],
    'biocidal': ['reach_chemicals_regulation'],
    'chemicals strategy': ['reach_chemicals_regulation'],
    'one substance one assessment': ['reach_chemicals_regulation'],
    'osoa': ['reach_chemicals_regulation'],
    'reglament reach': ['reach_chemicals_regulation'],

    # Multilingual, Translation and Content Localisation Law
    'translation': ['multilingual_content_law'],
    'localisation': ['multilingual_content_law'],
    'localization': ['multilingual_content_law'],
    'multilingual': ['multilingual_content_law'],
    'language requirements': ['multilingual_content_law'],
    'official languages': ['multilingual_content_law'],
    'content localisation': ['multilingual_content_law'],
    'content localization': ['multilingual_content_law'],
    'subtitling': ['multilingual_content_law'],
    'audio description': ['multilingual_content_law'],
    'labelling language': ['multilingual_content_law'],
    'etranslation': ['multilingual_content_law'],
    'avmsd': ['multilingual_content_law'],
    'audiovisual media': ['multilingual_content_law'],
    'european works': ['multilingual_content_law'],
    'media freedom': ['multilingual_content_law'],
    'en 17100': ['multilingual_content_law'],
    'dg translation': ['multilingual_content_law'],
    'linguistic diversity': ['multilingual_content_law'],
    'plain language': ['multilingual_content_law'],
    'package leaflet': ['multilingual_content_law'],
    'food labelling': ['multilingual_content_law'],
}


class KnowledgeLoader:
    """
    Load and manage internal knowledge base.

    Architecture:
    - Static JSON files (calendars, institutions) → In-memory cache
    - Templates (Markdown) → ChromaDB vector store
    - Unified query interface for AI context
    """

    def __init__(self, knowledge_base_dir: str = None):
        """
        Initialize knowledge loader.

        Args:
            knowledge_base_dir: Path to knowledge_base directory
        """
        if knowledge_base_dir is None:
            # Default to backend/knowledge_base
            current_dir = Path(__file__).parent
            knowledge_base_dir = str(current_dir)

        self.knowledge_base_dir = Path(knowledge_base_dir)

        # Directories
        self.calendars_dir = self.knowledge_base_dir / "calendars"
        self.institutions_dir = self.knowledge_base_dir / "institutions"
        self.templates_dir = self.knowledge_base_dir / "templates"
        self.organigrammes_dir = self.knowledge_base_dir / "ec_organigrammes" / "json"
        self.analytics_dir = self.knowledge_base_dir / "analytics"
        self.guides_dir = self.knowledge_base_dir / "guides"
        self.requirements_dir = self.knowledge_base_dir / "requirements"

        # In-memory caches
        self.calendars: Dict[str, Any] = {}
        self.institutions: Dict[str, Any] = {}
        self.templates: Dict[str, str] = {}
        self.organigrammes: Dict[str, Any] = {}  # DG organizational charts
        self.analytics: Dict[str, Any] = {}      # Analytics snapshots (e.g., EU law)
        self.guides: Dict[str, str] = {}         # Reference guides (EU jargon, resources, etc.)
        self.requirements: Dict[str, Any] = {}   # EU law requirements by cluster

        # Metadata
        self.last_loaded: Optional[datetime] = None
        self.stats: Dict[str, int] = {}

        logger.info(f"Initialized KnowledgeLoader at {self.knowledge_base_dir}")

    def load_all(self) -> Dict[str, Any]:
        """
        Load all knowledge base content.

        Returns:
            Statistics about loaded content
        """
        logger.info("Loading knowledge base...")
        start_time = datetime.now()

        # Load reference data
        self._load_calendars()
        self._load_institutions()
        self._load_templates()
        self._load_organigrammes()
        self._load_analytics()
        self._load_guides()
        self._load_requirements()

        self.last_loaded = datetime.now()
        load_time = (self.last_loaded - start_time).total_seconds()

        # Count total requirements across all clusters
        total_requirements = sum(
            len(cluster.get('requirements', []))
            for cluster in self.requirements.values()
        )

        self.stats = {
            'calendars': len(self.calendars),
            'institutions': len(self.institutions),
            'templates': len(self.templates),
            'organigrammes': len(self.organigrammes),
            'analytics': len(self.analytics),
            'guides': len(self.guides),
            'requirement_clusters': len(self.requirements),
            'total_requirements': total_requirements,
            'load_time_seconds': load_time
        }

        logger.info(f"Loaded knowledge base in {load_time:.2f}s: {self.stats}")
        return self.stats

    # =========================================================================
    # Loading Methods
    # =========================================================================

    def _load_calendars(self):
        """Load calendar JSON files into memory"""
        if not self.calendars_dir.exists():
            logger.warning(f"Calendars directory not found: {self.calendars_dir}")
            return

        for json_file in self.calendars_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "ep_calendar_2025"
                    self.calendars[key] = data
                    logger.debug(f"Loaded calendar: {key}")
            except Exception as e:
                logger.error(f"Failed to load calendar {json_file}: {str(e)}")

    def _load_institutions(self):
        """Load institution JSON files into memory"""
        if not self.institutions_dir.exists():
            logger.warning(f"Institutions directory not found: {self.institutions_dir}")
            return

        for json_file in self.institutions_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "commissioners"
                    self.institutions[key] = data
                    logger.debug(f"Loaded institution data: {key}")
            except Exception as e:
                logger.error(f"Failed to load institution data {json_file}: {str(e)}")

    def _load_templates(self):
        """Load template Markdown files into memory"""
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return

        for md_file in self.templates_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    key = md_file.stem  # e.g., "briefing_note"
                    self.templates[key] = content
                    logger.debug(f"Loaded template: {key}")
            except Exception as e:
                logger.error(f"Failed to load template {md_file}: {str(e)}")

    def _load_organigrammes(self):
        """Load EC organigramme JSON files into memory"""
        if not self.organigrammes_dir.exists():
            logger.warning(f"Organigrammes directory not found: {self.organigrammes_dir}")
            return

        for json_file in self.organigrammes_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "CLIMA", "AGRI"
                    self.organigrammes[key] = data
                    logger.debug(f"Loaded organigramme: {key}")
            except Exception as e:
                logger.error(f"Failed to load organigramme {json_file}: {str(e)}")

    def _load_analytics(self):
        """Load analytics snapshots (e.g., eu_law_snapshot.json)"""
        if not self.analytics_dir.exists():
            # Not critical; analytics are optional
            logger.info(f"Analytics directory not found: {self.analytics_dir}")
            return

        for json_file in self.analytics_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    key = json_file.stem  # e.g., "eu_law_snapshot"
                    self.analytics[key] = data
                    logger.debug(f"Loaded analytics snapshot: {key}")
            except Exception as e:
                logger.error(f"Failed to load analytics snapshot {json_file}: {str(e)}")

    def get_analytics_snapshot(self, key: str) -> Optional[Dict[str, Any]]:
        """Get analytics snapshot by key (e.g., 'eu_law_snapshot')."""
        return self.analytics.get(key)

    def _load_guides(self):
        """Load reference guide Markdown files into memory"""
        if not self.guides_dir.exists():
            logger.info(f"Guides directory not found: {self.guides_dir}")
            return

        for md_file in self.guides_dir.glob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    key = md_file.stem  # e.g., "eu_jargon", "council_guide"
                    self.guides[key] = content
                    logger.debug(f"Loaded guide: {key}")
            except Exception as e:
                logger.error(f"Failed to load guide {md_file}: {str(e)}")

    def _load_requirements(self):
        """Load EU law requirements from JSON files into memory"""
        if not self.requirements_dir.exists():
            logger.info(f"Requirements directory not found: {self.requirements_dir}")
            return

        for json_file in self.requirements_dir.glob("*.json"):
            # Skip index file
            if json_file.name.startswith("_"):
                continue

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Use cluster_id as key for quick lookup
                    cluster_id = data.get('cluster_id')
                    if cluster_id:
                        self.requirements[str(cluster_id)] = data
                        logger.debug(f"Loaded requirements for cluster {cluster_id}: {data.get('cluster_name')}")
            except Exception as e:
                logger.error(f"Failed to load requirements {json_file}: {str(e)}")

        # Load index if exists
        index_path = self.requirements_dir / "_index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    self.requirements['_index'] = json.load(f)
                    logger.debug("Loaded requirements index")
            except Exception as e:
                logger.error(f"Failed to load requirements index: {str(e)}")

    # =========================================================================
    # Query Methods - Reference Data
    # =========================================================================

    def query_calendar(
        self,
        year: int = None,
        month: str = None,
        activity_type: str = None
    ) -> Dict[str, Any]:
        """
        Query calendar data.

        Args:
            year: Calendar year (2025, 2026)
            month: Month name (january, february, etc.)
            activity_type: Activity type filter (plenary_session, committee_week, etc.)

        Returns:
            Filtered calendar data

        Example:
            >>> query_calendar(year=2025, month="january", activity_type="plenary_session")
        """
        if year:
            calendar_key = f"ep_calendar_{year}"
            if calendar_key not in self.calendars:
                return {"error": f"Calendar for year {year} not found"}

            calendar = self.calendars[calendar_key]

            # Filter by month if specified
            if month:
                month_lower = month.lower()
                if month_lower in calendar.get('months', {}):
                    month_data = calendar['months'][month_lower]

                    # Filter by activity type if specified
                    if activity_type:
                        filtered_weeks = [
                            week for week in month_data.get('weeks', [])
                            if week.get('activity_type') == activity_type
                        ]
                        return {
                            'year': year,
                            'month': month,
                            'activity_type': activity_type,
                            'weeks': filtered_weeks
                        }

                    return month_data
                else:
                    return {"error": f"Month {month} not found in {year} calendar"}

            return calendar

        # No specific year, return all calendars
        return self.calendars

    def query_institution(
        self,
        institution_type: str,
        query_filter: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Query institution data.

        Args:
            institution_type: Type of institution data
                - "commissioners"
                - "ec_dg"
                - "ep_organisational_structure"
                - "eu_institutions"
                - "eu_policies"
                - "permreps"
            query_filter: Optional filters (e.g., {"country": "Germany"})

        Returns:
            Institution data (filtered if applicable)

        Example:
            >>> query_institution("commissioners", {"country": "Spain"})
            >>> query_institution("ep_organisational_structure")
        """
        if institution_type not in self.institutions:
            return {"error": f"Institution type '{institution_type}' not found"}

        data = self.institutions[institution_type]

        # If no filter, return all
        if not query_filter:
            return data

        # Apply filters (basic implementation)
        # This is simplified - you can make it more sophisticated
        return data

    def find_commissioner(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find commissioner by name, country, or portfolio.

        Args:
            query: Search query (name, country, or portfolio keyword)

        Returns:
            Commissioner data or None

        Example:
            >>> find_commissioner("agriculture")
            >>> find_commissioner("Spain")
        """
        commissioners_data = self.institutions.get("commissioners", {})
        college = commissioners_data.get("college", {})

        query_lower = query.lower()

        # Search in president
        president = college.get("president", {})
        if self._matches_commissioner(president, query_lower):
            return president

        # Search in EVPs
        for evp in college.get("executive_vice_presidents", []):
            if self._matches_commissioner(evp, query_lower):
                return evp

        # Search in commissioners
        for commissioner in college.get("commissioners", []):
            if self._matches_commissioner(commissioner, query_lower):
                return commissioner

        return None

    def _matches_commissioner(self, commissioner: Dict[str, Any], query: str) -> bool:
        """Check if commissioner matches query"""
        searchable_fields = [
            commissioner.get("name", ""),
            commissioner.get("country", ""),
            commissioner.get("portfolio", ""),
            str(commissioner.get("additional_portfolio", "")),
        ]

        searchable_text = " ".join(searchable_fields).lower()
        return query in searchable_text

    def find_committee(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find EP committee by acronym or name.

        Args:
            query: Committee acronym (e.g., "ENVI") or partial name

        Returns:
            Committee data or None
        """
        ep_structure = self.institutions.get("ep_organisational_structure", {})
        committees_data = ep_structure.get("parliamentary_committees", {})

        query_upper = query.upper()
        query_lower = query.lower()

        # Search in categories
        for category in committees_data.get("categories", []):
            for committee in category.get("committees", []):
                # Match acronym
                if committee.get("acronym") == query_upper:
                    return committee
                # Match name
                if query_lower in committee.get("full_name", "").lower():
                    return committee

        # Search in subcommittees
        for subcommittee in committees_data.get("subcommittees", []):
            if subcommittee.get("acronym") == query_upper:
                return subcommittee
            if query_lower in subcommittee.get("full_name", "").lower():
                return subcommittee

        # Search in special committees
        for special in committees_data.get("special_committees", []):
            if special.get("acronym") == query_upper:
                return special
            if query_lower in special.get("full_name", "").lower():
                return special

        return None

    # =========================================================================
    # Organigramme Query Methods (EC Personnel)
    # =========================================================================

    def get_dg_organigramme(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get organigramme for a specific DG.

        Args:
            dg_code: DG code (e.g., "GROW", "CLIMA", "TRADE")

        Returns:
            Organigramme data or None

        Example:
            >>> get_dg_organigramme("GROW")
        """
        dg_upper = dg_code.upper()
        return self.organigrammes.get(dg_upper)

    def list_all_dgs(self) -> List[Dict[str, str]]:
        """
        List all available DGs.

        Returns:
            List of DG codes and names
        """
        dgs = []
        for dg_code, org in self.organigrammes.items():
            dgs.append({
                'dg_code': dg_code,
                'dg_name': org.get('dg_name', ''),
                'director_general': org.get('director_general', {}).get('name', 'Unknown')
            })
        return sorted(dgs, key=lambda x: x['dg_code'])

    def find_person_in_commission(self, name: str) -> List[Dict[str, Any]]:
        """
        Find a person across all Commission DGs.

        Args:
            name: Person's name (partial match supported)

        Returns:
            List of matches with DG and position info

        Example:
            >>> find_person_in_commission("Kerstin")
        """
        name_lower = name.lower()
        matches = []

        for dg_code, org in self.organigrammes.items():
            # Check Director-General
            if 'director_general' in org:
                dg_info = org['director_general']
                dg_name = dg_info.get('name', '')
                if name_lower in dg_name.lower():
                    matches.append({
                        'name': dg_name,
                        'position': 'Director-General',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', '')
                    })

            # Check Deputy Directors-General
            for ddg in org.get('deputy_directors_general', []):
                ddg_name = ddg.get('name', '')
                if name_lower in ddg_name.lower():
                    matches.append({
                        'name': ddg_name,
                        'position': 'Deputy Director-General',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'responsibilities': ddg.get('responsibilities')
                    })

            # Check Principal Advisers
            for adviser in org.get('principal_advisers', []):
                adviser_name = adviser.get('name', '')
                if name_lower in adviser_name.lower() and adviser_name.lower() != 'not shown':
                    matches.append({
                        'name': adviser_name,
                        'position': 'Principal Adviser',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'area': adviser.get('area')
                    })

            # Search in directorates
            for directorate in org.get('directorates', []):
                # Check Director (string format)
                director = directorate.get('director', '')
                if isinstance(director, str) and name_lower in director.lower():
                    matches.append({
                        'name': director,
                        'position': 'Director',
                        'dg': dg_code,
                        'dg_name': org.get('dg_name', ''),
                        'directorate': directorate.get('name'),
                        'directorate_code': directorate.get('code')
                    })

                # Check units
                for unit in directorate.get('units', []):
                    # Head of Unit (string format)
                    head = unit.get('head', '')
                    if isinstance(head, str) and name_lower in head.lower() and head.lower() != 'not shown':
                        matches.append({
                            'name': head,
                            'position': 'Head of Unit',
                            'dg': dg_code,
                            'dg_name': org.get('dg_name', ''),
                            'unit': unit.get('name'),
                            'unit_code': unit.get('code')
                        })

        return matches

    def get_director_general(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get Director-General info for a DG.

        Args:
            dg_code: DG code (e.g., "GROW", "CLIMA")

        Returns:
            DG info with name, assistants, etc. or None

        Example:
            >>> get_director_general("GROW")
            {"name": "Kerstin Jorna", "assistants": [...]}
        """
        org = self.get_dg_organigramme(dg_code)
        if org and 'director_general' in org:
            return org['director_general']
        return None

    def find_unit_by_name(self, unit_name_query: str, dg_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find units by name across DGs.

        Args:
            unit_name_query: Unit name or keyword
            dg_code: Optional DG to search in (searches all if None)

        Returns:
            List of matching units
        """
        query_lower = unit_name_query.lower()
        matches = []

        # Determine which DGs to search
        search_orgs = {}
        if dg_code:
            dg_upper = dg_code.upper()
            if dg_upper in self.organigrammes:
                search_orgs[dg_upper] = self.organigrammes[dg_upper]
        else:
            search_orgs = self.organigrammes

        for dg, org in search_orgs.items():
            for directorate in org.get('directorates', []):
                for unit in directorate.get('units', []):
                    unit_name = unit.get('name', '')
                    if query_lower in unit_name.lower():
                        matches.append({
                            'dg': dg,
                            'dg_name': org.get('dg_name', ''),
                            'directorate': directorate.get('name'),
                            'unit_code': unit.get('code'),
                            'unit_name': unit_name,
                            'head': unit.get('head', {}).get('name')
                        })

        return matches

    def get_dg_structure_summary(self, dg_code: str) -> Optional[Dict[str, Any]]:
        """
        Get high-level structure summary of a DG.

        Args:
            dg_code: DG code

        Returns:
            Structure summary with leadership and organizational info

        Example:
            >>> get_dg_structure_summary("GROW")
        """
        org = self.get_dg_organigramme(dg_code)
        if not org:
            return None

        # Get director general name
        dg_info = org.get('director_general', {})
        dg_name = dg_info.get('name') if isinstance(dg_info, dict) else None

        # Get deputy DGs
        deputy_dgs = []
        for ddg in org.get('deputy_directors_general', []):
            if 'name' in ddg:
                deputy_dgs.append({
                    'name': ddg['name'],
                    'responsibilities': ddg.get('responsibilities')
                })

        # Count units across directorates
        num_units = 0
        for directorate in org.get('directorates', []):
            num_units += len(directorate.get('units', []))

        summary = {
            'dg_code': dg_code.upper(),
            'dg_name': org.get('dg_name'),
            'executive_vice_president': org.get('executive_vice_president'),
            'director_general': dg_name,
            'deputy_directors_general': deputy_dgs,
            'num_directorates': len(org.get('directorates', [])),
            'num_units': num_units,
            'num_agencies': len(org.get('agencies', [])),
            'date_of_effect': org.get('date_of_effect')
        }

        return summary

    # =========================================================================
    # Template Methods
    # =========================================================================

    def get_template(self, template_name: str) -> Optional[str]:
        """
        Get template content by name.

        Args:
            template_name: Template identifier (e.g., "briefing_note")

        Returns:
            Template content (Markdown) or None
        """
        return self.templates.get(template_name)

    def list_templates(self) -> List[Dict[str, str]]:
        """
        List all available templates.

        Returns:
            List of template metadata
        """
        templates_list = []
        for name, content in self.templates.items():
            # Extract title from content (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            templates_list.append({
                'id': name,
                'title': title,
                'length': len(content)
            })

        return templates_list

    def search_templates(self, query: str) -> List[str]:
        """
        Search templates by keyword (simple text search).

        Args:
            query: Search query

        Returns:
            List of matching template names
        """
        query_lower = query.lower()
        matches = []

        for name, content in self.templates.items():
            # Search in name and content
            if query_lower in name.lower() or query_lower in content.lower():
                matches.append(name)

        return matches

    # =========================================================================
    # Guide Methods (Reference Knowledge)
    # =========================================================================

    def get_guide(self, guide_name: str) -> Optional[str]:
        """
        Get guide content by name.

        Args:
            guide_name: Guide identifier (e.g., "eu_jargon", "council_guide")

        Returns:
            Guide content (Markdown) or None

        Available guides:
            - eu_jargon: EU terminology glossary
            - eu_resources: Key EU websites and tools
            - working_with_apas: Guide to parliamentary assistants
            - monitoring_tips: EU policy monitoring best practices
            - council_guide: How the Council works
            - commission_guide: How the Commission works
            - event_planning_brussels: Organising EU events
        """
        return self.guides.get(guide_name)

    def list_guides(self) -> List[Dict[str, str]]:
        """
        List all available guides.

        Returns:
            List of guide metadata with id, title, and description
        """
        guides_list = []
        for name, content in self.guides.items():
            # Extract title from content (first # heading)
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            # Extract first paragraph as description
            desc_match = re.search(r'^#[^\n]+\n+([^\n#]+)', content)
            description = desc_match.group(1).strip() if desc_match else ""

            guides_list.append({
                'id': name,
                'title': title,
                'description': description,
                'length': len(content)
            })

        return guides_list

    def search_guides(self, query: str) -> List[Dict[str, Any]]:
        """
        Search guides by keyword triggers and content matching.

        Uses a two-pass approach:
        1. Keyword triggers: check if any trigger phrases appear in the query
           (higher priority, more precise matching)
        2. Content search: fallback to searching guide names and content
           (lower priority, broader matching)

        Args:
            query: Search query (searches triggers, name, and content)

        Returns:
            List of matching guides with context snippets, ordered by relevance
        """
        query_lower = query.lower()
        triggered_guides = set()
        matches = []
        seen_ids = set()

        # Pass 1: Keyword trigger matching (highest priority)
        # Check multi-word triggers first (longer = more specific), then single-word
        sorted_triggers = sorted(GUIDE_KEYWORD_TRIGGERS.keys(), key=len, reverse=True)
        for trigger in sorted_triggers:
            if trigger in query_lower:
                for guide_id in GUIDE_KEYWORD_TRIGGERS[trigger]:
                    if guide_id in self.guides and guide_id not in seen_ids:
                        triggered_guides.add(guide_id)

        # Add triggered guides first (they are the most relevant)
        for guide_id in triggered_guides:
            content = self.guides[guide_id]
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else guide_id.replace('_', ' ').title()

            # Find context around the query match in content
            content_lower = content.lower()
            idx = content_lower.find(query_lower)
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(content), idx + len(query_lower) + 100)
                snippet = content[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
            else:
                # Use the first paragraph after the title as snippet
                para_match = re.search(r'^#[^\n]+\n+([^\n#]+)', content)
                snippet = para_match.group(1).strip()[:150] + "..." if para_match else ""

            matches.append({
                'id': guide_id,
                'title': title,
                'snippet': snippet,
                'trigger_matched': True
            })
            seen_ids.add(guide_id)

        # Pass 2: Content search (fallback for guides not already matched by triggers)
        # Split query into individual words for broader matching
        # Filter out common words that would match too many guides
        stopwords = {
            'what', 'when', 'where', 'which', 'that', 'this', 'these', 'those',
            'have', 'does', 'will', 'would', 'could', 'should', 'about', 'with',
            'from', 'they', 'their', 'there', 'been', 'being', 'some', 'more',
            'also', 'than', 'then', 'very', 'just', 'like', 'make', 'made',
            'need', 'know', 'help', 'work', 'want', 'into', 'over', 'after',
            'before', 'between', 'under', 'through', 'during', 'each', 'only',
            'most', 'much', 'many', 'such', 'well', 'good', 'best',
        }
        query_words = [w for w in query_lower.split() if len(w) > 3 and w not in stopwords]

        for name, content in self.guides.items():
            if name in seen_ids:
                continue

            # Check if the full query or any significant word matches
            content_lower = content.lower()
            name_lower = name.lower()

            full_match = query_lower in name_lower or query_lower in content_lower
            word_matches = sum(1 for w in query_words if w in name_lower or w in content_lower)

            # Require either full match or at least 3 word matches (stricter to reduce noise)
            if full_match or word_matches >= 3:
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else name.replace('_', ' ').title()

                idx = content_lower.find(query_lower)
                if idx != -1:
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query_lower) + 100)
                    snippet = content[start:end].strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                else:
                    snippet = ""

                matches.append({
                    'id': name,
                    'title': title,
                    'snippet': snippet,
                    'trigger_matched': False
                })
                seen_ids.add(name)

        return matches

    def get_all_guides_content(self) -> str:
        """
        Get concatenated content of all guides for AI context.

        Returns:
            All guides content as a single string with separators
        """
        parts = []
        for name, content in sorted(self.guides.items()):
            parts.append(f"=== {name.upper().replace('_', ' ')} ===\n\n{content}")
        return "\n\n".join(parts)

    # =========================================================================
    # Requirements Methods (EU Law Compliance)
    # =========================================================================

    def get_requirements_for_cluster(self, cluster_id: int) -> Optional[Dict[str, Any]]:
        """
        Get all requirements for a specific cluster.

        Args:
            cluster_id: Cluster ID (1-21)

        Returns:
            Cluster data with requirements list

        Example:
            >>> get_requirements_for_cluster(1)  # GDPR
            {"cluster_id": 1, "cluster_name": "GDPR Package", "requirements": [...]}
        """
        return self.requirements.get(str(cluster_id))

    def get_requirements_index(self) -> Optional[Dict[str, Any]]:
        """
        Get the requirements index with summary of all clusters.

        Returns:
            Index with cluster summaries and counts
        """
        return self.requirements.get('_index')

    def list_requirement_clusters(self) -> List[Dict[str, Any]]:
        """
        List all clusters with extracted requirements.

        Returns:
            List of cluster summaries with counts
        """
        clusters = []
        for key, data in self.requirements.items():
            if key.startswith('_'):
                continue
            clusters.append({
                'cluster_id': data.get('cluster_id'),
                'cluster_name': data.get('cluster_name'),
                'policy_area': data.get('policy_area'),
                'total_requirements': data.get('total_requirements', len(data.get('requirements', []))),
                'total_laws': data.get('total_laws', 0)
            })
        return sorted(clusters, key=lambda x: x.get('cluster_id', 0))

    def search_requirements(
        self,
        query: str,
        cluster_id: Optional[int] = None,
        criticality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search requirements by keyword.

        Args:
            query: Search query (searches in requirement text and keywords)
            cluster_id: Optional cluster to search in
            criticality: Filter by criticality (critical, important, recommended)

        Returns:
            List of matching requirements with cluster context

        Example:
            >>> search_requirements("data breach", cluster_id=1)
            >>> search_requirements("notification", criticality="critical")
        """
        query_lower = query.lower()
        matches = []

        # Determine which clusters to search
        if cluster_id:
            clusters_to_search = [self.requirements.get(str(cluster_id))]
        else:
            clusters_to_search = [
                data for key, data in self.requirements.items()
                if not key.startswith('_')
            ]

        for cluster_data in clusters_to_search:
            if not cluster_data:
                continue

            cluster_name = cluster_data.get('cluster_name', '')
            cluster_id_val = cluster_data.get('cluster_id')

            for req in cluster_data.get('requirements', []):
                # Apply criticality filter
                if criticality and req.get('criticality') != criticality:
                    continue

                # Search in text and keywords
                req_text = req.get('requirement_text', '').lower()
                keywords = ' '.join(req.get('keywords', [])).lower()
                article = req.get('article', '').lower()
                law_title = req.get('law_title', '').lower()

                if (query_lower in req_text or
                    query_lower in keywords or
                    query_lower in article or
                    query_lower in law_title):

                    matches.append({
                        **req,
                        'cluster_name': cluster_name,
                        'cluster_id': cluster_id_val
                    })

        return matches

    def get_critical_requirements(self, cluster_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all critical requirements (highest priority).

        Args:
            cluster_id: Optional cluster to filter by

        Returns:
            List of critical requirements
        """
        return self.search_requirements("", cluster_id=cluster_id, criticality="critical")

    def get_requirements_by_entity(
        self,
        entity_type: str,
        cluster_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get requirements applicable to a specific entity type.

        Args:
            entity_type: Entity type (e.g., "data controller", "online platform")
            cluster_id: Optional cluster to filter by

        Returns:
            List of applicable requirements

        Example:
            >>> get_requirements_by_entity("online platform")
            >>> get_requirements_by_entity("data controller", cluster_id=1)
        """
        entity_lower = entity_type.lower()
        matches = []

        if cluster_id:
            clusters_to_search = [self.requirements.get(str(cluster_id))]
        else:
            clusters_to_search = [
                data for key, data in self.requirements.items()
                if not key.startswith('_')
            ]

        for cluster_data in clusters_to_search:
            if not cluster_data:
                continue

            cluster_name = cluster_data.get('cluster_name', '')
            cluster_id_val = cluster_data.get('cluster_id')

            for req in cluster_data.get('requirements', []):
                applicable = req.get('applicable_entity', '').lower()
                if entity_lower in applicable:
                    matches.append({
                        **req,
                        'cluster_name': cluster_name,
                        'cluster_id': cluster_id_val
                    })

        return matches

    def get_requirements_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of all requirements.

        Returns:
            Summary with counts by cluster, criticality, etc.
        """
        summary = {
            'total_clusters': 0,
            'total_requirements': 0,
            'by_criticality': {'critical': 0, 'important': 0, 'recommended': 0},
            'clusters': []
        }

        for key, data in self.requirements.items():
            if key.startswith('_'):
                continue

            summary['total_clusters'] += 1
            reqs = data.get('requirements', [])
            summary['total_requirements'] += len(reqs)

            # Count by criticality
            for req in reqs:
                crit = req.get('criticality', 'important')
                if crit in summary['by_criticality']:
                    summary['by_criticality'][crit] += 1

            summary['clusters'].append({
                'cluster_id': data.get('cluster_id'),
                'cluster_name': data.get('cluster_name'),
                'requirement_count': len(reqs)
            })

        summary['clusters'].sort(key=lambda x: x.get('cluster_id', 0))
        return summary

    def get_guide_for_topic(self, topic: str) -> Optional[str]:
        """
        Get the most relevant guide for a topic.

        Args:
            topic: Topic keyword (e.g., "jargon", "council", "monitoring")

        Returns:
            Guide content or None
        """
        topic_lower = topic.lower()

        # Direct mappings
        topic_map = {
            # EU Jargon
            'jargon': 'eu_jargon',
            'terminology': 'eu_jargon',
            'glossary': 'eu_jargon',
            'terms': 'eu_jargon',
            'acronyms': 'eu_jargon',
            # EU Resources
            'resources': 'eu_resources',
            'websites': 'eu_resources',
            'tools': 'eu_resources',
            'links': 'eu_resources',
            # Working with APAs
            'apa': 'working_with_apas',
            'assistant': 'working_with_apas',
            'assistants': 'working_with_apas',
            'parliamentary': 'working_with_apas',
            # Monitoring
            'monitoring': 'monitoring_tips',
            'tracking': 'monitoring_tips',
            'alerts': 'monitoring_tips',
            # Council
            'council': 'council_guide',
            'coreper': 'council_guide',
            'working party': 'council_guide',
            # Commission
            'commission': 'commission_guide',
            'dg': 'commission_guide',
            'consultation': 'commission_guide',
            # Events
            'event': 'event_planning_brussels',
            'events': 'event_planning_brussels',
            'conference': 'event_planning_brussels',
            'brussels': 'event_planning_brussels',
            # Lobbying Methodology (NEW)
            'lobby': 'lobbying_methodology',
            'lobbying': 'lobbying_methodology',
            'advocacy': 'lobbying_methodology',
            'influence': 'lobbying_methodology',
            'campaign': 'lobbying_methodology',
            'strategy': 'lobbying_methodology',
            'engage': 'lobbying_methodology',
            'engagement': 'lobbying_methodology',
            'position paper': 'lobbying_methodology',
            'amendment': 'lobbying_methodology',
            'trilogue': 'lobbying_methodology',
            'intervention': 'lobbying_methodology',
            'timing': 'lobbying_methodology',
            'coalition': 'lobbying_methodology',
            # Stakeholder Mapping (NEW)
            'stakeholder': 'stakeholder_mapping',
            'stakeholders': 'stakeholder_mapping',
            'mapping': 'stakeholder_mapping',
            'decision-maker': 'stakeholder_mapping',
            'decision maker': 'stakeholder_mapping',
            'rapporteur': 'stakeholder_mapping',
            'shadow': 'stakeholder_mapping',
            'mep': 'stakeholder_mapping',
            'influence matrix': 'stakeholder_mapping',
            'prioritise': 'stakeholder_mapping',
            'prioritize': 'stakeholder_mapping',
            # Public Affairs Industry (NEW)
            'consultancy': 'public_affairs_industry',
            'consultant': 'public_affairs_industry',
            'public affairs': 'public_affairs_industry',
            'professional': 'public_affairs_industry',
            'deliverable': 'public_affairs_industry',
            'position paper': 'public_affairs_industry',
            'brief': 'public_affairs_industry',
            'briefing': 'public_affairs_industry',
            # Brubru Features
            'brubru': 'brubru_features',
            'tracked files': 'brubru_features',
            'track file': 'brubru_features',
            'my eu bubble': 'brubru_features',
            'legislative train': 'brubru_features',
            'oeil sync': 'brubru_features',
            'eurlex sync': 'brubru_features',
            'eur-lex sync': 'brubru_features',
            'celex': 'brubru_features',
            'procedure reference': 'brubru_features',
            'data sources': 'brubru_features',
            'amendator': 'brubru_features',
            'load from tracked': 'brubru_features',
        }

        # Check direct mapping
        if topic_lower in topic_map:
            guide_name = topic_map[topic_lower]
            return self.guides.get(guide_name)

        # Fallback: search all guides
        for name, content in self.guides.items():
            if topic_lower in name.lower() or topic_lower in content.lower():
                return content

        return None

    # =========================================================================
    # Preparation for Vector Store
    # =========================================================================

    def prepare_templates_for_embedding(self) -> List[Dict[str, Any]]:
        """
        Prepare templates for ChromaDB indexing.

        Returns:
            List of documents ready for vector store:
            [
                {
                    "id": "template_briefing_note",
                    "text": "content...",
                    "metadata": {
                        "type": "template",
                        "name": "briefing_note",
                        "title": "Briefing Note Template",
                        "category": "consultancy"
                    }
                }
            ]
        """
        documents = []

        for name, content in self.templates.items():
            # Extract title
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else name.replace('_', ' ').title()

            # Infer category from name
            category = self._infer_template_category(name)

            doc = {
                "id": f"template_{name}",
                "text": content,
                "metadata": {
                    "type": "template",
                    "name": name,
                    "title": title,
                    "category": category,
                    "source": "internal_knowledge_base"
                }
            }
            documents.append(doc)

        return documents

    def _infer_template_category(self, template_name: str) -> str:
        """Infer category from template name"""
        name_lower = template_name.lower()

        if 'briefing' in name_lower or 'note' in name_lower:
            return 'briefing'
        elif 'position' in name_lower or 'paper' in name_lower:
            return 'position_paper'
        elif 'event' in name_lower or 'planning' in name_lower:
            return 'event_management'
        elif 'monitoring' in name_lower or 'tracking' in name_lower:
            return 'monitoring'
        elif 'strategy' in name_lower or 'advocacy' in name_lower:
            return 'strategy'
        elif 'stakeholder' in name_lower or 'mapping' in name_lower:
            return 'stakeholder_analysis'
        else:
            return 'general'

    # =========================================================================
    # Statistics & Utilities
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        return {
            **self.stats,
            'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
            'knowledge_base_dir': str(self.knowledge_base_dir),
            'template_categories': self._get_template_categories(),
            'dg_organigrammes': list(self.organigrammes.keys()),
            'guides_available': list(self.guides.keys())
        }

    def _get_template_categories(self) -> Dict[str, int]:
        """Count templates by category"""
        categories = {}
        for name in self.templates.keys():
            category = self._infer_template_category(name)
            categories[category] = categories.get(category, 0) + 1
        return categories

    def reload(self) -> Dict[str, Any]:
        """Reload all knowledge base content"""
        logger.info("Reloading knowledge base...")

        # Clear caches
        self.calendars.clear()
        self.institutions.clear()
        self.templates.clear()
        self.organigrammes.clear()
        self.analytics.clear()
        self.guides.clear()
        self.requirements.clear()

        # Reload
        return self.load_all()


# Global singleton
_knowledge_loader: Optional[KnowledgeLoader] = None


def get_knowledge_loader(knowledge_base_dir: str = None) -> KnowledgeLoader:
    """
    Get global knowledge loader instance.

    Args:
        knowledge_base_dir: Path to knowledge_base directory

    Returns:
        KnowledgeLoader instance
    """
    global _knowledge_loader

    if _knowledge_loader is None:
        _knowledge_loader = KnowledgeLoader(knowledge_base_dir)
        _knowledge_loader.load_all()

    return _knowledge_loader
