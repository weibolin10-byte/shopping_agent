"use client";

import { useEffect, useState } from "react";

import { Hint } from "../Hint";
import { AdminNav } from "../nav";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Bucket = {
  total: number;
  p95_latency_ms: number | null;
  error_rate: number;
  avg_cost: number | null;
  avg_grounding: number | null;
  throughput_per_min: number | null;
};

type Health = {
  overall: Bucket & { grounding_trend: { early: number | null; recent: number | null; delta: number | null } };
  by_language: Record<string, Bucket>;
};

function Row({ name, b }: { name: string; b: Bucket }) {
  return (
    <tr>
      <td>{name}</td>
      <td>{b.total}</td>
      <td>{b.p95_latency_ms ?? "-"}</td>
      <td>{b.throughput_per_min ?? "-"}</td>
      <td>{(b.error_rate * 100).toFixed(1)}%</td>
      <td>{b.avg_cost === null ? "-" : `¥${b.avg_cost.toFixed(4)}`}</td>
      <td>{b.avg_grounding === null ? "-" : b.avg_grounding.toFixed(2)}</td>
    </tr>
  );
}

export default function HealthPage() {
  const [mounted, setMounted] = useState(false);
  const [data, setData] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    const token = localStorage.getItem("shopping_agent_admin_token");
    if (!token) {
      setError("请先在 /admin 页面登录。");
      return;
    }
    fetch(`${API_BASE}/api/admin/health`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError("无法加载健康数据（您是否是管理员？）。"));
  }, []);

  if (!mounted) return null;
  if (error) return <main className="admin"><p className="error">{error}</p></main>;
  if (!data) return <main className="admin"><p>正在加载...</p></main>;

  const trend = data.overall.grounding_trend;
  return (
    <main className="admin">
      <AdminNav />
      <h1>平台健康</h1>
      <p className="ax-intro">
        基于近期请求追踪的助手实时运行健康状况：响应速度、可靠性、每条回答的成本。按语言细分，因为检索质量可能因语言而异。
      </p>
      <table>
        <thead>
          <tr>
            <th>分段</th>
            <th>请求数<Hint text="业务：该分段承载了多少真实流量，使其他数字有分量。技术：近期窗口内该语言分段已回答轮次的计数。" /></th>
            <th>P95 毫秒<Hint text="业务：大多数购物者不会超过的慢情况体验；决定助手是否感觉即时的数字。技术：第95百分位端到端延迟，95%的回答比这更快。" /></th>
            <th>请求/分钟<Hint text="业务：当前负载，判断是否需要担心峰值或停滞。技术：最近15分钟窗口内每分钟请求数。" /></th>
            <th>错误率<Hint text="业务：购物者遇到降级回答的频率；可靠性承诺。技术：失败或回退轮次的比例，通常是上游模型故障由回退链吸收。" /></th>
            <th>平均成本<Hint text="业务：每条回答的服务成本，毛利率背后的单位经济。技术：每条计费轮次的平均模型花费（人民币）；流式轮次不计token成本。" /></th>
            <th>事实性<Hint text="业务：每条回答有多少由真实来源支持，信任和幻觉防护栏。技术：已回答轮次的平均来源支持度（0到1）；注意它是否随时间下降。" /></th>
          </tr>
        </thead>
        <tbody>
          <Row name="全部" b={data.overall} />
          {Object.entries(data.by_language).map(([lang, b]) => (
            <Row key={lang} name={lang} b={b} />
          ))}
        </tbody>
      </table>
      {trend.delta !== null && (
        <p className="meta">
          检索质量趋势：{trend.early} → {trend.recent}（变化 {trend.delta}）
        </p>
      )}
    </main>
  );
}
