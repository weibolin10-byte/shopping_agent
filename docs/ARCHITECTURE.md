# 中文智能电商 Agent 平台架构

## 1. 产品目标

平台面向中文运动电商场景，覆盖商品推荐、商品比较、尺码与政策问答、订单查询、投诉处理和人工升级。核心原则是：确定性优先、证据驱动、统一安全门、成本可控。

## 2. 单轮请求链路

```text
Web / Telegram / MCP
        ↓
FastAPI：JWT、分布式限流、服务端会话状态、SSE 流式输出
        ↓
动态 Orchestrator
  L0 明确转人工
  L1 确定性意图规则
  L2 qwen-turbo 模糊裁决
        ↓
LanePolicy → RetrievalPlan
  商品事实：结构化/关键词优先；导购：Hybrid + 重排
  政策：版本与时效过滤；订单：私有 OrderStore 精确查询
        ↓
统一回答管线
  Request Guard → Evidence Assembler → Response Planner
  → DeepSeek 生成 → 结构化事实/引用/冲突校验
        ↓
回答 / 拒答 / 人工工单
        ↓
Trace、MLflow、漂移监控、评测与反馈闭环
```

## 3. Agent 编排

路由通道包括 `stylist`、`care`、`complaint`、`answers` 和 `escalation`。每个通道在领域包中声明权限、必填槽位、允许和优先数据源、检索模式、TopK、证据阈值及失败动作。它们不是彼此独立的开放式 Agent，仍共用一套安全与验证管线。

多意图输入会被拆成最多三个子任务，分别处理后再合并。普通请求最多两次 LLM 调用，困难链路最多四次；`TurnBudget` 同时统计生成、Embedding、重排和工具操作。LangGraph 由系统在证据冲突或长尾弱路由时动态启用，普通请求继续走低延迟快速路径。

## 4. 知识与数据

- 查询感知检索：按 Lane 选择结构化、Dense、Sparse、Hybrid 或订单服务，不假设 Hybrid 全面最优。
- 知识图谱：Product、Supplier、Store、Review 及受限关系遍历。
- 指标层：模型只填写指标参数，系统执行 `metrics.yaml` 中审核过的只读 SQL。
- 湖仓：结构化数据经过 Bronze、Silver、Gold；非结构化文档经过切分、上下文化、向量化和索引。
- 订单边界：订单不再进入公共向量摄入清单；查询必须在 OrderStore 内按租户和 JWT 用户过滤。
- 证据合同：所有来源转换为 `EvidenceItem`，携带权威等级、有效期、用户/租户范围及知识版本。
- 领域包：中文人设、LanePolicy、同义词、数据清单、图谱和评测集集中管理。
- 泛化验证：`home_ecommerce` 使用同一引擎完成摄入、问答、拒答、湖仓、指标和 PII
  合同测试，不依赖中国运动电商代码。

## 5. 模型与基础设施

- 生成：DeepSeek Chat。
- 路由兜底：通义千问 qwen-turbo。
- Embedding：通义千问 text-embedding-v3。
- API：FastAPI；前端：Next.js 14；会话使用乐观版本控制。
- 向量库：Qdrant；图数据库：Neo4j；分析与指标：DuckDB + dbt。
- 生产状态：PostgreSQL 保存会话/订单，Redis 支持共享会话、限流和答案缓存；本地仍可零依赖运行。
- 观测：JSONL Trace、Langfuse、MLflow；正式评测报告携带完整运行来源信息。

所有外部服务均通过 `adapters/` 接口接入，测试使用确定性 fake，避免 CI 依赖密钥和网络。

## 6. 对外合同

- `ChatRequest.session_id` 为可选字段；缺省时服务端创建临时会话。`history` 仅为兼容上下文，
  不参与 JWT 身份和订单权限判断。
- SSE `final` 事件稳定返回 `session_id`、`trace_id`、`lane`、`action`、`citations`、
  `clarification`（如有）、`degraded` 和预算快照。
- `LanePolicy`、`RetrievalPlan`、`EvidenceItem`、`ConversationState` 是核心边界类型；外部
  存储和检索适配器不得绕过其中的租户、用户、时效和来源约束。
