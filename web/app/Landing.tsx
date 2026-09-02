"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "./catalog";
import { setGate } from "./gate";
import { useTurnstile } from "./turnstile";

// Reveal children on scroll for a bit of motion without a library.
function useReveal() {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const els = ref.current?.querySelectorAll(".rv");
    if (!els) return;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
      { threshold: 0.15 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}

const FLOW = [
  { n: "01", t: "数据来源", d: "商品目录、描述、评价、政策等结构化与非结构化数据。", tech: ["CSV", "JSONL"] },
  { n: "02", t: "摄入与处理", d: "分片、向量化、稀疏 BM25 编码。数据湖仓治理各项指标。", tech: ["千问 Embedding", "dbt", "DuckDB"] },
  { n: "03", t: "存储", d: "混合向量检索、商品与供应商知识图谱、治理指标表。", tech: ["内存向量库", "Neo4j", "DuckDB"] },
  { n: "04", t: "检索", d: "稠密+稀疏混合搜索，重排序，融合图谱事实与治理指标。", tech: ["千问 Rerank", "BM25", "Graph"] },
  { n: "05", t: "推理", d: "智能体大脑理解意图、调度专家、整合信息并进行事实核查。每条回答均引用来源，不确定时坦诚告知。", tech: ["LangGraph", "DeepSeek"] },
  { n: "06", t: "监控与服务", d: "每轮对话均可追踪和评估。流式输出到店面，支持语音助手。", tech: ["Langfuse", "RAGAS", "FastAPI", "Next.js"] },
];

const STACK = [
  "千问 Embedding", "千问 Rerank", "DeepSeek", "千问 Turbo",
  "内存向量库", "Neo4j", "DuckDB", "LangChain", "LangGraph", "Langfuse", "MLflow",
  "RAGAS", "FastAPI", "Next.js",
];

const FEATURES = [
  { t: "有据可依·引用来源", d: "每个回答都基于检索到的上下文，附带内联引用，不确定时坦诚告知而非猜测。" },
  { t: "知识图谱 + 指标", d: "超越文本：商品图谱和治理指标表能回答关系类和数字类问题。" },
  { t: "语音对话", d: "免提语音模式，可在回答中途打断，像真实对话一样自然。" },
  { t: "领域可切换", d: "一份配置驱动整个引擎，切换数据包即可服务任意领域。" },
];

export default function Landing({ onEnter }: { onEnter: () => void }) {
  const ref = useReveal();
  const [brand, setBrand] = useState(process.env.NEXT_PUBLIC_STORE_NAME || "智能商城");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { token: captchaToken, widget: captchaWidget, reset: resetCaptcha } = useTurnstile();

  useEffect(() => {
    fetch(`${API_BASE}/api/catalog`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.brand && setBrand(d.brand))
      .catch(() => {});
  }, []);

  async function enter(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    const data = new FormData(e.currentTarget);
    try {
      const res = await fetch(`${API_BASE}/api/gate-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: data.get("username") || "demo",
          password: data.get("password") || "demo12345",
          turnstile_token: captchaToken || undefined,
        }),
      });
      if (res.ok) {
        setGate((await res.json()).access_token);
        onEnter();
      } else if (res.status === 401) {
        setError("用户名或密码不正确。");
        resetCaptcha();
      } else if (res.status === 403) {
        setError("请完成验证码后重试。");
        resetCaptcha();
      } else if (res.status === 429) {
        setError("尝试次数过多，请稍后再试。");
      } else {
        setError("验证失败，请重试。");
        resetCaptcha();
      }
    } catch {
      setError("无法连接服务器，请确认 API 是否正在运行。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="lp" ref={ref}>
      <header className="lp-nav">
        <div className="lp-brand">
          {brand}
          <span>.</span> <em>agentic RAG</em>
        </div>
        <a className="lp-cta-sm" href="#gate">
          查看演示
        </a>
      </header>

      <section className="lp-hero">
        <div className="rv">
          <div className="lp-kicker">检索增强 · 知识图谱 · 智能体</div>
          <h1>
            真正<span>了解商品目录</span>的 AI 助手
          </h1>
          <p>
            一个领域可切换的 Agentic RAG 平台。此处展示为运动品牌电商店面，同一引擎可服务任意领域。
            有据可依、引用来源、不知为不知。
          </p>
          <div className="lp-hero-cta">
            <a className="btn btn-primary" href="#gate">
              进入在线演示
            </a>
            <a className="btn btn-ghost lp-ghost" href="#how">
              工作原理
            </a>
          </div>
        </div>
        <div className="lp-orbwrap rv">
          <div className="lp-orb" />
          <div className="lp-orb-ring" />
        </div>
      </section>

      <section className="lp-features">
        {FEATURES.map((f) => (
          <div key={f.t} className="lp-feat rv">
            <h3>{f.t}</h3>
            <p>{f.d}</p>
          </div>
        ))}
      </section>

      <section className="lp-how" id="how">
        <div className="lp-sec-head rv">
          <div className="lp-kicker">处理流程</div>
          <h2>从原始数据到有据可依的回答</h2>
        </div>
        <div className="lp-flow">
          {FLOW.map((s, i) => (
            <div key={s.n} className="lp-stage rv" style={{ transitionDelay: `${i * 60}ms` }}>
              <div className="lp-stage-n">{s.n}</div>
              <h4>{s.t}</h4>
              <p>{s.d}</p>
              <div className="lp-tags">
                {s.tech.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
              {i < FLOW.length - 1 && <div className="lp-arrow">→</div>}
            </div>
          ))}
        </div>
      </section>

      <section className="lp-stack rv">
        <div className="lp-kicker">技术栈</div>
        <div className="lp-badges">
          {STACK.map((s) => (
            <span key={s} className="lp-badge">
              {s}
            </span>
          ))}
        </div>
      </section>

      <section className="lp-gate" id="gate">
        <div className="lp-gate-card rv">
          <div className="lp-kicker">演示入口</div>
          <h2>进入在线演示</h2>
          <p>
            点击下方按钮即可进入演示体验。演示环境已开放免密登录，直接点击进入即可。
          </p>
          <form className="lp-gate-form" onSubmit={enter}>
            <input name="username" placeholder="用户名（demo）" aria-label="用户名" autoComplete="username" defaultValue="demo" />
            <input
              name="password"
              type="password"
              placeholder="密码（demo12345）"
              aria-label="密码"
              autoComplete="current-password"
              defaultValue="demo12345"
            />
            {captchaWidget}
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "验证中..." : "进入演示"}
            </button>
            {error && <p className="err">{error}</p>}
          </form>
          <p className="lp-gate-note">
            演示环境无需注册，直接点击进入即可体验。
          </p>
        </div>
      </section>

      <footer className="lp-foot">
        <span>基于 Agentic RAG 构建</span>
        <span>合成数据 · 无真实商品或人物</span>
      </footer>
    </div>
  );
}
