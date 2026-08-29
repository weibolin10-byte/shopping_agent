import "./globals.css";
import type { ReactNode } from "react";

import { CartProvider } from "./cart";
import { ChatProvider } from "./ChatProvider";

export const metadata = {
  title: "运动品牌集合 - AI 智能购物助手",
  description: "基于 Agentic RAG 技术的智能电商平台，提供运动品牌商品浏览与 AI 客服助手服务。",
  // private demo link: keep it out of search engines and bot crawls
  robots: { index: false, follow: false, nocache: true },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <CartProvider>
          <ChatProvider>{children}</ChatProvider>
        </CartProvider>
      </body>
    </html>
  );
}
