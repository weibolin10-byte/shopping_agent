"use client";

import { useEffect, useState } from "react";

import { fetchStore } from "../catalog";
import { useChat } from "../ChatProvider";
import { useRequireGate } from "../gate";
import StoreFooter from "../StoreFooter";
import StoreHeader from "../StoreHeader";

const TOPICS = [
  {
    topic: "shipping",
    title: "配送说明",
    body: "上海发货，全国配送。标准配送满150元包邮，否则统一8元，预计2-8个工作日送达（视距离而定）。加急配送15元（1-2天）。暂不支持海外配送。",
  },
  {
    topic: "returns",
    title: "退换货",
    body: "30天内未穿着、吊牌完好的商品可申请全额退款。退货免费，提供预付费运单。换货在物流揽收后立即发出，无需额外费用。退款将在5-7个工作日内到账。",
  },
  {
    topic: "sizing",
    title: "尺码与版型",
    body: "尺码范围 XS-XL，包袋及配饰为均码。大部分商品为正常尺码；紧身裤为压缩版型，喜欢宽松建议选大一码。每个商品页面均有尺码表，评价中也常有版型反馈。",
  },
  {
    topic: "payment",
    title: "支付方式",
    body: "支持微信支付、支付宝、银联卡、Visa、Mastercard、Apple Pay、花呗分期等。满50元可享花呗免息分期。",
  },
  {
    topic: "care",
    title: "商品保养",
    body: "冷水机洗，同色洗涤，悬挂晾干或低温烘干。功能性面料避免使用柔顺剂，会影响吸湿排汗效果。羊毛制品可冷水羊毛模式洗涤。",
  },
  {
    topic: "warranty",
    title: "品质保证",
    body: "所有商品均享有制造缺陷质保（缝线、拉链等），我们提供维修或更换服务。正常磨损和使用不当不在质保范围内。",
  },
  {
    topic: "membership",
    title: "会员中心",
    body: "免费加入。消费1元积1分，新品优先购、会员专属运费优惠、生日礼券。积分可在结算时抵扣。",
  },
  {
    topic: "support",
    title: "联系客服",
    body: "在线客服与邮件支持每周7天，9:00-21:00（北京时间）。如 AI 助手无法解决，将转接人工专员，1个工作日内跟进。",
  },
];

export default function HelpPage() {
  const gateOk = useRequireGate();
  const [brand, setBrand] = useState("");
  const { openWith } = useChat();
  useEffect(() => {
    fetchStore().then((s) => setBrand(s.brand));
  }, []);
  if (!gateOk) return null;

  return (
    <>
      <StoreHeader brand={brand} />
      <main className="help">
        <h1>帮助与政策</h1>
        <p className="section-sub">
          AI 助手所知的一切信息汇总于此。有具体问题？直接问就好。
        </p>
        <div className="help-grid">
          {TOPICS.map((t) => (
            <section key={t.topic} className="help-card">
              <h3>{t.title}</h3>
              <p>{t.body}</p>
              <button
                className="chip"
                onClick={() => openWith(`请告诉我更多关于${t.title}的信息`, { kind: "help", topic: t.topic })}
              >
                了解{t.title}
              </button>
            </section>
          ))}
        </div>
      </main>
      <StoreFooter brand={brand} />
    </>
  );
}
