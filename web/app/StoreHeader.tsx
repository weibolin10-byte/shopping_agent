"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useCart } from "./cart";
import { useChat } from "./ChatProvider";

export default function StoreHeader({ brand, active }: { brand: string; active?: string }) {
  const { count } = useCart();
  const { openWith } = useChat();
  const router = useRouter();
  const [term, setTerm] = useState("");
  const short = brand || process.env.NEXT_PUBLIC_STORE_NAME || "智能商城";
  const genders = [
    { key: "women", label: "女士" },
    { key: "men", label: "男士" },
    { key: "all", label: "全部" },
  ];
  return (
    <header className="hdr">
      <div className="hdr-in">
        <Link href="/" className="brand">
          {short}
          <span>.</span>
        </Link>
        <nav className="nav">
          {genders.map((g) => (
            <Link
              key={g.key}
              href={g.key === "all" ? "/" : `/?g=${g.key}`}
              className={active === g.key ? "on" : ""}
            >
              {g.label}
            </Link>
          ))}
        </nav>
        <form
          className="hdr-search"
          style={{ marginLeft: "auto" }}
          onSubmit={(e) => {
            e.preventDefault();
            if (term.trim()) router.push(`/?q=${encodeURIComponent(term.trim())}`);
          }}
        >
          <span className="hs-icon">&#128269;</span>
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="搜索产品"
            aria-label="搜索产品"
          />
        </form>
        <button className="chip" onClick={() => openWith(null, null)}>
          AI助手
        </button>
        <Link href="/cart" className="cart-btn" aria-label="购物车">
          &#128722;
          {count > 0 && <span className="cart-count">{count}</span>}
        </Link>
      </div>
    </header>
  );
}
