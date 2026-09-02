"use client";

import Link from "next/link";

// Shared footer for every store page. Brand text comes from the API (never hardcoded), so the
// engine stays domain agnostic.
export default function StoreFooter({ brand }: { brand?: string }) {
  const name = brand || process.env.NEXT_PUBLIC_STORE_NAME || "智能商城";
  const short = name;
  return (
    <footer className="sfoot">
      <div className="sfoot-in">
        <div className="sfoot-brand-col">
          <div className="sfoot-brand">
            {short}
            <span>.</span>
          </div>
          <p>
            {name}，提供商品浏览与智能导购。平台基于 Agentic RAG 构建，演示数据均为合成数据。
          </p>
        </div>
        <div className="sfoot-col">
          <h4>购物</h4>
          <Link href="/?g=women">女士</Link>
          <Link href="/?g=men">男士</Link>
          <Link href="/">新品上架</Link>
        </div>
        <div className="sfoot-col">
          <h4>帮助</h4>
          <Link href="/shipping">配送说明</Link>
          <Link href="/size-guide">尺码表</Link>
          <Link href="/payment">支付方式</Link>
          <Link href="/help">全部政策</Link>
        </div>
        <div className="sfoot-col">
          <h4>关于我们</h4>
          <Link href="/membership">会员中心</Link>
          <Link href="/contact">联系我们</Link>
          <a href="/admin">管理后台</a>
          <span className="sfoot-credit">基于 Agentic RAG 构建</span>
        </div>
      </div>
      <div className="sfoot-bottom">
        <span>{name}（演示）· 上海发货 · 全国配送</span>
        <span>满150元包邮</span>
      </div>
    </footer>
  );
}
