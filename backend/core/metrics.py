"""Prometheus metrics for observability (request count, latency, error rate)."""

import time
from enum import Enum
from typing import Dict, Optional


class MetricType(str, Enum):
    """Prometheus metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricsCollector:
    """In-memory metrics collector (can be exported to Prometheus).

    For production, integrate with prometheus-client library.
    """

    def __init__(self) -> None:
        """Initialize metrics store."""
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histogram_buckets: Dict[str, Dict[str, int]] = {}
        self.request_count = 0
        self.error_count = 0
        self.latency_samples = []

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name (e.g., 'requests_total')
            value: Amount to increment (default: 1)
        """
        if name not in self.counters:
            self.counters[name] = 0
        self.counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: Metric name (e.g., 'active_connections')
            value: Gauge value
        """
        self.gauges[name] = value

    def record_latency(
        self,
        name: str,
        latency_ms: float,
        buckets: Optional[list] = None,
    ) -> None:
        """Record latency histogram for percentile calculation.

        Args:
            name: Metric name (e.g., 'request_latency_ms')
            latency_ms: Latency in milliseconds
            buckets: Optional bucket boundaries for histogram
        """
        if name not in self.histogram_buckets:
            self.histogram_buckets[name] = {
                "total": 0,
                "sum": 0.0,
                "count": 0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        self.histogram_buckets[name]["total"] += 1
        self.histogram_buckets[name]["sum"] += latency_ms
        self.histogram_buckets[name]["count"] += 1
        self.latency_samples.append(latency_ms)

        # Approximate percentiles (simple: sort and pick indices)
        if self.latency_samples:
            sorted_samples = sorted(self.latency_samples)
            n = len(sorted_samples)
            self.histogram_buckets[name]["p50"] = sorted_samples[int(n * 0.50)]
            self.histogram_buckets[name]["p95"] = sorted_samples[int(n * 0.95)]
            self.histogram_buckets[name]["p99"] = sorted_samples[int(n * 0.99)]

    def get_metrics(self) -> Dict[str, any]:
        """Get all current metrics.

        Returns:
            Dictionary of all metrics (counters, gauges, histograms)
        """
        return {
            "counters": self.counters,
            "gauges": self.gauges,
            "histograms": self.histogram_buckets,
            "request_count": self.request_count,
            "error_count": self.error_count,
        }

    def get_summary(self) -> Dict[str, any]:
        """Get summary metrics for dashboard.

        Returns:
            Summary: error rate, p50/p95/p99 latency, etc.
        """
        error_rate = (
            (self.error_count / self.request_count * 100)
            if self.request_count > 0
            else 0.0
        )

        avg_latency = (
            (self.histogram_buckets.get("request_latency_ms", {}).get("sum", 0.0)
             / self.histogram_buckets.get("request_latency_ms", {}).get("count", 1))
            if self.request_count > 0
            else 0.0
        )

        return {
            "requests_total": self.request_count,
            "errors_total": self.error_count,
            "error_rate_percent": error_rate,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": self.histogram_buckets.get("request_latency_ms", {}).get("p50", 0.0),
            "p95_latency_ms": self.histogram_buckets.get("request_latency_ms", {}).get("p95", 0.0),
            "p99_latency_ms": self.histogram_buckets.get("request_latency_ms", {}).get("p99", 0.0),
        }


# Global metrics instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get global metrics collector instance.

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics() -> None:
    """Reset all metrics (for testing)."""
    global _metrics_collector
    _metrics_collector = MetricsCollector()
