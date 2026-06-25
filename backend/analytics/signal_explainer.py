"""
Phase 313: Signal Explainer - Explain composite signal components.

Breaks down signal score into GARP + Technical components, shows drivers/detractors.
Adapted for crypto-daytrading autonomous trader.
"""
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SignalExplainer:
    """Explain composite signal components for autonomous crypto trading."""

    def __init__(self) -> None:
        self.components: Dict[str, Dict[str, Any]] = {
            "garp": {
                "weight": 0.60,
                "label": "GARP Quality Score",
                "metrics": [
                    "Trend above MA",
                    "Not overbought",
                    "Volatility health",
                    "Volume",
                ],
                "max_score": 100,
            },
            "technical": {
                "weight": 0.40,
                "label": "Technical Analysis",
                "metrics": ["RSI momentum", "MACD trend", "Bollinger position"],
                "max_score": 100,
            },
        }

    def explain_score(
        self,
        symbol: str,
        total_score: float,
        component_scores: Dict[str, float],
        asset_class: str = "crypto",
    ) -> Dict[str, Any]:
        """
        Explain a composite signal score.

        Parameters:
        -----------
        symbol : str
            Trading symbol (BTC, EQ_AAPL, etc.)
        total_score : float
            Final blended signal score (0-100)
        component_scores : dict
            {"garp": 70.0, "technical": 50.0, ...}
        asset_class : str
            "crypto" or "stock"
        """

        breakdown: List[Dict[str, Any]] = []
        for component_name, score in component_scores.items():
            if component_name not in self.components:
                continue

            comp_info = self.components[component_name]
            max_score = comp_info["max_score"]
            weight = comp_info["weight"]
            label = comp_info["label"]

            contribution = score * weight
            pct_of_total = (contribution / total_score * 100) if total_score > 0 else 0

            breakdown.append(
                {
                    "component": component_name,
                    "label": label,
                    "score": round(score, 1),
                    "max": max_score,
                    "weight": f"{weight*100:.0f}%",
                    "contribution": round(contribution, 1),
                    "pct_of_total": round(pct_of_total, 1),
                    "status": "strong" if score > max_score * 0.7 else "weak",
                    "metrics": comp_info["metrics"],
                }
            )

        # Determine overall grade (adjusted for 55.0 entry threshold)
        if total_score >= 75:
            grade: str = "Strong Buy"
            emoji: str = "🚀"
        elif total_score >= 60:
            grade = "Buy"
            emoji = "⭐⭐"
        elif total_score >= 55:
            grade = "Enter"
            emoji = "⭐"
        elif total_score >= 40:
            grade = "Watch"
            emoji = "👁️"
        else:
            grade = "Avoid"
            emoji = "❌"

        # Top drivers and detractors
        sorted_components: List[Dict[str, Any]] = sorted(
            breakdown, key=lambda x: x["contribution"], reverse=True
        )
        drivers: List[Dict[str, Any]] = sorted_components[:2]
        detractors: List[Dict[str, Any]] = (
            sorted_components[-1:] if len(sorted_components) > 1 else []
        )

        return {
            "symbol": symbol,
            "asset_class": asset_class,
            "score": round(total_score, 1),
            "grade": grade,
            "emoji": emoji,
            "breakdown": breakdown,
            "top_drivers": drivers,
            "detractors": detractors,
            "reasoning": self._build_reasoning(grade, drivers, detractors),
        }

    def _build_reasoning(
        self,
        grade: str,
        drivers: List[Dict[str, Any]],
        detractors: List[Dict[str, Any]],
    ) -> str:
        """Build natural language explanation of signal."""
        if not drivers:
            return "Insufficient data for analysis"

        main_driver = drivers[0]["label"]
        main_score = drivers[0]["score"]

        reason = f"{grade}: {main_driver} is strong ({main_score:.0f}/100)"

        if detractors:
            weak_comp = detractors[0]["label"]
            weak_score = detractors[0]["score"]
            reason += f" but {weak_comp} is weak ({weak_score:.0f}/100)"

        return reason


# Global instance
_explainer: Optional[SignalExplainer] = None


def get_signal_explainer() -> SignalExplainer:
    """Get or create signal explainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = SignalExplainer()
    return _explainer
