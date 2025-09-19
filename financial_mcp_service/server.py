"""Financial report analysis MCP service built with the Model Context Protocol."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field


@dataclass
class MetricPattern:
    """Configuration for extracting a metric from free-form text."""

    name: str
    keywords: tuple[str, ...]
    preferred_unit: str


CHINESE_UNIT_SCALE = {
    "亿": 1e8,
    "亿元": 1e8,
    "万亿": 1e12,
    "万": 1e4,
    "万元": 1e4,
    "千": 1e3,
    "百": 1e2,
}

ENGLISH_UNIT_SCALE = {
    "billion": 1e9,
    "bn": 1e9,
    "million": 1e6,
    "m": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}

DEFAULT_UNIT = "人民币元"


class NumericMetric(BaseModel):
    """Structured representation of a numeric financial figure."""

    name: str = Field(description="指标名称，例如营业收入、净利润")
    value: Optional[float] = Field(
        default=None,
        description="换算成基础货币单位后的数值，默认单位为人民币元",
    )
    unit: str = Field(default=DEFAULT_UNIT, description="数值对应的货币或比例单位")
    raw_text: Optional[str] = Field(
        default=None,
        description="用于推断该指标的文本片段，便于进一步审计",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0-1 之间的置信度，反映正则匹配的可靠程度",
    )


class NarrativeInsight(BaseModel):
    """Qualitative observation extracted from the report text."""

    topic: str
    detail: str


class FinancialReportAnalysis(BaseModel):
    """分析结果的标准结构。"""

    summary: str = Field(description="对财报的简要总结")
    metrics: List[NumericMetric] = Field(description="抽取到的核心财务指标列表")
    highlights: List[NarrativeInsight] = Field(
        default_factory=list, description="财报亮点列表"
    )
    risks: List[NarrativeInsight] = Field(
        default_factory=list, description="潜在风险或需要关注的事项"
    )


class ComparativeMetric(BaseModel):
    """用于跨期对比的结构化数据。"""

    metric: str
    current_value: Optional[float]
    previous_value: Optional[float]
    unit: str = DEFAULT_UNIT
    change: Optional[float] = Field(
        default=None,
        description="绝对变化量，单位与值一致",
    )
    growth_rate: Optional[float] = Field(
        default=None,
        description="增长率，使用小数形式（0.15 表示 15%）",
    )


class ComparativeAnalysis(BaseModel):
    """跨期对比的综合输出。"""

    focus: str
    metrics: List[ComparativeMetric]
    interpretation: str


METRIC_PATTERNS: tuple[MetricPattern, ...] = (
    MetricPattern("营业收入", ("营业收入", "总收入", "Revenue"), DEFAULT_UNIT),
    MetricPattern("净利润", ("净利润", "净收益", "Net profit", "Net income"), DEFAULT_UNIT),
    MetricPattern(
        "扣非净利润",
        ("扣非净利润", "扣除非经常性损益后的净利润"),
        DEFAULT_UNIT,
    ),
    MetricPattern("毛利率", ("毛利率", "Gross margin"), "百分比"),
    MetricPattern("净利率", ("净利率", "Net margin"), "百分比"),
    MetricPattern("基本每股收益", ("基本每股收益", "EPS"), "人民币元/股"),
)


def _normalize_number(text: str) -> float | None:
    """将包含逗号的数值字符串转换为浮点数。"""

    try:
        cleaned = text.replace(",", "").replace(" ", "")
        return float(cleaned)
    except ValueError:
        return None


def _detect_unit(text: str) -> tuple[float, str]:
    """从匹配文本中推断单位及换算比例。"""

    lowered = text.lower()
    for unit, scale in CHINESE_UNIT_SCALE.items():
        if unit in text:
            return scale, f"人民币{unit}"
    for unit, scale in ENGLISH_UNIT_SCALE.items():
        if unit in lowered:
            return scale, unit
    if "%" in text or "％" in text:
        return 0.01, "百分比"
    return 1.0, DEFAULT_UNIT


def _extract_candidates(report: str, keywords: Iterable[str]) -> list[re.Match[str]]:
    pattern = (
        r"(?P<keyword>{keywords})"
        r"(?P<context>[^\d\n]{{0,40}})"
        r"(?P<number>[\-\d,.]+)"
        r"(?P<unit>[万千百亿亿元万元万亿billionbnmillionmk千百\%％]*)"
    ).format(keywords="|".join(re.escape(k) for k in keywords))
    return list(re.finditer(pattern, report, flags=re.IGNORECASE))


def _build_metric(name: str, match: re.Match[str]) -> NumericMetric:
    number_text = match.group("number")
    raw_unit_text = match.group("unit") or ""
    scale, unit = _detect_unit(raw_unit_text)
    value = _normalize_number(number_text)
    if value is None:
        return NumericMetric(
            name=name,
            unit=unit,
            raw_text=match.group(0).strip(),
            confidence=0.3,
        )

    if unit == "百分比":
        normalized = value * 0.01 if value > 1 else value
    else:
        normalized = value * scale
    confidence = 0.6 + min(len(number_text) / 20, 0.3)
    return NumericMetric(
        name=name,
        value=normalized,
        unit=unit,
        raw_text=match.group(0).strip(),
        confidence=min(confidence, 0.95),
    )


def extract_metrics(report: str) -> list[NumericMetric]:
    metrics: list[NumericMetric] = []
    for metric in METRIC_PATTERNS:
        candidates = _extract_candidates(report, metric.keywords)
        if not candidates:
            metrics.append(
                NumericMetric(
                    name=metric.name,
                    unit=metric.preferred_unit,
                    confidence=0.0,
                )
            )
            continue
        best = max(candidates, key=lambda m: len(m.group(0)))
        metrics.append(_build_metric(metric.name, best))
    return metrics


def _format_currency(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "未知"
    magnitude = abs(value)
    if magnitude >= 1e12:
        return f"{value / 1e12:.2f}万亿元"
    if magnitude >= 1e8:
        return f"{value / 1e8:.2f}亿元"
    if magnitude >= 1e6:
        return f"{value / 1e6:.2f}百万元"
    if magnitude >= 1e4:
        return f"{value / 1e4:.2f}万元"
    return f"{value:.2f}元"


def _metric_by_name(metrics: Iterable[NumericMetric], name: str) -> NumericMetric | None:
    for metric in metrics:
        if metric.name == name:
            return metric
    return None


def build_summary(metrics: list[NumericMetric]) -> str:
    revenue = _metric_by_name(metrics, "营业收入")
    net_profit = _metric_by_name(metrics, "净利润")
    gross_margin = _metric_by_name(metrics, "毛利率")
    parts: list[str] = []
    if revenue and revenue.value is not None:
        parts.append(f"本期营业收入约为{_format_currency(revenue.value)}")
    if net_profit and net_profit.value is not None:
        parts.append(f"净利润约{_format_currency(net_profit.value)}")
    if gross_margin and gross_margin.value is not None:
        margin = gross_margin.value * 100 if gross_margin.value <= 1 else gross_margin.value
        parts.append(f"毛利率约为{margin:.2f}%")
    if not parts:
        return "未能从文本中识别出明确的核心财务指标，请提供更完整的财报内容。"
    return "，".join(parts) + "。"


def extract_highlights(report: str) -> list[NarrativeInsight]:
    highlights: list[NarrativeInsight] = []
    for keyword in ("增长", "提升", "创新", "突破", "创纪录", "同比增长"):
        match = re.search(rf"(.{{0,30}}{keyword}.{{0,30}})", report)
        if match:
            highlights.append(
                NarrativeInsight(topic=keyword, detail=match.group(1).strip())
            )
    return highlights


def extract_risks(report: str) -> list[NarrativeInsight]:
    risks: list[NarrativeInsight] = []
    for keyword in ("风险", "压力", "下降", "减弱", "亏损", "下滑", "挑战"):
        match = re.search(rf"(.{{0,30}}{keyword}.{{0,30}})", report)
        if match:
            risks.append(
                NarrativeInsight(topic=keyword, detail=match.group(1).strip())
            )
    return risks


def compare_metric(
    metric_name: str, current: NumericMetric | None, previous: NumericMetric | None
) -> ComparativeMetric:
    current_value = current.value if current else None
    previous_value = previous.value if previous else None
    change = None
    growth = None
    if (
        current_value is not None
        and previous_value is not None
        and current.unit == previous.unit
        and current.unit != "百分比"
    ):
        change = current_value - previous_value
        if previous_value != 0:
            growth = change / previous_value
    elif (
        current_value is not None
        and previous_value is not None
        and current.unit == previous.unit == "百分比"
    ):
        change = current_value - previous_value
    return ComparativeMetric(
        metric=metric_name,
        current_value=current_value,
        previous_value=previous_value,
        unit=current.unit if current else (previous.unit if previous else DEFAULT_UNIT),
        change=change,
        growth_rate=growth,
    )


def interpret_comparison(metrics: list[ComparativeMetric]) -> str:
    insights: list[str] = []
    for metric in metrics:
        if metric.current_value is None or metric.previous_value is None:
            continue
        if metric.unit == "百分比":
            change = metric.change or 0.0
            if change > 0:
                insights.append(f"{metric.metric}提升了{change * 100:.2f}个百分点。")
            elif change < 0:
                insights.append(f"{metric.metric}下降了{abs(change) * 100:.2f}个百分点。")
            continue
        if metric.growth_rate is None:
            continue
        if metric.growth_rate > 0:
            insights.append(
                f"{metric.metric}同比增长{metric.growth_rate * 100:.2f}%，增加了{_format_currency(metric.change)}。"
            )
        elif metric.growth_rate < 0:
            insights.append(
                f"{metric.metric}同比下降{abs(metric.growth_rate) * 100:.2f}%，减少了{_format_currency(metric.change)}。"
            )
    return "".join(insights) if insights else "缺乏足够数据进行跨期趋势解读。"


server = FastMCP(
    name="financial-report-analyst",
    instructions=(
        "提供中文和英文财报文本的结构化分析能力，支持核心指标提取、亮点与风险归纳以及跨期对比。"
    ),
)


@server.tool(title="财报指标抽取与总结", description="从原始财报文本中提取关键财务指标并生成摘要")
def analyze_financial_report(
    report_text: str,
    ctx: Context | None = None,
) -> FinancialReportAnalysis:
    if ctx:
        ctx.info("开始解析财报指标")
    metrics = extract_metrics(report_text)
    highlights = extract_highlights(report_text)
    risks = extract_risks(report_text)
    summary = build_summary(metrics)
    if ctx:
        ctx.info("财报解析完成")
    return FinancialReportAnalysis(
        summary=summary,
        metrics=metrics,
        highlights=highlights,
        risks=risks,
    )


@server.tool(title="财报跨期对比分析", description="比较当前与上一期财报的核心指标变化")
def compare_financial_reports(
    current_report: str,
    previous_report: str,
    focus_metric: str = "营业收入",
    ctx: Context | None = None,
) -> ComparativeAnalysis:
    if ctx:
        ctx.info("抽取当前财报指标")
    current_metrics = extract_metrics(current_report)
    previous_metrics = extract_metrics(previous_report)
    metric_map = {metric.name: metric for metric in current_metrics}
    prev_metric_map = {metric.name: metric for metric in previous_metrics}

    metrics_to_compare = [focus_metric, "净利润", "毛利率"]
    comparative: list[ComparativeMetric] = []
    for name in metrics_to_compare:
        comparative.append(
            compare_metric(name, metric_map.get(name), prev_metric_map.get(name))
        )
    interpretation = interpret_comparison(comparative)
    if ctx:
        ctx.info("跨期对比完成")
    return ComparativeAnalysis(
        focus=focus_metric,
        metrics=comparative,
        interpretation=interpretation,
    )


def run() -> None:
    """Start the MCP server using stdio transport."""
    server.run()


if __name__ == "__main__":
    run()
