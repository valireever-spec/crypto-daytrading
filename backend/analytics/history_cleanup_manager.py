"""
Phase 328: History Cleanup Manager

Prevent unbounded memory growth by archiving old records.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of cleanup operation."""

    archived_count: int
    remaining_count: int
    space_freed_kb: float
    last_archived_date: Optional[datetime]
    next_cleanup_recommended: bool


class HistoryCleanupManager:
    """Manage history cleanup and archival."""

    def __init__(self, archive_dir: str = "logs/archive", retention_count: int = 100):
        """
        Initialize cleanup manager.

        Parameters:
        -----------
        archive_dir : str
            Directory to archive old records
        retention_count : int
            Number of records to keep (older ones archived)
        """
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.retention_count = retention_count
        self.cleanup_history: List[CleanupResult] = []

    def cleanup_rebalancing_history(
        self,
        history_list: List[Any],  # List of RebalancingPlan objects
    ) -> CleanupResult:
        """
        Archive old rebalancing records.

        Parameters:
        -----------
        history_list : list
            List of RebalancingPlan objects

        Returns:
        --------
        CleanupResult with statistics
        """
        if len(history_list) <= self.retention_count:
            return CleanupResult(
                archived_count=0,
                remaining_count=len(history_list),
                space_freed_kb=0.0,
                last_archived_date=None,
                next_cleanup_recommended=False,
            )

        # Keep most recent, archive oldest
        to_archive = history_list[: len(history_list) - self.retention_count]
        to_keep = history_list[len(history_list) - self.retention_count :]

        # Archive as JSON
        archive_file = (
            self.archive_dir
            / f"rebalancing_{datetime.now(timezone.utc).isoformat()}.json"
        )
        archived_data = [
            {
                "num_trades": len(p.trades) if hasattr(p, "trades") else 0,
                "total_cost_pct": p.total_cost_pct
                if hasattr(p, "total_cost_pct")
                else 0,
                "feasible": p.feasible if hasattr(p, "feasible") else False,
            }
            for p in to_archive
        ]

        try:
            with open(archive_file, "w") as f:
                json.dump(archived_data, f, indent=2)
            space_freed = archive_file.stat().st_size / 1024
            logger.info(
                f"Archived {len(to_archive)} rebalancing records to {archive_file}"
            )
        except Exception as e:
            logger.error(f"Error archiving rebalancing history: {e}")
            space_freed = 0.0

        result = CleanupResult(
            archived_count=len(to_archive),
            remaining_count=len(to_keep),
            space_freed_kb=space_freed,
            last_archived_date=datetime.now(timezone.utc),
            next_cleanup_recommended=len(to_keep) > self.retention_count * 1.2,
        )

        self.cleanup_history.append(result)
        return result

    def cleanup_recommendations_and_outcomes(
        self,
        recommendations: List[Any],
        outcomes: List[Any],
    ) -> CleanupResult:
        """
        Archive old recommendations and outcomes.

        Parameters:
        -----------
        recommendations : list
            List of RecommendationRecord objects
        outcomes : list
            List of OutcomeRecord objects

        Returns:
        --------
        CleanupResult with statistics
        """
        total_before = len(recommendations) + len(outcomes)
        cutoff_days = self.retention_count  # Keep last N days

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=cutoff_days)

        # Filter to keep recent
        recs_to_keep = [r for r in recommendations if r.timestamp >= cutoff_date]
        outcomes_to_keep = [o for o in outcomes if o.timestamp >= cutoff_date]

        archived_count = (len(recommendations) - len(recs_to_keep)) + (
            len(outcomes) - len(outcomes_to_keep)
        )

        # Archive
        archive_file = (
            self.archive_dir
            / f"performance_{datetime.now(timezone.utc).isoformat()}.json"
        )
        archived_data = {
            "recommendations_archived": len(recommendations) - len(recs_to_keep),
            "outcomes_archived": len(outcomes) - len(outcomes_to_keep),
            "cutoff_date": cutoff_date.isoformat(),
        }

        try:
            with open(archive_file, "w") as f:
                json.dump(archived_data, f, indent=2)
            space_freed = archive_file.stat().st_size / 1024
            logger.info(
                f"Archived {archived_count} performance records to {archive_file}"
            )
        except Exception as e:
            logger.error(f"Error archiving performance history: {e}")
            space_freed = 0.0

        result = CleanupResult(
            archived_count=archived_count,
            remaining_count=len(recs_to_keep) + len(outcomes_to_keep),
            space_freed_kb=space_freed,
            last_archived_date=datetime.now(timezone.utc),
            next_cleanup_recommended=archived_count > 50,
        )

        self.cleanup_history.append(result)
        return result

    def get_cleanup_schedule(self) -> Dict[str, Any]:
        """Get recommended cleanup schedule."""
        return {
            "retention_count": self.retention_count,
            "cleanup_interval_days": 30,
            "next_recommended_cleanup": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat(),
            "archive_location": str(self.archive_dir),
            "total_cleanups_performed": len(self.cleanup_history),
        }


# Global instance
_cleanup_manager: HistoryCleanupManager = None


def get_cleanup_manager() -> HistoryCleanupManager:
    """Get or create cleanup manager."""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = HistoryCleanupManager()
    return _cleanup_manager
