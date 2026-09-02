import "./globals.css";
import type { ReactNode } from "react";

import { CartProvider } from "./cart";
import { ChatProvider } from "./ChatProvider";

export const metadata = {
  title: `${process.env.NEXT_PUBLIC_STORE_NAME || "智能商城"} - AI 智能购物助手`,
  description: "基于 Agentic RAG 技术的智能电商平台，提供商品浏览与 AI 客服助手服务。",
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
