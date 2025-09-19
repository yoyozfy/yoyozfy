"""Financial report analysis MCP service package."""

from .server import (
    ComparativeAnalysis,
    ComparativeMetric,
    FinancialReportAnalysis,
    NarrativeInsight,
    NumericMetric,
    compare_financial_reports,
    extract_metrics,
    run,
    server,
)

__all__ = [
    "ComparativeAnalysis",
    "ComparativeMetric",
    "FinancialReportAnalysis",
    "NarrativeInsight",
    "NumericMetric",
    "compare_financial_reports",
    "extract_metrics",
    "run",
    "server",
]
