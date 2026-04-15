"""
Generic RSS/Atom ingester.

Reads YAML configs from `configs/*.yaml`, fetches each feed, normalises entries
into the `institutional_publications` table. One ingester class serves N feeds
— no per-feed Python code needed.

Config shape (YAML):
    slug: ec_press
    institution_slug: european_commission
    category: press_release
    url: https://feeds.ec.europa.eu/news/en/RSS-all.xml
    default_policy_areas: []
    language: en
    # Optional: fetch full article HTML if the feed only provides summaries
    fetch_full_content: false
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.database import SessionLocal
from models.institutional_publication import InstitutionalPublication
from services.api_clients.base_rss_client import BaseRSSClient

logger = logging.getLogger(__name__)


CONFIGS_DIR = Path(__file__).parent / "configs"


@dataclass
class FeedConfig:
    slug: str
    institution_slug: str
    url: str
    category: Optional[str] = None
    default_policy_areas: Optional[List[str]] = None
    language: str = "en"
    fetch_full_content: bool = False

    @classmethod
    def from_file(cls, path: Path) -> "FeedConfig":
        data = yaml.safe_load(path.read_text())
        return cls(
            slug=data["slug"],
            institution_slug=data["institution_slug"],
            url=data["url"],
            category=data.get("category"),
            default_policy_areas=data.get("default_policy_areas") or [],
            language=data.get("language", "en"),
            fetch_full_content=bool(data.get("fetch_full_content", False)),
        )


def list_configs() -> List[FeedConfig]:
    if not CONFIGS_DIR.exists():
        return []
    return [FeedConfig.from_file(p) for p in sorted(CONFIGS_DIR.glob("*.yaml"))]


class RSSIngestor:
    """Fetch one feed, upsert into institutional_publications. Returns stats."""

    def __init__(self, config: FeedConfig):
        self.config = config

    async def run(self) -> Dict[str, int]:
        client = BaseRSSClient()
        try:
            feed = await client.fetch_feed(self.config.url)
            entries = feed.entries
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[ingest:{self.config.slug}] fetch failed: {exc}")
            return {"fetched": 0, "inserted": 0, "skipped": 0, "error": 1}
        finally:
            try:
                await client.close()
            except Exception:
                pass

        db = SessionLocal()
        inserted = 0
        skipped = 0
        try:
            for entry in entries:
                ext_id, row = self._entry_to_row(entry)
                if not ext_id:
                    skipped += 1
                    continue
                exists = (
                    db.query(InstitutionalPublication)
                    .filter(
                        InstitutionalPublication.source_slug == self.config.slug,
                        InstitutionalPublication.external_id == ext_id,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    continue
                db.add(InstitutionalPublication(**row))
                inserted += 1
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception(f"[ingest:{self.config.slug}] DB error: {exc}")
            return {"fetched": len(entries), "inserted": inserted, "skipped": skipped, "error": 1}
        finally:
            db.close()

        return {"fetched": len(entries), "inserted": inserted, "skipped": skipped, "error": 0}

    def _entry_to_row(self, entry: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """Convert an RSSEntry into (external_id, row_dict)."""
        ext_id = getattr(entry, "id", None) or getattr(entry, "link", None)
        if not ext_id:
            return None, {}

        title = (getattr(entry, "title", "") or "").strip()
        url = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", None) or getattr(entry, "content", None)
        published = getattr(entry, "published", None)

        def _norm_dt(v: Any) -> Optional[datetime]:
            if isinstance(v, datetime):
                return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            return None

        tags_raw = getattr(entry, "categories", None) or []
        tags: List[str] = [t for t in tags_raw if isinstance(t, str)]

        row = {
            "source_slug": self.config.slug,
            "institution_slug": self.config.institution_slug,
            "category": self.config.category,
            "external_id": ext_id[:500],
            "url": url,
            "title": title[:1000] if title else (url[:200] if url else "(untitled)"),
            "summary": summary,
            "language": self.config.language,
            "published_date": _norm_dt(published),
            "updated_date": None,
            "policy_areas": list(self.config.default_policy_areas or []),
            "tags": tags,
            "authors": [],
            "extra_metadata": {},
        }
        return ext_id, row


async def ingest_all(only: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
    """Run every config (or a subset by slug). Returns {slug: stats}."""
    configs = list_configs()
    if only:
        configs = [c for c in configs if c.slug in set(only)]
    results: Dict[str, Dict[str, int]] = {}
    for cfg in configs:
        logger.info(f"[ingest] running {cfg.slug} <- {cfg.url}")
        results[cfg.slug] = await RSSIngestor(cfg).run()
    return results
