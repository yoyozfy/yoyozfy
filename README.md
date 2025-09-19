# Financial Report MCP Service

本项目实现了一个遵循 [Model Context Protocol](https://modelcontextprotocol.io) 的财报分析服务，可供各类智能体平台直接调用。

## 功能

- 🔍 **财报指标抽取**：自动识别营业收入、净利润、毛利率等关键指标，并给出置信度与原始依据。
- 🧾 **摘要生成**：基于抽取结果生成结构化总结，支持中文和英文财报文本。
- 📊 **跨期对比**：对比当前与上一期财报中的核心指标，提供变化量与增长率解释。

## 快速开始

1. 安装依赖：

   ```bash
   pip install -e .[dev]
   ```

2. 启动 MCP 服务（默认通过 stdio 与客户端通信）：

   ```bash
   financial-mcp-service
   ```

   也可以通过 Python 直接运行：

   ```bash
   python -m financial_mcp_service.server
   ```

3. 在智能体平台中按照平台要求注册该 MCP 服务的可执行命令即可。

## 可用工具

服务当前暴露以下 MCP 工具：

- `analyze_financial_report`：输入整段财报文本，返回 `FinancialReportAnalysis` 结构。
- `compare_financial_reports`：输入当前期与上一期的财报文本，返回 `ComparativeAnalysis`。

返回的 Pydantic 结构体与字段含义可参考 `financial_mcp_service/server.py`。

## 测试

运行单元测试：

```bash
pytest
```

## 许可证

本项目基于 MIT 许可证开放。
