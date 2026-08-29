# 中文智能电商 Agent 平台架构

## 1. 产品目标

平台面向中文运动电商场景，覆盖商品推荐、商品比较、尺码与政策问答、订单查询、投诉处理和人工升级。核心原则是：确定性优先、证据驱动、统一安全门、成本可控。

## 2. 单轮请求链路

```text
Web / Telegram / MCP
        ↓
FastAPI：JWT、限流、SSE 流式输出
        ↓
Omni Orchestrator
  L0 明确转人工
  L1 确定性意图规则
  L2 qwen-turbo 模糊裁决
        ↓
统一回答管线
  输入安全 → 身份与订单 PII → 混合检索
  → 图谱/业务指标证据 → 置信度门 → DeepSeek 生成
  → 引用 grounding 检查
        ↓
回答 / 拒答 / 人工工单
        ↓
Trace、MLflow、漂移监控、评测与反馈闭环
```

## 3. Agent 编排

路由通道包括 `stylist`、`care`、`complaint`、`answers` 和 `escalation`。它们是不同的业务角色策略，不是彼此独立的开放式 Agent。所有通道都调用 `pipeline/answer.py`，因此订单隐私、提示注入、证据门和引用检查只有一个实现。

多意图输入会被拆成最多三个子任务，分别处理后再合并。每轮共享 `TurnBudget`，限制模型调用次数、token、费用和执行时长。可选的 LangGraph corrective-RAG 只负责困难检索的重写与重试，不建立第二套安全面。

## 4. 知识与数据

- 混合检索：千问 Embedding 的稠密向量与 CJK Bigram 稀疏检索融合。
- 知识图谱：Product、Supplier、Store、Review 及受限关系遍历。
- 指标层：模型只填写指标参数，系统执行 `metrics.yaml` 中审核过的只读 SQL。
- 湖仓：结构化数据经过 Bronze、Silver、Gold；非结构化文档经过切分、上下文化、向量化和索引。
- 领域包：中文人设、同义词、数据清单、图谱和评测集集中在 `domains/china_ecommerce/`。

## 5. 模型与基础设施

- 生成：DeepSeek Chat。
- 路由兜底：通义千问 qwen-turbo。
- Embedding：通义千问 text-embedding-v3。
- API：FastAPI；前端：Next.js 14。
- 向量库：Qdrant；图数据库：Neo4j；分析与指标：DuckDB + dbt。
- 观测：JSONL Trace、Langfuse、MLflow。

所有外部服务均通过 `adapters/` 接口接入，测试使用确定性 fake，避免 CI 依赖密钥和网络。
