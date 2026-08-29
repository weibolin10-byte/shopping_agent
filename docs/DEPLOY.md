# 运行与部署

## 本地轻量模式

1. 复制 `.env.example` 为 `.env`，配置 DeepSeek 和通义千问密钥。
2. 安装依赖：`uv sync --extra dev`。
3. 生成中文数据：`uv run python domains/china_ecommerce/tools/generate_all.py`。
4. 构建内存索引：`uv run python scripts/seed_memory.py`。
5. 启动 API：`make serve`。
6. 在 `web/` 下执行 `npm ci && npm run dev`。

## 完整基础设施

`docker compose` 提供 Qdrant、Neo4j 和 MLflow。依次执行 `make up`、`make lakehouse`、`make dbt-build`、`make ingest` 和 `make graph-load`。

生产环境需要替换 JWT 与管理员密码，限制允许来源，使用托管存储并为 Trace、认证库和审核队列配置持久化。模型与数据库凭据只能通过环境变量或密钥管理系统注入。

## 验证命令

- `make check`：代码规范、测试、领域泄漏检查和离线门禁。
- `make eval`：中文检索与拒答评测。
- `make routing-eval`：中文路由模型消融。
- `make conversation-eval`：中文多轮评测。
- `make full-eval`：需要真实模型的综合评测。
- `make cost`：重新生成中文成本模型。
