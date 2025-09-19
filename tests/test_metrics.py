from financial_mcp_service import server


def test_extract_metrics_revenue():
    report = "公司本期营业收入达到120.5亿元，同比增长15%。净利润为23.4亿元。"
    metrics = server.extract_metrics(report)
    revenue = next(m for m in metrics if m.name == "营业收入")
    assert revenue.value is not None
    # 120.5 亿元 -> 12.05e9
    assert abs(revenue.value - 12.05e9) < 1e7


def test_build_summary_with_partial_metrics():
    report = "营业收入为3.2亿元，毛利率45%。"
    metrics = server.extract_metrics(report)
    summary = server.build_summary(metrics)
    assert "营业收入约为" in summary
    assert "毛利率约为" in summary


def test_compare_reports_growth_interpretation():
    current = "公司营业收入达到200亿元，净利润为40亿元。"
    previous = "去年同期营业收入为150亿元，净利润为35亿元。"
    result = server.compare_financial_reports(current, previous)
    assert any(m.metric == "营业收入" for m in result.metrics)
    assert "增长" in result.interpretation
