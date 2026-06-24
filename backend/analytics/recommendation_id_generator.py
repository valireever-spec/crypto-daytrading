"""
Phase 330+: Recommendation ID Generator

Generate and track recommendation IDs for Phase 325 integration.
"""

import logging
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RecommendationIDGenerator:
    """Generate unique IDs for recommendations and track allocation."""

    def __init__(self):
        """Initialize generator."""
        self.last_generated = None

    def generate_recommendation_id(self, symbol: str = "", scenario: str = "") -> str:
        """
        Generate unique recommendation ID.

        Parameters:
        -----------
        symbol : str
            Symbol for this recommendation (informational)
        scenario : str
            Scenario type (base/upside/downside) (informational)

        Returns:
        --------
        UUID string formatted as rec-{uuid}
        """
        rec_id = f"rec-{uuid4()}"
        self.last_generated = {
            "id": rec_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "scenario": scenario,
        }
        logger.debug(f"Generated recommendation ID: {rec_id} ({symbol}/{scenario})")
        return rec_id

    def get_last_generated(self) -> Optional[dict]:
        """Get metadata of last generated ID."""
        return self.last_generated


def ensure_recommendation_has_id(recommendation: dict) -> dict:
    """
    Ensure recommendation record has recommendation_id field.

    If missing, generates one. Useful for Phase 325 compatibility.

    Parameters:
    -----------
    recommendation : dict
        Recommendation record (may lack recommendation_id)

    Returns:
    --------
    Recommendation with recommendation_id guaranteed
    """
    if "recommendation_id" not in recommendation or not recommendation["recommendation_id"]:
        generator = RecommendationIDGenerator()
        recommendation["recommendation_id"] = generator.generate_recommendation_id(
            symbol=recommendation.get("symbol", ""),
            scenario=recommendation.get("scenario", ""),
        )
        logger.info(f"Generated missing recommendation_id: {recommendation['recommendation_id']}")

    return recommendation


# Global instance
_generator: RecommendationIDGenerator = None


def get_recommendation_id_generator() -> RecommendationIDGenerator:
    """Get or create recommendation ID generator."""
    global _generator
    if _generator is None:
        _generator = RecommendationIDGenerator()
    return _generator
