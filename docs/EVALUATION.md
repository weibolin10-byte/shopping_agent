# 中文评测体系

## 1. 评测分层

| 层级 | 数据集/机制 | 主要指标 |
| --- | --- | --- |
| 功能回归 | pytest + 离线 fake | 安全、路由、预算、数据管线是否回归 |
| 路由 | 33 条中文意图样例 | Accuracy、分层准确率、转人工 Precision/Recall |
| 检索与拒答 | 45 条中文 Golden Set | Hit@K、实体召回、MRR、拒答召回 |
| 生成质量 | 12 条真实模型子集 | Faithfulness、Answer Relevance、Context Precision/Recall |
| 多轮对话 | 8 个场景、每个 4 轮 | 错误、重复追问、性别泄漏 |
| 消融实验 | dense / sparse / hybrid | Hit@8、实体召回、MRR |
| 成本 | 自底向上成本模型 | 单轮、单会话、AI/人工成本比 |

## 2. 当前已提交结果

- 中文路由集：确定性规则、qwen-turbo、qwen-plus 均为 33/33；qwen-turbo 的裁决成本约为 qwen-plus 的 1/2.9。
- RAGAS 子集：Faithfulness 0.917，Answer Relevance 0.831，Context Precision 0.910，Context Recall 0.222。
- 混合检索消融：Hit@8 0.885，实体召回 0.744，MRR 0.659（n=26）。
- 多轮对话：8 个场景，0 错误、0 性别泄漏。
- 中文方案估算：每轮约 $0.000682，每个 8 轮会话约 $0.0055。

原始报告保存在 `domains/china_ecommerce/eval/reports/`，文档中的数字应从报告读取，不手工创造结果。

## 3. 结果解读与局限

`45/45` 表示当前通过标准下能回答或正确拒答，不代表检索完美。基础报告中的实体 Hit@K、实体召回和 RAGAS Context Recall 仍有提升空间。33 条路由集也偏小，尚不能代表线上口语、歧义、错别字和对抗输入的完整分布。

上线前应扩充：真实流量回放、长尾投诉、混合意图、第三方 PII、Prompt Injection、商品缺货和知识过期样本，并把关键安全指标设置为不可回退门槛。
