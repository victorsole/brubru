"""
Position Aggregator.

Assembles a file-level position snapshot for a legislative carriage by combining:
  * Commission proposal (commission_documents + legislative_carriages.celex_numbers)
  * Parliament stance:
      - Lead committee + rapporteur + shadows (from legislative_carriages)
      - Per-group stance via GroupVotePredictor
      - Amendment activity counts by political group (from mep_amendments)
      - Adopted plenary text if any (texts_adopted)
  * Council stance:
      - Per-Member-State stance via CouncilPositionInferrer
      - OEIL key events referencing Council (general approach, first reading position)

No new scrapers required; everything reuses existing tables and prediction
services. Output matches the `position_*_position` JSONB columns on
file_position_snapshots.

Created: April 2026
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.commission_document import CommissionDocument
from models.file_position import FilePositionSnapshot
from models.legislative_train import LegislativeCarriage
from models.mep_amendment import MEPAmendment

logger = logging.getLogger(__name__)

SNAPSHOT_TTL_HOURS = 24


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class GroupPosition:
    group_code: str
    stance: str               # for | against | abstention | split | unknown
    confidence: str           # high | medium | low
    cohesion: float           # 0.0 - 1.0
    rationale: str = ""
    amendment_count: int = 0
    top_amendments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MemberStatePosition:
    country_code: str
    country_name: str
    stance: str               # support | oppose | neutral | undecided
    confidence: str
    rationale: str = ""
    signal_count: int = 0


@dataclass
class FilePosition:
    procedure_ref: str
    commission: Dict[str, Any]
    parliament: Dict[str, Any]
    council: Dict[str, Any]
    amendments_by_article: List[Dict[str, Any]] = field(default_factory=list)
    data_completeness: str = "partial"
    confidence: str = "medium"
    sources: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

# Political-group display mapping
GROUP_DISPLAY = {
    "PPE": "EPP", "EPP": "EPP",
    "S&D": "S&D", "SD": "S&D",
    "Renew": "Renew", "RE": "Renew",
    "Verts/ALE": "Greens/EFA", "Greens": "Greens/EFA",
    "ECR": "ECR",
    "ID": "ID",
    "PfE": "PfE",
    "GUE/NGL": "The Left", "The Left": "The Left",
    "NI": "NI", "ESN": "ESN",
}

COUNTRY_NAME = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
    "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia",
    "FI": "Finland", "FR": "France", "DE": "Germany", "GR": "Greece",
    "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LV": "Latvia",
    "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia",
    "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
}


class PositionAggregator:
    """Produces a FilePosition for a given legislative carriage."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self._db = db
        self._owns_db = db is None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self) -> None:
        if self._owns_db and self._db is not None:
            self._db.close()
            self._db = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def aggregate(self, carriage: LegislativeCarriage) -> FilePosition:
        """Build a FilePosition for a carriage. Uses cached snapshot if fresh."""
        commission = self._commission_block(carriage)
        parliament = await self._parliament_block(carriage)
        council = await self._council_block(carriage)
        amendments_by_article = self._amendments_by_article(carriage)

        sources = {
            "commission_documents": commission.get("documents", []),
            "amendments_total": int(parliament.get("amendment_activity", {}).get("total", 0)),
            "amendments_by_group": parliament.get("amendment_activity", {}).get("by_group", {}),
            "oeil_events": len(council.get("oeil_events", [])),
        }
        completeness = self._completeness(commission, parliament, council)
        confidence = self._confidence(completeness)

        return FilePosition(
            procedure_ref=carriage.oeil_procedure_ref or carriage.file_id or "",
            commission=commission,
            parliament=parliament,
            council=council,
            amendments_by_article=amendments_by_article,
            data_completeness=completeness,
            confidence=confidence,
            sources=sources,
        )

    async def aggregate_and_cache(self, carriage: LegislativeCarriage) -> FilePosition:
        """Compute and upsert a snapshot row."""
        fp = await self.aggregate(carriage)
        self._upsert_snapshot(carriage, fp)
        return fp

    def get_cached(self, carriage_id: Any) -> Optional[FilePositionSnapshot]:
        return (
            self.db.query(FilePositionSnapshot)
            .filter(FilePositionSnapshot.carriage_id == carriage_id)
            .first()
        )

    def is_fresh(self, snap: FilePositionSnapshot) -> bool:
        if not snap or not snap.generated_at:
            return False
        gen_at = snap.generated_at
        if gen_at.tzinfo is None:
            gen_at = gen_at.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - gen_at) < timedelta(hours=SNAPSHOT_TTL_HOURS)

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #

    def _commission_block(self, carriage: LegislativeCarriage) -> Dict[str, Any]:
        """Commission proposal summary: COM references, celex numbers, headline text."""
        celex = list(carriage.celex_numbers or [])
        com_refs: List[str] = []
        docs_meta: List[Dict[str, Any]] = []
        if celex:
            docs = (
                self.db.query(CommissionDocument)
                .filter(CommissionDocument.celex.in_(celex))
                .all()
            )
            for d in docs:
                docs_meta.append({
                    "reference": d.reference,
                    "title": d.title,
                    "doc_type": d.doc_type,
                    "publication_date": d.publication_date.isoformat() if d.publication_date else None,
                    "portal_url": d.portal_url,
                    "celex": d.celex,
                })
                if d.reference:
                    com_refs.append(d.reference)

        return {
            "title": carriage.title or "",
            "description": (carriage.description or "")[:800],
            "com_references": sorted(set(com_refs)),
            "celex_numbers": celex,
            "text_type": carriage.text_type,
            "proposal_date": next(
                (d["publication_date"] for d in docs_meta if d.get("publication_date")), None,
            ),
            "documents": docs_meta,
            "lead_dg": self._lead_dg_from_docs(docs_meta),
        }

    @staticmethod
    def _lead_dg_from_docs(docs: List[Dict[str, Any]]) -> Optional[str]:
        for d in docs:
            if (d.get("doc_type") or "").upper() in ("COM", "JOIN") and d.get("title"):
                return d.get("title", "").split("-", 1)[0].strip()
        return None

    async def _parliament_block(self, carriage: LegislativeCarriage) -> Dict[str, Any]:
        """EP stance: rapporteur + committees + per-group predicted position + amendment activity."""
        lead_committee = carriage.lead_committee
        rapporteur_group = self._rapporteur_group(carriage)

        # Per-group predictions via the existing GroupVotePredictor
        group_positions: List[GroupPosition] = []
        try:
            from services.predictions.group_vote_predictor import get_group_vote_predictor
            predictor = get_group_vote_predictor()
            plenary = await predictor.predict_plenary_vote(
                procedure_ref=carriage.oeil_procedure_ref or "",
                lead_committee=lead_committee,
                rapporteur_group=rapporteur_group,
                title=carriage.title,
            )
            for gp in plenary.group_predictions:
                group_positions.append(GroupPosition(
                    group_code=gp.group_code,
                    stance=(gp.predicted_position.value if hasattr(gp.predicted_position, "value") else str(gp.predicted_position)).lower(),
                    confidence=self._confidence_from_cohesion(gp.expected_cohesion),
                    cohesion=round(float(gp.expected_cohesion), 3),
                    rationale=self._group_rationale(gp, rapporteur_group),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[position-agg] GroupVotePredictor failed for %s: %s", carriage.oeil_procedure_ref, exc)
            # Predictor may have poisoned the shared session with a failed Postgres transaction
            try: self.db.rollback()
            except Exception: pass
            # Produce a baseline set of groups so the UI still has something to render
            group_positions = self._baseline_groups(rapporteur_group)

        # Amendment activity by group (ground truth from mep_amendments)
        activity = self._amendment_activity(carriage)

        # Enrich group_positions with amendment counts and top amendments
        by_group_counts = activity["by_group"]
        for gp in group_positions:
            display = GROUP_DISPLAY.get(gp.group_code, gp.group_code)
            count = 0
            for key, n in by_group_counts.items():
                if GROUP_DISPLAY.get(key, key) == display:
                    count += n
            gp.amendment_count = count

        top_amends_by_group = self._top_amendments_by_group(carriage, limit_per_group=3)
        for gp in group_positions:
            display = GROUP_DISPLAY.get(gp.group_code, gp.group_code)
            gp.top_amendments = top_amends_by_group.get(display, [])

        return {
            "lead_committee": lead_committee,
            "opinion_committees": carriage.opinion_committees or [],
            "rapporteur": self._rapporteur_name(carriage),
            "rapporteur_group": rapporteur_group,
            "groups": [asdict(g) for g in group_positions],
            "amendment_activity": activity,
            "plenary_adopted": self._plenary_adopted(carriage),
        }

    async def _council_block(self, carriage: LegislativeCarriage) -> Dict[str, Any]:
        """Council stance: per-MS inference + OEIL Council events."""
        state_positions: List[MemberStatePosition] = []
        try:
            from services.predictions.council_position_inferrer import get_council_position_inferrer
            inferrer = get_council_position_inferrer()
            prediction = await inferrer.predict_council_vote(
                procedure_ref=carriage.oeil_procedure_ref or "",
                lead_committee=carriage.lead_committee,
                title=carriage.title,
            )
            for sp in prediction.state_positions:
                cc = (sp.country_code or "").upper()
                state_positions.append(MemberStatePosition(
                    country_code=cc,
                    country_name=COUNTRY_NAME.get(cc, cc),
                    stance=str(sp.position or "undecided").lower(),
                    confidence=(sp.confidence.value if hasattr(sp.confidence, "value") else str(sp.confidence or "low")).lower(),
                    rationale=(sp.rationale or "") if hasattr(sp, "rationale") else "",
                    signal_count=len(getattr(sp, "signals", []) or []),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[position-agg] CouncilPositionInferrer failed for %s: %s", carriage.oeil_procedure_ref, exc)
            try: self.db.rollback()
            except Exception: pass
            state_positions = self._baseline_member_states()

        # OEIL events referencing Council
        events = self._council_events(carriage)

        # Aggregate into support / oppose / undecided blocs
        supporting = [p for p in state_positions if p.stance == "support"]
        opposing = [p for p in state_positions if p.stance == "oppose"]
        neutral = [p for p in state_positions if p.stance not in ("support", "oppose")]

        return {
            "member_states": [asdict(s) for s in state_positions],
            "summary": {
                "supporting_count": len(supporting),
                "opposing_count": len(opposing),
                "undecided_count": len(neutral),
                "supporting": [s.country_code for s in supporting],
                "opposing": [s.country_code for s in opposing],
            },
            "oeil_events": events,
            "general_approach_adopted": any(
                "general approach" in (e.get("summary") or "").lower() for e in events
            ),
        }

    def _amendments_by_article(self, carriage: LegislativeCarriage, limit_articles: int = 25) -> List[Dict[str, Any]]:
        """Article-by-article amendment drill-down (v2)."""
        proc_ref = carriage.oeil_procedure_ref
        if not proc_ref:
            return []
        rows = (
            self.db.query(
                MEPAmendment.element_reference,
                MEPAmendment.political_group,
                func.count(MEPAmendment.id).label("n"),
            )
            .filter(MEPAmendment.procedure_reference == proc_ref)
            .filter(MEPAmendment.element_reference.isnot(None))
            .group_by(MEPAmendment.element_reference, MEPAmendment.political_group)
            .all()
        )
        by_article: Dict[str, Dict[str, int]] = {}
        for art, group, n in rows:
            key = art or "(unspecified)"
            by_article.setdefault(key, {})
            by_article[key][group or "Unknown"] = int(n)
        # Rank by total activity, return most-amended articles first
        out = []
        for art, counts in sorted(by_article.items(), key=lambda kv: -sum(kv[1].values()))[: limit_articles]:
            out.append({
                "article": art,
                "by_group": counts,
                "total": sum(counts.values()),
            })
        return out

    # ------------------------------------------------------------------ #
    # Low-level helpers
    # ------------------------------------------------------------------ #

    def _amendment_activity(self, carriage: LegislativeCarriage) -> Dict[str, Any]:
        proc_ref = carriage.oeil_procedure_ref
        if not proc_ref:
            return {"total": 0, "by_group": {}, "by_mep_top": []}
        rows = (
            self.db.query(MEPAmendment.political_group, func.count(MEPAmendment.id))
            .filter(MEPAmendment.procedure_reference == proc_ref)
            .group_by(MEPAmendment.political_group)
            .all()
        )
        by_group = {g or "Unknown": int(n) for g, n in rows}
        total = sum(by_group.values())
        # Top MEPs: unnest author_names array
        top_rows = (
            self.db.query(
                func.unnest(MEPAmendment.author_names).label("mep"),
                MEPAmendment.political_group,
                func.count(MEPAmendment.id).label("n"),
            )
            .filter(MEPAmendment.procedure_reference == proc_ref)
            .group_by("mep", MEPAmendment.political_group)
            .order_by(func.count(MEPAmendment.id).desc())
            .limit(8)
            .all()
        )
        return {
            "total": total,
            "by_group": by_group,
            "by_mep_top": [
                {"mep": (r[0] or "Unknown"), "group": (r[1] or ""), "count": int(r[2])}
                for r in top_rows
            ],
        }

    def _top_amendments_by_group(
        self, carriage: LegislativeCarriage, limit_per_group: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        proc_ref = carriage.oeil_procedure_ref
        if not proc_ref:
            return {}
        rows = (
            self.db.query(MEPAmendment)
            .filter(MEPAmendment.procedure_reference == proc_ref)
            .order_by(MEPAmendment.document_date.desc().nullslast())
            .limit(300)
            .all()
        )
        out: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            display = GROUP_DISPLAY.get((r.political_group or ""), r.political_group or "")
            bucket = out.setdefault(display, [])
            if len(bucket) >= limit_per_group:
                continue
            authors = r.author_names if isinstance(r.author_names, list) else []
            bucket.append({
                "author": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "group": r.political_group,
                "article": r.element_reference,
                "amendment_type": r.amendment_type,
                "summary": ((r.justification or r.proposed_text or "") or "")[:240],
                "tabled_date": r.document_date.isoformat() if getattr(r, "document_date", None) else None,
            })
        return out

    def _rapporteur_name(self, carriage: LegislativeCarriage) -> Optional[str]:
        if not carriage.oeil_procedure_data:
            return None
        data = carriage.oeil_procedure_data or {}
        for key in ("rapporteur", "rapporteur_name", "rapporteurs"):
            v = data.get(key)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, dict):
                    return first.get("name")
                if isinstance(first, str):
                    return first
        return None

    def _rapporteur_group(self, carriage: LegislativeCarriage) -> Optional[str]:
        if not carriage.oeil_procedure_data:
            return None
        data = carriage.oeil_procedure_data or {}
        v = data.get("rapporteur_group") or data.get("rapporteur_political_group")
        if isinstance(v, str):
            return v
        raps = data.get("rapporteurs") or []
        if isinstance(raps, list) and raps:
            first = raps[0]
            if isinstance(first, dict):
                return first.get("group") or first.get("political_group")
        return None

    def _plenary_adopted(self, carriage: LegislativeCarriage) -> Dict[str, Any]:
        events = self._oeil_events(carriage)
        for e in events:
            text = (e.get("summary") or e.get("type") or "").lower()
            if "text adopted by parliament" in text or "adopted by parliament" in text:
                return {"adopted": True, "date": e.get("date"), "reference": e.get("reference")}
        return {"adopted": False}

    def _council_events(self, carriage: LegislativeCarriage) -> List[Dict[str, Any]]:
        out = []
        for e in self._oeil_events(carriage):
            text = (e.get("summary") or e.get("type") or "").lower()
            if "council" in text or "general approach" in text or "first reading position" in text:
                out.append(e)
        return out

    @staticmethod
    def _oeil_events(carriage: LegislativeCarriage) -> List[Dict[str, Any]]:
        raw = carriage.oeil_key_events or []
        if isinstance(raw, list):
            return [e for e in raw if isinstance(e, dict)]
        return []

    @staticmethod
    def _confidence_from_cohesion(cohesion: float) -> str:
        if cohesion >= 0.8:
            return "high"
        if cohesion >= 0.6:
            return "medium"
        return "low"

    @staticmethod
    def _group_rationale(gp, rapporteur_group: Optional[str]) -> str:
        if rapporteur_group and gp.group_code == rapporteur_group:
            return "Rapporteur's group -- owns the file."
        base = f"Predicted {gp.predicted_position.value if hasattr(gp.predicted_position, 'value') else gp.predicted_position} with cohesion {gp.expected_cohesion:.2f}."
        if gp.prob_for >= 0.6:
            return base + " Historical pattern favours FOR."
        if gp.prob_against >= 0.6:
            return base + " Historical pattern favours AGAINST."
        return base + " Swing group."

    @staticmethod
    def _completeness(commission: Dict, parliament: Dict, council: Dict) -> str:
        score = 0
        if commission.get("com_references"):
            score += 1
        if parliament.get("groups"):
            score += 1
        if parliament.get("amendment_activity", {}).get("total", 0) > 0:
            score += 1
        if council.get("member_states"):
            score += 1
        if score >= 3:
            return "full"
        if score == 2:
            return "partial"
        return "minimal"

    @staticmethod
    def _confidence(completeness: str) -> str:
        return {"full": "high", "partial": "medium", "minimal": "low"}.get(completeness, "low")

    @staticmethod
    def _baseline_groups(rapporteur_group: Optional[str]) -> List[GroupPosition]:
        """Fallback: list all EP groups with 'unknown' stance when predictor fails."""
        groups = ["PPE", "S&D", "Renew", "Verts/ALE", "ECR", "PfE", "GUE/NGL", "ESN", "NI"]
        out = []
        for g in groups:
            rationale = "Rapporteur's group." if rapporteur_group and g == rapporteur_group else "Prediction unavailable; inspect amendment activity."
            out.append(GroupPosition(
                group_code=g,
                stance="unknown",
                confidence="low",
                cohesion=0.0,
                rationale=rationale,
            ))
        return out

    @staticmethod
    def _baseline_member_states() -> List[MemberStatePosition]:
        return [
            MemberStatePosition(
                country_code=cc,
                country_name=name,
                stance="undecided",
                confidence="low",
                rationale="Council position inference unavailable; inspect OEIL events below.",
            )
            for cc, name in COUNTRY_NAME.items()
        ]

    def _upsert_snapshot(self, carriage: LegislativeCarriage, fp: FilePosition) -> None:
        existing = (
            self.db.query(FilePositionSnapshot)
            .filter(FilePositionSnapshot.carriage_id == carriage.id)
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = FilePositionSnapshot(
                carriage_id=carriage.id,
                procedure_ref=fp.procedure_ref,
            )
            self.db.add(existing)
        existing.procedure_ref = fp.procedure_ref
        existing.commission_position = fp.commission
        existing.parliament_position = fp.parliament
        existing.council_position = fp.council
        existing.amendment_positions = fp.amendments_by_article
        existing.data_completeness = fp.data_completeness
        existing.confidence = fp.confidence
        existing.sources = fp.sources
        existing.generated_at = now
        existing.expires_at = now + timedelta(hours=SNAPSHOT_TTL_HOURS)
        self.db.commit()


_singleton: Optional[PositionAggregator] = None


def get_position_aggregator(db: Optional[Session] = None) -> PositionAggregator:
    global _singleton
    if db is not None:
        return PositionAggregator(db=db)
    if _singleton is None:
        _singleton = PositionAggregator()
    return _singleton
