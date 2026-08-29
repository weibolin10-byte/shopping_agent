"use client";

import { useEffect, useState } from "react";

import { Hint } from "../Hint";
import { AdminNav } from "../nav";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Domain = {
  domain: string;
  ontology: { entity_types: string[]; edges: { type: string; from: string; to: string }[] };
  metrics: { name: string; grain: string | null; dimensions: string[]; params: string[] }[];
  lineage: { medallion: { role: string; layers: string[]; pii_columns: string[]; metrics: string[] }[] };
  mlflow_url: string | null;
  langfuse_url: string | null;
};

type Gap = { question: string; count: number; lang?: string };

export default function InsightsPage() {
  const [mounted, setMounted] = useState(false);
  const [domain, setDomain] = useState<Domain | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    const token = localStorage.getItem("shopping_agent_admin_token");
    if (!token) {
      setError("请先在 /admin 页面登录。");
      return;
    }
    const headers = { Authorization: `Bearer ${token}` };
    fetch(`${API_BASE}/api/admin/domain`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setDomain)
      .catch(() => setError("无法加载领域视图（您是否是管理员？）。"));
    fetch(`${API_BASE}/api/admin/gaps`, { headers })
      .then((r) => (r.ok ? r.json() : { gaps: [] }))
      .then((d) => setGaps(d.gaps));
  }, []);

  if (!mounted) return null;
  if (error) return <main className="admin"><p className="error">{error}</p></main>;
  if (!domain) return <main className="admin"><p>正在加载...</p></main>;

  return (
    <main className="admin">
      <AdminNav />
      <h1>领域：{domain.domain}</h1>

      {(domain.mlflow_url || domain.langfuse_url) && (
        <div className="row">
          <span className="meta">可观测性：</span>
          <Hint text="业务：证明系统被监控，不是黑盒；每条回答和模型运行都可追踪。技术：Langfuse 捕获每轮 span（检索、重排、生成）；MLflow 记录评估运行和模型版本。" />
          {domain.langfuse_url && (
            <a className="ext" href={domain.langfuse_url} target="_blank" rel="noreferrer">
              Langfuse 追踪
            </a>
          )}
          {domain.mlflow_url && (
            <a className="ext" href={domain.mlflow_url} target="_blank" rel="noreferrer">
              MLflow 运行
            </a>
          )}
        </div>
      )}

      <h2>知识缺口
        <Hint text="业务：助手尚不能满足的真实购物者需求，按频次排名；是下一步最值得添加的内容。技术：触发拒答或低 grounding 轮次的问题，从实时追踪中去重计数。" />
      </h2>
      <p className="ax-intro">
        购物者真实提出但助手未能很好回答的问题，按频次从高到低排列。这是下一步要教它的工作清单：
        添加政策或商品文档，缺口就会缩小。这些不是测试查询，而是真实需求。
      </p>
      {gaps.length === 0 ? (
        <p>暂无未回答的问题。</p>
      ) : (
        <ul className="gap-list">
          {gaps.map((g) => (
            <li key={g.question}>
              <span className="gap-count">{g.count}×</span>
              <span className="gap-q">{g.question}</span>
              {g.lang && g.lang !== "zh" && <span className="gap-lang">{g.lang}</span>}
            </li>
          ))}
        </ul>
      )}

      <h2>本体
        <Hint text="业务：该领域的词汇表——商品、订单、政策及其关系；替换它即可为新行业重新皮肤整个平台。技术：domain.yaml 中声明的实体类型和类型化边，塑造知识图谱和检索。" />
      </h2>
      <p className="meta">实体：{domain.ontology.entity_types.join("、")}</p>
      <ul>
        {domain.ontology.edges.map((e) => (
          <li key={e.type}>
            {e.from} <em>{e.type}</em> {e.to}
          </li>
        ))}
      </ul>

      <h2>治理指标
        <Hint text="业务：所有人都同意的数字，定义一次，使同一指标在助手、仪表盘和董事会报告中含义一致。技术：语义层，每个指标有其粒度、维度和参数，从金牌 medallion 表计算。" />
      </h2>
      <ul>
        {domain.metrics.map((m) => (
          <li key={m.name}>
            <strong>{m.name}</strong>（{m.grain || "无粒度"}）参数：{m.params.join("、") || "无"}
          </li>
        ))}
      </ul>

      <h2>数据血缘
        <Hint text="业务：每个数字的来源以及PII在途中如何被保护——监管机构或买家要求的审计追踪。技术：medallion 路径（bronze到silver到gold），哪些列被掩码，每层服务哪些治理指标。" />
      </h2>
      <ul>
        {domain.lineage.medallion.map((r) => (
          <li key={r.role}>
            {r.layers.join(" → ")}
            {r.pii_columns.length > 0 && <span className="meta">（PII：{r.pii_columns.join("、")}）</span>}
            {r.metrics.length > 0 && <span className="meta"> 服务指标：{r.metrics.join("、")}</span>}
          </li>
        ))}
      </ul>
    </main>
  );
}
