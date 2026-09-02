# 智能电商 AI 助手 — Agentic RAG 平台

> 基于 Agentic RAG 架构的中文电商智能客服平台，使用 DeepSeek + 通义千问国产大模型，覆盖商品推荐、订单查询、退换货政策、尺码咨询、投诉处理等全链路购物场景。

[![](https://img.shields.io/badge/LLM-DeepSeek-blue)](https://www.deepseek.com)
[![](https://img.shields.io/badge/Embedding-通义千问-orange)](https://dashscope.aliyun.com)
[![](https://img.shields.io/badge/Python-3.12-green)](https://www.python.org)
[![](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![](https://img.shields.io/badge/Tests-CI%20verified-brightgreen)](#基线评测结果)

---

## 项目背景

本项目是一套面向国内购物场景的**国产大模型驱动中文电商解决方案**，以可控路由、证据检索、安全回答和持续评测为核心。

项目围绕中文语言特性和国内电商业务场景进行系统设计：支持 CJK 分词、中文意图路由、投诉情绪识别、偏见控制和人民币价格理解，并通过全量评测验证关键能力。

**MVP 状态：已完成。** 当前版本包含可运行的 Web 界面、API、路由、分 Lane 检索、
多轮状态、订单隔离、安全校验与离线评测。未接入的大规模线上基础设施不属于本次 MVP 范围。

## 核心能力

| 用户说 | 系统行为 |
| --- | --- |
| "帮我推荐一双日常训练跑鞋，预算 800 左右" | 从商品目录筛选，给出带理由的推荐，尊重预算 |
| "我的订单到哪了？" | 登录态解锁用户订单信息，仅返回本人数据 |
| "Nike Pegasus 和 Adidas Ultraboost 哪个好？" | 跨品牌对比，从评测和商品知识中提取依据 |
| "Lululemon 的瑜伽裤尺码偏小吗？" | 基于真实用户评论给出有引用的回答 |
| "退换货政策是什么？" | 基于知识库回答，不编造政策 |
| "再不到货我就退货了！" | 投诉通道：先共情，再给出具体解决方案 |
| "转人工客服" | 收集信息后生成工单，转接人工 |

## 技术架构

```
用户（Web 前端）
    │
    ▼
FastAPI 后端（SSE 流式 / JWT 认证 / 限流）
    │
    ▼
Omni 路由器 ── L0 正则规则（$0，覆盖大部分请求）
    │           L1 意图守卫（stylist / care / complaint / answers）
    │           L2 小模型兜底（qwen-turbo，仅在模糊时调用）
    ▼
LanePolicy → RetrievalPlan → 统一回答管线
    │
    ├── 查询感知检索：结构化 / Dense / Sparse / Hybrid / OrderStore
    ├── 知识图谱：Product ↔ Supplier ↔ Store
    ├── 引用校验：每条回答必须有检索来源支撑
    └── 安全门：租户与用户数据隔离 / PII 防护 / 中英文 Prompt 注入拦截
    │
    ▼
流式回答（SSE）或主动拒答或转人工
```

**设计原则：**
- **确定性优先**：正则路由覆盖 100% 测试用例，零模型调用成本
- **一条管线**：所有路由通道共用同一个安全门，不存在薄弱通道
- **能拒答不编造**：检索证据不足时明确告知"信息不足"，不猜测
- **成本可控**：普通请求最多两次 LLM，复杂工作流最多四次；全链路统一计量
- **订单隔离**：订单由私有 OrderStore 精确查询，不进入公共向量索引
- **服务端记忆**：`session_id` 绑定登录用户，会话状态使用版本控制防止并发覆盖

## 当前正式评测结果

唯一正式入口为 `domains/china_ecommerce/eval/reports/current.json`。下面的表格由该报告自动
生成，样本量较小，只代表当前离线测试集，不代表线上业务效果。

<!-- EVAL_METRICS:START -->
| 评测维度 | 当前成绩 | 口径 |
| --- | --- | --- |
| 意图路由准确率 | **100.0%** | 33 条中文路由样本；含 7 次小模型裁决 |
| RAGAS 忠实度 | **97.1%** | 30 条真实生成样本（regression 集）；有效评分 28/30 |
| RAGAS 答案相关性 | **82.6%** | 独立 Judge + Embedding；有效评分 28/30 |
| RAGAS 上下文精度 | **82.4%** | 检索块有效性；有效评分 25/30 |
| RAGAS 上下文召回 | **96.6%** | 参考答案事实覆盖；有效评分 28/30 |
| 确定性事实召回 | **99.3%** | 价格、商品名等机器可核验字段；n=30 |
| Dense 检索 | **Hit@8 88.5% / MRR 0.667** | n=26 |
| Hybrid 检索 | **Hit@8 88.5% / MRR 0.632** | n=26；不预设优于 Dense |
<!-- EVAL_METRICS:END -->

路由、生成和检索的完整逐项结果、模型版本、数据哈希、知识版本、随机种子均记录在正式报告中。

### 历史成本模型（估算，不代表当前模型账单）

以下是早期基于 DeepSeek-Chat + 确定性路由 + 千问 Embedding 的假设性测算，仅保留作
容量规划示例；当前使用 deepseek-v4-flash，不能沿用这些单价作为真实成本。

| 环节 | 每轮成本（USD） |
| --- | --- |
| 路由（确定性正则） | $0.000000 |
| Embedding（千问 v3） | $0.000002 |
| Reranker | $0.000000 |
| 生成（DeepSeek-Chat） | $0.000680 |
| **合计** | **$0.000682** |

**以下是成本假设，不是线上账单**（按 8 轮会话、人工 4 分钟/单、¥30/小时计）：

| | 单轮成本 | 单会话成本 |
| --- | --- | --- |
| AI 助手 | $0.000682 | $0.0055 |
| 人工客服 | $0.278 | $2.224 |
| **倍率** | **人工贵 408 倍** | **人工贵 408 倍** |

## 中文适配关键工作

### 1. 国产大模型接入
- 开发 `openai_compat` 适配器，支持任意 OpenAI 兼容 API
- 大模型：deepseek-v4-flash（关闭思考模式用于低延迟客服回答）
- 小模型：qwen-turbo（路由 + 草稿）
- Embedding：通义千问 text-embedding-v3（1024 维）

### 2. CJK 中文分词
- 对英文空格分词无法直接覆盖的中文文本增加专用处理
- 实现 CJK Bigram 分词器，中文字符两两组合
- 混合检索（稠密向量 + 稀疏关键词）在中文场景下达到 88.5% 命中率

### 3. 中文意图路由
- 为中文购物表达建立确定性规则，模糊请求再交给小模型语义分类
- 覆盖购物推荐、订单查询、退换货、尺码咨询、投诉 5 类意图
- 从最初 30.3% 准确率迭代至 100%

### 4. 投诉情绪识别
- 中文表达投诉的方式远多于英文（"再不发货就退"、"什么垃圾"等）
- 三轮正则迭代 + complaint lane 兜底机制
- 实现 CJK 语言检测，拒答消息自动切换中文

### 5. 性别偏见修复
- 评测发现低价区间缺少女款产品，导致推荐时出现性别偏移
- 补充 9 款女性低价产品（P091-P099），重跑评测后 gender_leaks = 0
- **修复数据而非修改 prompt**——产品目录缺女款是真实数据缺口

### 6. 中文前端
- 21 个中文 React 交互组件
- 商品名、价格（人民币）、尺码、客服话术全部适配国内电商习惯
- 支持流式对话、商品目录浏览、购物车、管理后台

## 快速开始

### 环境要求
- Python 3.12（使用 [uv](https://docs.astral.sh/uv/) 管理）
- Node.js 18+
- DeepSeek API Key
- 阿里云 DashScope API Key（千问）

### 1. 克隆项目

```bash
git clone git@github.com:weibolin10-byte/shopping_agent.git
cd shopping_agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入以下密钥：
# OPENAI_COMPAT_API_KEY=你的 DeepSeek API Key
# OPENAI_COMPAT_SMALL_API_KEY=你的千问 API Key
# QWEN_API_KEY=你的千问 API Key（与上面相同即可）
```

### 3. 安装依赖 & 初始化数据

```bash
# Python 依赖（uv 自动创建虚拟环境）
uv sync

# 生成中文电商领域数据
uv run python domains/china_ecommerce/tools/generate_all.py

# 构建向量索引（内存模式，无需 Docker）
uv run python scripts/seed_memory.py
```

### 4. 启动后端

```bash
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### 5. 启动前端

```bash
cd web
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run build
npm run start -- -p 3000
```

打开 http://127.0.0.1:3000 ，使用用户名 `demo`、密码 `demo12345` 登录体验。

### 6. 运行评测

```bash
# 基础检索评测（45 题）
uv run python scripts/run_eval_zh.py

# 综合评测（RAGAS + Ablation）
uv run python scripts/run_full_eval_zh.py

# 多轮对话评测（8 场景 × 4 轮）
uv run python scripts/probe_conversation_zh.py

# 路由模型消融实验（qwen-turbo vs qwen-plus）
uv run python scripts/run_routing_ablation_zh.py

# 成本模型（AI vs 人工客服）
uv run python -m mlops.cost_model_zh

# 项目全量测试
uv run pytest --tb=short
```

## 运行截图

### 登录页
![登录页](docs/screenshots/01_landing.png)

### 商品主页
![商品主页](docs/screenshots/02_store.png)

### AI 智能客服对话
![AI客服对话](docs/screenshots/09_chat.png)

## 项目文档

- [系统架构](docs/ARCHITECTURE.md)
- [评测体系](docs/EVALUATION.md)
- [运行与部署](docs/DEPLOY.md)
- [AI 产品经理面试讲解](docs/INTERVIEW_GUIDE.md)


## 项目结构

```
├── adapters/               # 大模型适配器
│   ├── openai_compat.py    # DeepSeek / 任意 OpenAI 兼容 API
│   └── qwen_embed.py       # 千问 Embedding（支持批量≤10）
├── api/                    # FastAPI 后端
│   └── app.py              # 路由、认证、SSE 流式接口
├── pipeline/               # 核心回答管线
│   └── answer.py           # 检索、引用校验、安全门、生成
├── rag/                    # 路由与编排
│   └── router.py           # Omni 路由器（确定性正则 + LLM 兜底）
├── retrieval/              # 检索层
│   └── sparse.py           # CJK Bigram 稀疏检索
├── domains/
│   └── china_ecommerce/    # 中文电商领域包
│       ├── domain.yaml     # 领域定义（商品、图谱、推荐问题）
│       ├── seed/           # 种子数据（商品、评论、订单、知识）
│       ├── eval/           # 评测集和报告
│       └── tools/          # 数据生成工具
│   └── home_ecommerce/     # 第二领域包：验证引擎、湖仓、指标与 PII 合同可复用
├── scripts/                # 评测和运维脚本
│   ├── run_routing_ablation_zh.py  # 路由大小模型消融
│   └── ...
├── mlops/                  # 成本模型与运维
│   └── cost_model_zh.py    # AI vs 人工客服成本测算
├── web/                    # Next.js 前端
│   └── app/                # 中文交互页面和组件
└── .env.example            # 环境变量模板
```

## 技术栈

| 层级 | 技术选型 |
| --- | --- |
| 大模型 | deepseek-v4-flash |
| 小模型 | 通义千问 qwen-turbo |
| Embedding | 通义千问 text-embedding-v3（1024 维） |
| 后端 | FastAPI + Uvicorn + SSE |
| 检索 | 内存向量库 + CJK Bigram 稀疏检索（轻量模式） |
| 图谱 | 内存属性图（Product / Supplier / Store） |
| 前端 | Next.js 14 + React + TypeScript |
| 评测 | RAGAS + Pytest + 自定义对话评测 |
| 依赖管理 | uv（Python）+ npm（Node） |

## 设计思考

作为 AI 产品经理视角，这个项目关注的核心问题：

1. **答得准不准** — 通过 RAGAS 四维度量化，忠实度 91.7%
2. **会不会乱答** — 引用校验 + 拒答机制，不知道就说不知道
3. **成本高不高** — 确定性路由零成本覆盖 78.8% 请求，模糊时仅调 qwen-turbo 小模型兜底；单轮对话 $0.0007，比人工客服便宜 408 倍
4. **中文好不好用** — CJK 分词、中文意图、投诉情绪、人民币价格
5. **安不安全** — PII 防护、Prompt 注入拦截、客户枚举拒绝
6. **怎么迭代** — 评测驱动开发，每次模型或逻辑变更都跑全量评测，569 个通过、1 个跳过
