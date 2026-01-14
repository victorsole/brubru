"""
Data Synchronization Orchestrator

Coordinates and schedules data fetching from all EU institutional APIs:
- Scheduled background tasks
- Priority-based execution
- Error recovery and retry
- Progress tracking
- Incremental updates

Sync tasks:
- RSS feeds (every 15 minutes)
- EUR-Lex documents (every hour)
- MEP profiles (daily)
- TED notices (every 30 minutes)
- IATE terminology (weekly)
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from services.api_clients.european_parliament_client import EuropeanParliamentClient
from services.api_clients.eurlex_client import EURLexClient
from services.api_clients.publications_office_client import PublicationsOfficeClient
from services.api_clients.iate_client import IATEClient
from services.api_clients.data_europa_client import DataEuropaClient
from services.rss.rss_aggregator import RSSAggregator

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Sync task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SyncPriority(Enum):
    """Sync task priority"""
    CRITICAL = 1  # Run immediately, every time
    HIGH = 2  # Run frequently
    MEDIUM = 3  # Run regularly
    LOW = 4  # Run occasionally


@dataclass
class SyncTask:
    """Represents a data synchronization task"""
    name: str
    description: str
    priority: SyncPriority
    interval_seconds: int
    handler: Callable
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: SyncStatus = SyncStatus.PENDING
    last_result: Optional[Dict[str, Any]] = None
    error_count: int = 0
    total_runs: int = 0


class SyncOrchestrator:
    """
    Orchestrates all data synchronization tasks

    Features:
    - Priority-based scheduling
    - Concurrent execution with rate limiting
    - Error recovery and exponential backoff
    - Progress tracking and reporting
    - Incremental updates
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        enable_auto_sync: bool = True
    ):
        """
        Initialize sync orchestrator

        Args:
            database_url: Database connection URL (for storing sync state)
            enable_auto_sync: Enable automatic background sync
        """
        # Initialize clients
        self.rss_aggregator = RSSAggregator()
        self.ep_client = EuropeanParliamentClient()
        self.eurlex_client = EURLexClient()
        self.publications_client = PublicationsOfficeClient()
        self.iate_client = IATEClient()
        self.data_europa_client = DataEuropaClient()

        # Sync tasks registry
        self.tasks: Dict[str, SyncTask] = {}

        # Background task
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False

        # Configuration
        self.enable_auto_sync = enable_auto_sync
        self.database_url = database_url

        # Initialize tasks
        self._register_tasks()

        logger.info("Initialized Data Sync Orchestrator")

    def _register_tasks(self):
        """Register all sync tasks"""

        # RSS Feeds (every 15 minutes)
        self.tasks["rss_feeds"] = SyncTask(
            name="rss_feeds",
            description="Fetch all RSS feeds from EU institutions",
            priority=SyncPriority.CRITICAL,
            interval_seconds=900,  # 15 minutes
            handler=self._sync_rss_feeds
        )

        # EUR-Lex documents (every hour)
        self.tasks["eurlex_documents"] = SyncTask(
            name="eurlex_documents",
            description="Sync EUR-Lex legal documents",
            priority=SyncPriority.HIGH,
            interval_seconds=3600,  # 1 hour
            handler=self._sync_eurlex_documents
        )

        # TED procurement notices (every 30 minutes)
        self.tasks["ted_notices"] = SyncTask(
            name="ted_notices",
            description="Fetch TED procurement notices",
            priority=SyncPriority.HIGH,
            interval_seconds=1800,  # 30 minutes
            handler=self._sync_ted_notices
        )

        # MEP profiles (daily)
        self.tasks["mep_profiles"] = SyncTask(
            name="mep_profiles",
            description="Update MEP profiles",
            priority=SyncPriority.MEDIUM,
            interval_seconds=86400,  # 24 hours
            handler=self._sync_mep_profiles
        )

        # European Parliament documents (every 2 hours)
        self.tasks["ep_documents"] = SyncTask(
            name="ep_documents",
            description="Sync European Parliament documents",
            priority=SyncPriority.MEDIUM,
            interval_seconds=7200,  # 2 hours
            handler=self._sync_ep_documents
        )

        # Data.europa.eu datasets (daily)
        self.tasks["datasets"] = SyncTask(
            name="datasets",
            description="Update open datasets catalog",
            priority=SyncPriority.LOW,
            interval_seconds=86400,  # 24 hours
            handler=self._sync_datasets
        )

        # IATE terminology (weekly)
        self.tasks["iate_terminology"] = SyncTask(
            name="iate_terminology",
            description="Update IATE terminology database",
            priority=SyncPriority.LOW,
            interval_seconds=604800,  # 7 days
            handler=self._sync_iate_terminology
        )

        logger.info(f"Registered {len(self.tasks)} sync tasks")

    async def _sync_rss_feeds(self) -> Dict[str, Any]:
        """Sync RSS feeds"""
        logger.info("Syncing RSS feeds")

        try:
            # Fetch last 24 hours
            since = datetime.now() - timedelta(hours=24)
            entries = await self.rss_aggregator.fetch_all_feeds(since=since)

            # TODO: Store entries in database

            return {
                "success": True,
                "entries_fetched": len(entries),
                "sources": len(set(e.source for e in entries))
            }

        except Exception as e:
            logger.error(f"RSS feed sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_eurlex_documents(self) -> Dict[str, Any]:
        """Sync EUR-Lex documents"""
        logger.info("Syncing EUR-Lex documents")

        try:
            # Fetch documents from last week
            date_from = datetime.now() - timedelta(days=7)
            documents = await self.eurlex_client.search_documents(
                query="",
                date_from=date_from,
                limit=200
            )

            # TODO: Store documents in database

            return {
                "success": True,
                "documents_fetched": len(documents)
            }

        except Exception as e:
            logger.error(f"EUR-Lex sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_ted_notices(self) -> Dict[str, Any]:
        """Sync TED procurement notices"""
        logger.info("Syncing TED notices")

        try:
            # Fetch notices from last 7 days
            date_from = datetime.now() - timedelta(days=7)
            notices = await self.publications_client.search_ted_notices(
                date_from=date_from,
                limit=200
            )

            # TODO: Store notices in database

            return {
                "success": True,
                "notices_fetched": len(notices)
            }

        except Exception as e:
            logger.error(f"TED notices sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_mep_profiles(self) -> Dict[str, Any]:
        """Sync MEP profiles"""
        logger.info("Syncing MEP profiles")

        try:
            meps = await self.ep_client.get_mep_list()

            # TODO: Store MEP profiles in database

            return {
                "success": True,
                "meps_fetched": len(meps)
            }

        except Exception as e:
            logger.error(f"MEP profiles sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_ep_documents(self) -> Dict[str, Any]:
        """Sync European Parliament documents"""
        logger.info("Syncing EP documents")

        try:
            # Fetch documents from last month
            date_from = datetime.now() - timedelta(days=30)
            documents = await self.ep_client.search_documents(
                query="",
                date_from=date_from,
                limit=200
            )

            # TODO: Store documents in database

            return {
                "success": True,
                "documents_fetched": len(documents)
            }

        except Exception as e:
            logger.error(f"EP documents sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_datasets(self) -> Dict[str, Any]:
        """Sync open datasets from EU institutions"""
        logger.info("Syncing datasets from EU institutions")

        try:
            all_datasets = []

            # Fetch datasets from key EU institutions
            institutions = [
                ("ep", "European Parliament"),
                ("estat", "Eurostat"),
                ("consil", "Council"),
                ("eea-sdi", "European Environment Agency")
            ]

            for institution_id, institution_name in institutions:
                try:
                    logger.info(f"Fetching datasets from {institution_name}")
                    inst_datasets = await self.data_europa_client.get_eu_institution_datasets(
                        institution=institution_id,
                        limit=50
                    )
                    all_datasets.extend(inst_datasets)
                    logger.info(f"Fetched {len(inst_datasets)} datasets from {institution_name}")
                except Exception as e:
                    logger.warning(f"Failed to fetch datasets from {institution_name}: {str(e)}")
                    continue

            # TODO: Store datasets in database

            return {
                "success": True,
                "datasets_fetched": len(all_datasets),
                "institutions_synced": len(institutions)
            }

        except Exception as e:
            logger.error(f"Datasets sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _sync_iate_terminology(self) -> Dict[str, Any]:
        """Sync IATE terminology"""
        logger.info("Syncing IATE terminology")

        try:
            # Sample terminology sync (would need more comprehensive approach)
            terms = []
            for domain in ["ENVIRONMENT", "DIGITAL"]:
                domain_terms = await self.iate_client.search_terms(
                    query=domain,
                    limit=50
                )
                terms.extend(domain_terms)

            # TODO: Store terms in database

            return {
                "success": True,
                "terms_fetched": len(terms)
            }

        except Exception as e:
            logger.error(f"IATE terminology sync failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def run_task(self, task_name: str) -> Dict[str, Any]:
        """
        Run specific sync task

        Args:
            task_name: Name of task to run

        Returns:
            Task result
        """
        if task_name not in self.tasks:
            raise ValueError(f"Unknown task: {task_name}")

        task = self.tasks[task_name]

        logger.info(f"Running sync task: {task_name}")

        task.status = SyncStatus.RUNNING
        task.last_run = datetime.now()
        task.total_runs += 1

        try:
            result = await task.handler()
            task.status = SyncStatus.COMPLETED
            task.last_result = result
            task.error_count = 0
            task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)

            logger.info(f"Task {task_name} completed successfully")
            return result

        except Exception as e:
            logger.error(f"Task {task_name} failed: {str(e)}")
            task.status = SyncStatus.FAILED
            task.error_count += 1
            task.last_result = {"success": False, "error": str(e)}

            # Exponential backoff for failed tasks
            backoff = min(task.interval_seconds * (2 ** task.error_count), 3600)
            task.next_run = datetime.now() + timedelta(seconds=backoff)

            return task.last_result

    async def run_all_tasks(self) -> Dict[str, Any]:
        """
        Run all sync tasks

        Returns:
            Summary of all tasks
        """
        logger.info("Running all sync tasks")

        results = {}
        for task_name in self.tasks.keys():
            results[task_name] = await self.run_task(task_name)

        return results

    async def start_background_sync(self):
        """Start background sync scheduler"""
        if self._running:
            logger.warning("Background sync already running")
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._background_sync_loop())
        logger.info("Started background sync scheduler")

    async def stop_background_sync(self):
        """Stop background sync scheduler"""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background sync scheduler")

    async def _background_sync_loop(self):
        """Background task scheduling loop"""
        logger.info("Background sync loop started")

        while self._running:
            try:
                now = datetime.now()

                # Check which tasks need to run
                tasks_to_run = []
                for task in self.tasks.values():
                    if task.next_run is None or task.next_run <= now:
                        tasks_to_run.append(task.name)

                # Run tasks by priority
                tasks_to_run.sort(
                    key=lambda name: self.tasks[name].priority.value
                )

                for task_name in tasks_to_run:
                    if not self._running:
                        break
                    await self.run_task(task_name)

                # Wait before next check (60 seconds)
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background sync loop error: {str(e)}")
                await asyncio.sleep(60)

        logger.info("Background sync loop stopped")

    def get_task_status(self, task_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of sync tasks

        Args:
            task_name: Specific task name (None for all)

        Returns:
            Task status information
        """
        if task_name:
            if task_name not in self.tasks:
                raise ValueError(f"Unknown task: {task_name}")

            task = self.tasks[task_name]
            return {
                "name": task.name,
                "description": task.description,
                "priority": task.priority.name,
                "status": task.status.value,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "total_runs": task.total_runs,
                "error_count": task.error_count,
                "last_result": task.last_result
            }

        # Return all tasks
        return {
            task_name: self.get_task_status(task_name)
            for task_name in self.tasks.keys()
        }

    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get overall sync statistics

        Returns:
            Statistics summary
        """
        total_runs = sum(task.total_runs for task in self.tasks.values())
        total_errors = sum(task.error_count for task in self.tasks.values())

        successful_tasks = sum(
            1 for task in self.tasks.values()
            if task.status == SyncStatus.COMPLETED
        )

        return {
            "total_tasks": len(self.tasks),
            "total_runs": total_runs,
            "total_errors": total_errors,
            "successful_tasks": successful_tasks,
            "running": self._running,
            "tasks_by_status": {
                status.value: sum(
                    1 for task in self.tasks.values()
                    if task.status == status
                )
                for status in SyncStatus
            }
        }

    async def close(self):
        """Stop background sync and close all clients"""
        await self.stop_background_sync()

        await self.rss_aggregator.close()
        await self.ep_client.close()
        await self.eurlex_client.close()
        await self.publications_client.close()
        await self.iate_client.close()
        await self.data_europa_client.close()

        logger.info("Closed sync orchestrator")
