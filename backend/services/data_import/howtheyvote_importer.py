"""
HowTheyVote.eu Data Importer - Phase 1.1

Downloads and imports EP voting data from HowTheyVote.eu GitHub releases.
Source: https://github.com/HowTheyVote/data/releases/latest

Data files:
- members.csv.gz - MEP profiles
- groups.csv.gz - Political groups
- group_memberships.csv.gz - MEP group history
- votes.csv.gz - Roll-call votes
- member_votes.csv.gz - Individual voting records (~16M records)
"""

import gzip
import csv
import logging
import io
import tempfile
import os
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List, Callable, Tuple
from pathlib import Path

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from core.database import SessionLocal
from models.ep_voting import (
    EPPoliticalGroup, EPMember, EPGroupMembership,
    EPVote, EPMemberVote, EPDataImport,
    VotePosition, VoteResult, ProcedureType
)

logger = logging.getLogger(__name__)


# HowTheyVote GitHub release URLs
HTV_BASE_URL = "https://github.com/HowTheyVote/data/releases/latest/download"
HTV_FILES = {
    "members": f"{HTV_BASE_URL}/members.csv.gz",
    "groups": f"{HTV_BASE_URL}/groups.csv.gz",
    "group_memberships": f"{HTV_BASE_URL}/group_memberships.csv.gz",
    "votes": f"{HTV_BASE_URL}/votes.csv.gz",
    "member_votes": f"{HTV_BASE_URL}/member_votes.csv.gz",
}

# Map HowTheyVote group codes to our codes
GROUP_CODE_MAP = {
    "EPP": "EPP",
    "SD": "SD",
    "S&D": "SD",
    "RENEW": "RENEW",
    "GREEN_EFA": "GREEN_EFA",
    "Greens/EFA": "GREEN_EFA",
    "ECR": "ECR",
    "GUE_NGL": "GUE_NGL",
    "The Left": "GUE_NGL",
    "ID": "PFE",  # ID became PfE
    "PFE": "PFE",
    "ESN": "ESN",
    "NI": "NI",
}

# Map vote position strings
POSITION_MAP = {
    "FOR": VotePosition.FOR,
    "AGAINST": VotePosition.AGAINST,
    "ABSTENTION": VotePosition.ABSTENTION,
    "DID_NOT_VOTE": VotePosition.DID_NOT_VOTE,
}

# Map procedure type strings
PROCEDURE_TYPE_MAP = {
    "COD": ProcedureType.COD,
    "CNS": ProcedureType.CNS,
    "APP": ProcedureType.APP,
    "NLE": ProcedureType.NLE,
    "INI": ProcedureType.INI,
    "INL": ProcedureType.INL,
    "RSP": ProcedureType.RSP,
    "BUD": ProcedureType.BUD,
    "DEC": ProcedureType.DEC,
}


