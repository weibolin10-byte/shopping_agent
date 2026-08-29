"use client";

import { useEffect, useState } from "react";

import { BarList, Donut, Funnel, Sparkbars } from "../charts";
import { Hint } from "../Hint";
import { AdminNav } from "../nav";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Analytics = {
  kpis: Record<string, number>;
  sessions_by_day: { day: string; count: number }[];
  top_searches: { term: string; count: number }[];
  top_questions: { question: string; count: number }[];
  top_products: { name: string; count: number }[];
  by_category: { label: string; pct: number }[];
  by_device: { label: string; pct: number }[];
  by_country: { label: string; pct: number }[];
  funnel: { step: string; count: number }[];
  unmet_demand?: { term: string; count: number; reason: string }[];
};
type Gap = { question: string; count: number };

const money = (n: number) => "¥" + (n || 0).toLocaleString();
const num = (n: number) => (n || 0).toLocaleString();

export default function AnalyticsPage() {
  const [mounted, setMounted] = useState(false);
  const [a, setA] = useState<Analytics | null>(null);
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
    fetch(`${API_BASE}/api/admin/analytics`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setA)
      .catch(() => setError("无法加载分析数据（您是否是管理员？）。"));
    fetch(`${API_BASE}/api/admin/gaps`, { headers })
      .then((r) => (r.ok ? r.json() : { gaps: [] }))
      .then((d) => setGaps(d.gaps || []))
      .catch(() => {});
  }, []);

  if (!mounted) return null;
  if (error)
    return (
      <main className="admin">
        <AdminNav />
        <p className="error">{error}</p>
      </main>
    );
  if (!a || !a.kpis)
    return (
      <main className="admin">
        <AdminNav />
        <p className="meta">
          {a ? "当前领域暂无分析数据。" : "正在加载仪表盘..."}
        </p>
      </main>
    );

  const k = a.kpis;
  const kpis = [
    { label: "会话数", value: num(k.sessions),
      hint: "业务：窗口内访问商店的次数，漏斗最顶端。技术：从请求追踪中统计的不同浏览器会话，按会话 ID 去重。" },
    { label: "访客数", value: num(k.visitors),
      hint: "业务：多少不同的人来访，避免重复访问虚高覆盖人数。技术：跨会话的独立访客 ID；访客数低于会话数说明有人回访。" },
    { label: "订单数", value: num(k.orders),
      hint: "业务：完成的购买数，商店存在的最终目标。技术：窗口内结算完成事件的计数。" },
    { label: "营收", value: money(k.revenue),
      hint: "业务：窗口内总销售额。技术：按商店货币计算的订单总额汇总，退货前毛额。" },
    { label: "转化率", value: `${k.conversion}%`,
      hint: "业务：访问者中购买的比例，最直观的健康信号。技术：订单数除以会话数；分母小时波动大，需结合会话数判断。" },
    { label: "客单价", value: money(k.aov),
      hint: "业务：每位购物者每次购买的消费额；追加销售和捆绑销售可提升。技术：营收除以订单数（AOV）。" },
    { label: "搜索次数", value: num(k.searches),
      hint: "业务：购物者搜索的频率；高搜索低转化说明可发现性有差距。技术：窗口内搜索和助手检索查询的计数。" },
    { label: "加购次数", value: num(k.add_to_cart),
      hint: "业务：购买意向，结算前的最后一步；到订单的差距就是购物车放弃率。技术：加购事件计数。" },
  ];

  return (
    <main className="admin">
      <AdminNav />
      <h1>商店总览</h1>
      <p className="ax-intro">
        助手背后的业务视图：流量、购物者搜索和提问的内容，以及漏斗转化情况。近30天，共 {num(k.sessions)} 个会话。
      </p>

      <div className="stats">
        {kpis.map((kp) => (
          <div key={kp.label} className="stat">
            <div className="stat-label">
              {kp.label}
              <Hint text={kp.hint} />
            </div>
            <div className="stat-value">{kp.value}</div>
          </div>
        ))}
      </div>

      <div className="ax-grid">
        <div className="ax-card ax-wide">
          <h3>每日会话数
            <Hint text="业务：流量趋势，可关联营销活动或服务中断。技术：窗口内每日请求追踪的会话计数。" />
          </h3>
          <Sparkbars data={a.sessions_by_day} />
        </div>
        <div className="ax-card">
          <h3>转化漏斗
            <Hint text="业务：购物者从进入到购买各环节的流失情况；降幅最大处最值得投入。技术：从会话到搜索到加购到订单，每一步占上一步的比例。" />
          </h3>
          <Funnel steps={a.funnel} />
        </div>
        <div className="ax-card">
          <h3>热门搜索
            <Hint text="业务：购物者在主动找什么，是商品推销的需求信号。技术：按频次排名的最常搜索词。" />
          </h3>
          <BarList items={a.top_searches.map((s) => ({ label: s.term, count: s.count }))} />
        </div>
        <div className="ax-card">
          <h3>用户常问助手的问题
            <Hint text="业务：用户用自己的话信任助手回答的问题；是内容和FAQ的路线图。技术：按频次聚类的最常见助手查询。" />
          </h3>
          <BarList items={a.top_questions.map((s) => ({ label: s.question, count: s.count }))} />
        </div>
        <div className="ax-card">
          <h3>最多浏览商品
            <Hint text="业务：什么在吸引注意力；结合转化率可区分只看不买和真正购买。技术：按计数排名的商品详情页浏览。" />
          </h3>
          <BarList items={a.top_products.map((s) => ({ label: s.name, count: s.count }))} />
        </div>
        <div className="ax-card">
          <h3>分类流量
            <Hint text="业务：哪些品类吸引人群，指导库存和促销跟随需求。技术：按商品分类的会话占比，前六名。" />
          </h3>
          <Donut slices={a.by_category.slice(0, 6)} />
        </div>
        <div className="ax-card">
          <h3>设备分布
            <Hint text="业务：移动端与桌面端的比例，决定UX投入的方向。技术：从请求User-Agent推断的设备类别会话占比。" />
          </h3>
          <Donut slices={a.by_device} />
        </div>
        <div className="ax-card">
          <h3>地区分布
            <Hint text="业务：需求在哪里，指导配送、货币和语言优先级。技术：从请求推断的国家/地区会话占比。" />
          </h3>
          <Donut slices={a.by_country} />
        </div>
        <div className="ax-card ax-wide">
          <h3>未能很好回答的问题
            <Hint text="业务：未满足的问题，按频次排名；每解决一个都提升信任和转化。技术：助手拒答或 grounding 分数低的轮次，按问题分组。" />
          </h3>
          {gaps.length === 0 ? (
            <p className="meta">暂无标记，助手正在自信地回答。</p>
          ) : (
            <BarList items={gaps.slice(0, 8).map((g) => ({ label: g.question, count: g.count }))} />
          )}
        </div>
        {a.unmet_demand && a.unmet_demand.length > 0 && (
          <div className="ax-card ax-wide">
            <h3>未满足需求：购物者想要但我们没有的
              <Hint text="业务：暂时无法捕获的收入，按出现频次排名；是商品推销和路线图的工作清单。技术：没有匹配商品或政策文档的搜索和问题，按词条分组。" />
            </h3>
            <p className="meta">
              流失的商机：人们搜索或询问但我们目前无法提供的东西。每个都是一个商品决策——进货、扩展尺码或地区、或增加功能。
            </p>
            <ul className="unmet-list">
              {a.unmet_demand.map((u) => (
                <li key={u.term}>
                  <span className="unmet-count">{u.count}</span>
                  <span className="unmet-term">{u.term}</span>
                  <span className="unmet-reason">{u.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </main>
  );
}
