# 中文评测体系

## 1. 评测分层

| 层级 | 数据集/机制 | 主要指标 |
| --- | --- | --- |
| 功能回归 | pytest + 离线 fake | 安全、路由、预算、数据管线是否回归 |
| 路由 | 中文意图冻结集 | Macro-F1、各 Lane Recall、误路由率、转人工 Precision/Recall |
| 检索与拒答 | 45 条中文 Golden Set | Hit@K、实体召回、MRR、拒答召回 |
| 生成质量快速检查 | 独立 `generation_smoke.jsonl`（11 条） | Faithfulness、Answer Relevance、Context Precision/Recall、确定性事实召回 |
| 生成质量正式评测 | 已审核 regression 集；frozen 为后续增强 | 分 Lane 生成质量、拒答、事实和引用准确率 |
| 多轮对话 | 8 个场景、每个 4 轮 | 错误、重复追问、性别泄漏 |
| 消融实验 | dense / sparse / hybrid | Hit@8、实体召回、MRR |
| 成本 | 自底向上成本模型 | 单轮、单会话、AI/人工成本比 |

## 2. 正式报告与数据切分

`domains/china_ecommerce/eval/reports/current.json` 是唯一正式报告。每次运行必须记录 Git
版本、数据集 SHA-256、模型、知识版本、参数和随机种子。其他报告均为历史实验，不能作为
当前产品结论。

检索样例可以通过稳定哈希拆分，但生成评测不再从检索 Golden Set 临时抽样。生成评测使用
三份显式、分别版本化的数据：`generation_smoke.jsonl`、`generation_regression.jsonl` 和
`generation_frozen.jsonl`。开发和调参不得查看冻结集结果；发布门禁只比较
regression/frozen 与上一个正式版本。当前已完成 30 条逐条证据核对的
`generation_regression.jsonl`；`generation_frozen.jsonl` 仍未建立，因此可以形成回归基线，
但还不能声称已经完成不参与调参的冻结测试。未准备好的数据集仍会让正式脚本直接失败。

## 3. 当前正式基线

- 中文路由集：33 条样本准确率 1.000，其中 7 条调用 qwen-turbo 语义裁决。
- 公共知识 regression 集 30 条（DeepSeek 生成、qwen-plus 独立裁判）：
  Faithfulness 0.971、Answer Relevance 0.826、Context Precision 0.824、Context Recall 0.966。
- 确定性生成契约：必要事实召回率 0.993；身份、越权与禁止结论由独立安全契约验收。
- 检索消融（n=26）：Dense 与 Hybrid 的 Hit@8 均为 0.885、实体召回均为 0.756；Dense
  MRR 0.667，高于 Hybrid 的 0.632。只有关系查询中 Hybrid MRR 更高，因此关系查询保留
  Hybrid，其余已测类型默认 Dense。
- 多轮对话：8 个场景，0 错误、0 性别泄漏。
- 中文方案估算：每轮约 $0.000682，每个 8 轮会话约 $0.0055。

订单查询依赖登录身份和独立 OrderStore，不混入公共知识 RAGAS；它通过鉴权端到端与越权
测试单独验收。当前公共回归集已达到 Context Precision 0.80 门槛。独立 frozen 集、
真实长尾样本和大规模重复性试验属于后续生产化增强，不影响当前 MVP 验收。

成本数字均为假设模型，除非正式报告的 `report_kind` 明确为 `online_measured`。

### MVP 范围

当前版本以 30 条公共生成回归集、身份/多轮/安全离线契约和一份 `current.json`
正式报告作为 MVP 验收范围。独立 frozen 集、线上影子流量和大规模重复性试验属于
后续生产化增强，不作为当前 MVP 交付的前置条件。仓库保留了重复性比较工具，但不提交
本地临时实验报告。

## 4. 发布门禁

- 路由 Macro-F1 ≥ 0.90；订单与投诉 Lane Recall ≥ 0.95。
- Retrieval Recall@8 ≥ 0.75；Context Precision ≥ 0.80。
- Faithfulness ≥ 0.90；结构化事实准确率 ≥ 0.95；拒答 F1 ≥ 0.90。
- 多轮任务完成率 ≥ 0.85；重复追问率 ≤ 5%。
- 越权订单、跨租户访问和 PII 泄漏必须为 0。
- 生产化发布时，同一版本重复运行的核心指标波动应不超过 2%。

## 5. 结果解读与局限

当前 Faithfulness、Context Recall 和 Context Precision 达标不代表检索完美。Context Precision
仅高于门槛；33 条路由集和 30 条公共生成回归集仍不能代表线上口语、歧义、
错别字和对抗输入的完整分布。若继续生产化，可扩展为 100 条不参与调参的 frozen 样本；每条必须
包含期望动作、参考答案、结构化事实、答案关键词/禁用结论、证据目标和场景标签。

第一批 30 条公共样本已逐条核对 `source_refs`，在 `generation_regression.jsonl`
中全部标记为 `approved`。原始 `generation_candidates.jsonl` 仍保留 `pending` 状态作为候选记录；
订单与投诉样本继续由身份化执行器单独验收，不进入公共 RAGAS 裁判链路。

身份化评测由 `evaluation/identity_eval.py` 执行，样本保存在
`generation_identity_candidates.jsonl`。执行器把经过验证的用户和租户传入 LanePolicy，
通过独立 `OrderStore` 查询，并检查最终 Lane、动作、必要事实和 `must_not_disclose` 隐私
字段。匿名、跨用户和跨租户请求必须没有订单引用且不能泄露订单状态、物流单号或用户信息。
这套样本不参与公共 RAGAS，因为把私人订单上下文交给通用评审链路会扩大敏感数据暴露面。

多轮候选集 `generation_multiturn_candidates.json` 包含 5 个四轮场景，共 20 个 Turn。
`evaluation/scenario_eval.py` 在同一个 `ConversationState` 和服务端历史中依次执行每轮，
统计 Lane/动作准确率、隐私安全率和不必要的重复追问率。身份校验属于必须重复的安全门槛，
场景可用 `allow_repeated_clarification` 明确豁免，避免把正确的持续拒绝误记为体验缺陷。

韧性与安全候选集 `generation_resilience_candidates.jsonl` 增加 18 条可执行夹具：4 条检索
上下文注入、4 条用户输入攻击、4 条权威证据冲突、4 条依赖故障和 2 条伪造历史。对应的
`evaluation/resilience_eval.py` 不调用真实模型，直接验证清洗、前置拒绝、冲突决策、降级/
fallback 和“只信任用户历史”的身份边界。第一版候选库存因此达到 80 个评测单元：公共
30、身份订单 12、多轮 Turn 20、韧性安全 18；测试会锁定这个分布，避免样本被意外删除。

上线前应扩充：真实流量回放、长尾投诉、混合意图、第三方 PII、Prompt Injection、商品缺货和知识过期样本，并把关键安全指标设置为不可回退门槛。
