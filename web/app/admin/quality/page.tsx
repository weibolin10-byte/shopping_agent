"use client";

import { useEffect, useState } from "react";

import { Hint } from "../Hint";
import { AdminNav } from "../nav";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Bucket = {
  total: number;
  escalation_rate: number;
  abstain_rate: number;
  avg_grounding: number | null;
  thumbs_up: number;
  thumbs_down: number;
};

type Quality = { overall: Bucket; by_language: Record<string, Bucket> };

function Row({ name, b }: { name: string; b: Bucket }) {
  return (
    <tr>
      <td>{name}</td>
      <td>{b.total}</td>
      <td>{(b.escalation_rate * 100).toFixed(1)}%</td>
      <td>{(b.abstain_rate * 100).toFixed(1)}%</td>
      <td>{b.avg_grounding === null ? "-" : b.avg_grounding.toFixed(2)}</td>
      <td>
        {b.thumbs_up} / {b.thumbs_down}
      </td>
    </tr>
  );
}

function Stat({ label, value, pct, tone, hint }: {
  label: string; value: string; pct?: number; tone?: string; hint?: string;
}) {
  return (
    <div className="stat">
      <div className="stat-label">
        {label}
        {hint && <Hint text={hint} />}
      </div>
      <div className="stat-value">{value}</div>
      {pct !== undefined && (
        <div className="bar">
          <div className={`bar-fill ${tone || ""}`}
            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
        </div>
      )}
    </div>
  );
}

export default function QualityPage() {
  const [mounted, setMounted] = useState(false);
  const [data, setData] = useState<Quality | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    const token = localStorage.getItem("shopping_agent_admin_token");
    if (!token) {
      setError("请先在 /admin 页面登录。");
      return;
    }
    fetch(`${API_BASE}/api/admin/quality`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError("无法加载质量数据（您是否是管理员？）。"));
  }, []);

  if (!mounted) return null;
  if (error) return <main className="admin"><p className="error">{error}</p></main>;
  if (!data) return <main className="admin"><p>正在加载...</p></main>;

  const o = data.overall;
  return (
    <main className="admin">
      <AdminNav />
      <h1>回答质量</h1>
      <p className="ax-intro">
        助手回答购物者问题的质量，基于商店运行的相同请求追踪。悬停任何 <span className="ax-hint" style={{ cursor: "default" }}>?</span> 查看指标含义。
      </p>
      <div className="stats">
        <Stat label="轮次数" value={String(o.total)}
          hint="业务：质量读数基于多少条回答，使下方比率有分量。技术：近期流量窗口内助手回答的总数。" />
        <Stat label="事实性" value={o.avg_grounding === null ? "-" : o.avg_grounding.toFixed(2)}
          pct={(o.avg_grounding || 0) * 100} tone="good"
          hint="业务：反幻觉评分；越高表示购物者越能信任被告知的内容。技术：每条回答由检索来源支持的平均比例（0到1）。" />
        <Stat label="拒答率" value={`${(o.abstain_rate * 100).toFixed(0)}%`}
          pct={o.abstain_rate * 100} tone="warn"
          hint="业务：助手说'我不确定'而非猜测的频率；这是功能而非缺陷，但突增标志着内容缺口。技术：因检索置信度低于阈值而拒绝回答的轮次比例。" />
        <Stat label="转人工率" value={`${(o.escalation_rate * 100).toFixed(0)}%`}
          pct={o.escalation_rate * 100} tone="warn"
          hint="业务：人工专员被介入的频率；困难或敏感请求的安全网。技术：由督导员转到审核队列的轮次比例。" />
        <Stat label="有帮助" value={`${o.thumbs_up} / ${o.thumbs_down}`}
          pct={o.thumbs_up + o.thumbs_down ? (o.thumbs_up / (o.thumbs_up + o.thumbs_down)) * 100 : 0}
          tone="good"
          hint="业务：购物者对回答的直接评价，最真实的满意度信号。技术：助手轮次上留下的赞/踩数。" />
      </div>
      <table>
        <thead>
          <tr>
            <th>分段</th>
            <th>轮次</th>
            <th>转人工</th>
            <th>拒答</th>
            <th>事实性</th>
            <th>赞/踩</th>
          </tr>
        </thead>
        <tbody>
          <Row name="全部" b={data.overall} />
          {Object.entries(data.by_language).map(([lang, b]) => (
            <Row key={lang} name={lang} b={b} />
          ))}
        </tbody>
      </table>
    </main>
  );
}