class HowTheyVoteImporter:
    """
    Imports EP voting data from HowTheyVote.eu GitHub releases.

    Usage:
        importer = HowTheyVoteImporter()
        result = await importer.import_all()
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

        # Member ID mapping (HTV ID -> UUID)
        self._member_id_map: Dict[int, str] = {}

        # Vote ID mapping (HTV ID -> UUID)
        self._vote_id_map: Dict[int, str] = {}

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(
            timeout=300.0,  # 5 min timeout for large files
            follow_redirects=True,
            headers={"User-Agent": "Brubru/1.0 (EU Policy Assistant)"}
        )
        self._temp_dir = tempfile.TemporaryDirectory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
        if self._temp_dir:
            self._temp_dir.cleanup()
        if self._owns_db and self._db:
            self._db.close()

    async def _download_file(self, url: str, filename: str) -> Path:
        """Download a gzipped CSV file from HowTheyVote."""
        logger.info(f"Downloading {filename} from {url}")

        response = await self._http_client.get(url)
        response.raise_for_status()

        filepath = Path(self._temp_dir.name) / filename
        filepath.write_bytes(response.content)

        logger.info(f"Downloaded {filename}: {len(response.content) / 1024:.1f} KB")
        return filepath

    def _read_gzip_csv(self, filepath: Path) -> List[Dict[str, str]]:
        """Read a gzipped CSV file and return list of dicts."""
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse a date string (YYYY-MM-DD)."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse a datetime string."""
        if not dt_str:
            return None
        try:
            # Try ISO format first
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None

    def _parse_bool(self, val: str) -> bool:
        """Parse boolean from string."""
        return val.lower() in ("true", "1", "yes", "t")

    def _parse_int(self, val: str, default: int = 0) -> int:
        """Parse integer from string."""
        try:
            return int(val) if val else default
        except ValueError:
            return default

    def _create_import_record(self, import_type: str) -> EPDataImport:
        """Create an import tracking record."""
        record = EPDataImport(
            source="howtheyvote",
            import_type=import_type,
            status="running"
        )
        self.db.add(record)
        self.db.commit()
        return record

    def _complete_import_record(
        self,
        record: EPDataImport,
        added: int,
        updated: int,
        skipped: int,
        errors: int,
        error_details: Optional[List[str]] = None
    ):
        """Mark import record as completed."""
        record.completed_at = datetime.now(timezone.utc)
        record.records_processed = added + updated + skipped + errors
        record.records_added = added
        record.records_updated = updated
        record.records_skipped = skipped
        record.errors = errors
        record.error_details = error_details[:100] if error_details else None
        record.status = "completed" if errors == 0 else "completed_with_errors"
        self.db.commit()

    async def import_groups(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """Import political groups from groups.csv.gz."""
        import_record = self._create_import_record("groups")
        added, updated, skipped, errors = 0, 0, 0, 0
        error_details = []

        try:
            filepath = await self._download_file(HTV_FILES["groups"], "groups.csv.gz")
            rows = self._read_gzip_csv(filepath)
            total = len(rows)

            for i, row in enumerate(rows):
                try:
                    code = row.get("code", "").strip()
                    if not code:
                        skipped += 1
                        continue

                    # Map to our code if needed
                    mapped_code = GROUP_CODE_MAP.get(code, code)

                    # Check if exists
                    existing = self.db.query(EPPoliticalGroup).filter(
                        EPPoliticalGroup.code == mapped_code
                    ).first()

                    if existing:
                        # Update
                        existing.official_label = row.get("official_label", existing.official_label)
                        existing.label = row.get("label", existing.label)
                        existing.short_label = row.get("short_label", existing.short_label)
                        updated += 1
                    else:
                        # Insert
                        group = EPPoliticalGroup(
                            code=mapped_code,
                            official_label=row.get("official_label", code),
                            label=row.get("label", code),
                            short_label=row.get("short_label")
                        )
                        self.db.add(group)
                        added += 1

                    if progress_callback and (i + 1) % 5 == 0:
                        progress_callback(i + 1, total, f"Processing groups: {i + 1}/{total}")

                except Exception as e:
                    errors += 1
                    error_details.append(f"Row {i}: {str(e)}")
                    logger.error(f"Error importing group row {i}: {e}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error importing groups: {e}")
            errors += 1
            error_details.append(str(e))

        self._complete_import_record(import_record, added, updated, skipped, errors, error_details)

        return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}

    async def import_members(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """Import MEPs from members.csv.gz."""
        import_record = self._create_import_record("members")
        added, updated, skipped, errors = 0, 0, 0, 0
        error_details = []

        try:
            filepath = await self._download_file(HTV_FILES["members"], "members.csv.gz")
            rows = self._read_gzip_csv(filepath)
            total = len(rows)

            for i, row in enumerate(rows):
                try:
                    htv_id = self._parse_int(row.get("id"))
                    if not htv_id:
                        skipped += 1
                        continue

                    first_name = row.get("first_name", "").strip()
                    last_name = row.get("last_name", "").strip()
                    country_code = row.get("country_code", "").strip()

                    if not all([first_name, last_name, country_code]):
                        skipped += 1
                        continue

                    full_name = f"{first_name} {last_name}"

                    # Check if exists
                    existing = self.db.query(EPMember).filter(
                        EPMember.htv_id == htv_id
                    ).first()

                    if existing:
                        # Update
                        existing.first_name = first_name
                        existing.last_name = last_name
                        existing.full_name = full_name
                        existing.country_code = country_code
                        existing.date_of_birth = self._parse_date(row.get("date_of_birth"))
                        existing.email = row.get("email")
                        existing.twitter = row.get("twitter")
                        existing.facebook = row.get("facebook")
                        self._member_id_map[htv_id] = str(existing.id)
                        updated += 1
                    else:
                        # Insert
                        member = EPMember(
                            htv_id=htv_id,
                            first_name=first_name,
                            last_name=last_name,
                            full_name=full_name,
                            country_code=country_code,
                            date_of_birth=self._parse_date(row.get("date_of_birth")),
                            email=row.get("email"),
                            twitter=row.get("twitter"),
                            facebook=row.get("facebook"),
                            is_active=True,
                            term=10
                        )
                        self.db.add(member)
                        self.db.flush()  # Get ID
                        self._member_id_map[htv_id] = str(member.id)
                        added += 1

                    if progress_callback and (i + 1) % 100 == 0:
                        progress_callback(i + 1, total, f"Processing members: {i + 1}/{total}")

                except Exception as e:
                    errors += 1
                    error_details.append(f"Row {i}: {str(e)}")
                    logger.error(f"Error importing member row {i}: {e}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error importing members: {e}")
            errors += 1
            error_details.append(str(e))

        self._complete_import_record(import_record, added, updated, skipped, errors, error_details)

        return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}

    async def import_group_memberships(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """Import group memberships from group_memberships.csv.gz."""
        import_record = self._create_import_record("group_memberships")
        added, updated, skipped, errors = 0, 0, 0, 0
        error_details = []

        # Build member ID map if not already done
        if not self._member_id_map:
            for m in self.db.query(EPMember).all():
                self._member_id_map[m.htv_id] = str(m.id)

        try:
            filepath = await self._download_file(HTV_FILES["group_memberships"], "group_memberships.csv.gz")
            rows = self._read_gzip_csv(filepath)
            total = len(rows)

            for i, row in enumerate(rows):
                try:
                    member_htv_id = self._parse_int(row.get("member_id"))
                    group_code = row.get("group_code", "").strip()
                    term = self._parse_int(row.get("term"))

                    if not all([member_htv_id, group_code, term]):
                        skipped += 1
                        continue

                    # Map group code
                    mapped_code = GROUP_CODE_MAP.get(group_code, group_code)

                    # Get member UUID
                    member_uuid = self._member_id_map.get(member_htv_id)
                    if not member_uuid:
                        skipped += 1
                        continue

                    start_date = self._parse_date(row.get("start_date"))
                    end_date = self._parse_date(row.get("end_date"))

                    if not start_date:
                        skipped += 1
                        continue

                    # Check if exists
                    existing = self.db.query(EPGroupMembership).filter(
                        EPGroupMembership.member_id == member_uuid,
                        EPGroupMembership.group_code == mapped_code,
                        EPGroupMembership.term == term,
                        EPGroupMembership.start_date == start_date
                    ).first()

                    if existing:
                        existing.end_date = end_date
                        updated += 1
                    else:
                        membership = EPGroupMembership(
                            member_id=member_uuid,
                            group_code=mapped_code,
                            term=term,
                            start_date=start_date,
                            end_date=end_date
                        )
                        self.db.add(membership)
                        added += 1

                    # Update member's current group if this is current term and no end date
                    if term == 10 and not end_date:
                        member = self.db.query(EPMember).filter(EPMember.id == member_uuid).first()
                        if member:
                            member.current_group_code = mapped_code

                    if progress_callback and (i + 1) % 500 == 0:
                        progress_callback(i + 1, total, f"Processing memberships: {i + 1}/{total}")

                except Exception as e:
                    errors += 1
                    error_details.append(f"Row {i}: {str(e)}")
                    logger.error(f"Error importing membership row {i}: {e}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error importing group memberships: {e}")
            errors += 1
            error_details.append(str(e))

        self._complete_import_record(import_record, added, updated, skipped, errors, error_details)

        return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}

    async def import_votes(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """Import votes from votes.csv.gz."""
        import_record = self._create_import_record("votes")
        added, updated, skipped, errors = 0, 0, 0, 0
        error_details = []

        try:
            filepath = await self._download_file(HTV_FILES["votes"], "votes.csv.gz")
            rows = self._read_gzip_csv(filepath)
            total = len(rows)

            for i, row in enumerate(rows):
                try:
                    htv_id = self._parse_int(row.get("id"))
                    if not htv_id:
                        skipped += 1
                        continue

                    timestamp = self._parse_datetime(row.get("timestamp"))
                    display_title = row.get("display_title", "").strip()

                    if not all([timestamp, display_title]):
                        skipped += 1
                        continue

                    # Parse procedure type
                    proc_type_str = row.get("procedure_type", "").strip()
                    proc_type = PROCEDURE_TYPE_MAP.get(proc_type_str, ProcedureType.OTHER) if proc_type_str else None

                    # Parse result
                    result_str = row.get("result", "").strip().upper()
                    if result_str == "ADOPTED":
                        result = VoteResult.ADOPTED
                    elif result_str == "REJECTED":
                        result = VoteResult.REJECTED
                    else:
                        result = VoteResult.UNKNOWN

                    # Check if exists
                    existing = self.db.query(EPVote).filter(EPVote.htv_id == htv_id).first()

                    if existing:
                        existing.display_title = display_title
                        existing.count_for = self._parse_int(row.get("count_for"))
                        existing.count_against = self._parse_int(row.get("count_against"))
                        existing.count_abstention = self._parse_int(row.get("count_abstention"))
                        existing.count_did_not_vote = self._parse_int(row.get("count_did_not_vote"))
                        existing.result = result
                        self._vote_id_map[htv_id] = str(existing.id)
                        updated += 1
                    else:
                        vote = EPVote(
                            htv_id=htv_id,
                            timestamp=timestamp,
                            display_title=display_title,
                            reference=row.get("reference"),
                            description=row.get("description"),
                            amendment_subject=row.get("amendment_subject"),
                            amendment_number=row.get("amendment_number"),
                            is_main=self._parse_bool(row.get("is_main", "false")),
                            procedure_reference=row.get("procedure_reference"),
                            procedure_title=row.get("procedure_title"),
                            procedure_type=proc_type,
                            procedure_stage=row.get("procedure_stage"),
                            count_for=self._parse_int(row.get("count_for")),
                            count_against=self._parse_int(row.get("count_against")),
                            count_abstention=self._parse_int(row.get("count_abstention")),
                            count_did_not_vote=self._parse_int(row.get("count_did_not_vote")),
                            result=result,
                            texts_adopted_reference=row.get("texts_adopted_reference")
                        )
                        self.db.add(vote)
                        self.db.flush()
                        self._vote_id_map[htv_id] = str(vote.id)
                        added += 1

                    if progress_callback and (i + 1) % 1000 == 0:
                        progress_callback(i + 1, total, f"Processing votes: {i + 1}/{total}")

                except Exception as e:
                    errors += 1
                    error_details.append(f"Row {i}: {str(e)}")
                    logger.error(f"Error importing vote row {i}: {e}")

            self.db.commit()

        except Exception as e:
            logger.error(f"Error importing votes: {e}")
            errors += 1
            error_details.append(str(e))

        self._complete_import_record(import_record, added, updated, skipped, errors, error_details)

        return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}

    async def import_member_votes(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        batch_size: int = 10000
    ) -> Dict[str, int]:
        """
        Import individual member votes from member_votes.csv.gz.
        This is the largest file (~16M records), so we process in batches.
        """
        import_record = self._create_import_record("member_votes")
        added, updated, skipped, errors = 0, 0, 0, 0
        error_details = []

        # Build maps if not already done
        if not self._member_id_map:
            for m in self.db.query(EPMember).all():
                self._member_id_map[m.htv_id] = str(m.id)

        if not self._vote_id_map:
            for v in self.db.query(EPVote).all():
                self._vote_id_map[v.htv_id] = str(v.id)

        try:
            filepath = await self._download_file(HTV_FILES["member_votes"], "member_votes.csv.gz")

            # Stream the file to avoid memory issues
            batch = []
            total_processed = 0

            with gzip.open(filepath, "rt", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        vote_htv_id = self._parse_int(row.get("vote_id"))
                        member_htv_id = self._parse_int(row.get("member_id"))
                        position_str = row.get("position", "").strip().upper()

                        if not all([vote_htv_id, member_htv_id, position_str]):
                            skipped += 1
                            continue

                        # Get UUIDs
                        vote_uuid = self._vote_id_map.get(vote_htv_id)
                        member_uuid = self._member_id_map.get(member_htv_id)

                        if not vote_uuid or not member_uuid:
                            skipped += 1
                            continue

                        position = POSITION_MAP.get(position_str)
                        if not position:
                            skipped += 1
                            continue

                        country_code = row.get("country_code", "").strip()
                        group_code = row.get("group_code", "").strip()
                        mapped_group = GROUP_CODE_MAP.get(group_code, group_code)

                        batch.append({
                            "vote_id": vote_uuid,
                            "member_id": member_uuid,
                            "position": position,
                            "country_code": country_code,
                            "group_code": mapped_group
                        })

                        if len(batch) >= batch_size:
                            # Bulk insert
                            self._bulk_insert_member_votes(batch)
                            added += len(batch)
                            total_processed += len(batch)
                            batch = []

                            if progress_callback:
                                progress_callback(
                                    total_processed, 16000000,
                                    f"Processing member votes: {total_processed:,}"
                                )

                    except Exception as e:
                        errors += 1
                        if len(error_details) < 100:
                            error_details.append(f"Row: {str(e)}")

                # Process remaining batch
                if batch:
                    self._bulk_insert_member_votes(batch)
                    added += len(batch)

            self.db.commit()

        except Exception as e:
            logger.error(f"Error importing member votes: {e}")
            errors += 1
            error_details.append(str(e))

        self._complete_import_record(import_record, added, updated, skipped, errors, error_details)

        return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}

    def _bulk_insert_member_votes(self, batch: List[Dict[str, Any]]):
        """Bulk insert member votes with ON CONFLICT DO NOTHING."""
        if not batch:
            return

        stmt = insert(EPMemberVote).values(batch)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_member_vote")
        self.db.execute(stmt)
        self.db.commit()

    async def import_all(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        skip_member_votes: bool = False
    ) -> Dict[str, Any]:
        """
        Import all data from HowTheyVote.

        Args:
            progress_callback: Optional callback for progress updates
            skip_member_votes: Skip the large member_votes file (for testing)

        Returns:
            Dict with results for each import type
        """
        start_time = datetime.now(timezone.utc)
        results = {}

        async with self:
            logger.info("Starting HowTheyVote full import...")

            # 1. Groups
            logger.info("Importing groups...")
            results["groups"] = await self.import_groups(progress_callback)

            # 2. Members
            logger.info("Importing members...")
            results["members"] = await self.import_members(progress_callback)

            # 3. Group memberships
            logger.info("Importing group memberships...")
            results["group_memberships"] = await self.import_group_memberships(progress_callback)

            # 4. Votes
            logger.info("Importing votes...")
            results["votes"] = await self.import_votes(progress_callback)

            # 5. Member votes (optional - very large)
            if not skip_member_votes:
                logger.info("Importing member votes (this may take a while)...")
                results["member_votes"] = await self.import_member_votes(progress_callback)
            else:
                results["member_votes"] = {"skipped": True, "reason": "skip_member_votes=True"}

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        results["total_duration_seconds"] = duration
        logger.info(f"HowTheyVote import completed in {duration:.1f}s")

        return results


# Singleton instance
_importer_instance: Optional[HowTheyVoteImporter] = None


def get_howtheyvote_importer() -> HowTheyVoteImporter:
    """Get or create the HowTheyVote importer instance."""
    global _importer_instance
    if _importer_instance is None:
        _importer_instance = HowTheyVoteImporter()
    return _importer_instance
