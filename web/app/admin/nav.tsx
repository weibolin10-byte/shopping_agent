"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Shared backoffice top bar: brand plus tabs with an active state, so every admin view feels like
// one console.
const TABS = [
  { href: "/admin/analytics", label: "总览" },
  { href: "/admin", label: "审核队列" },
  { href: "/admin/quality", label: "质量" },
  { href: "/admin/health", label: "健康" },
  { href: "/admin/insights", label: "洞察" },
];

export function AdminNav() {
  const path = usePathname();
  const brand = process.env.NEXT_PUBLIC_STORE_NAME || "智能商城";
  return (
    <div className="ax-topbar">
      <Link href="/admin" className="ax-brand">
        {brand} <span>管理后台</span>
      </Link>
      <nav className="ax-tabs">
        {TABS.map((t) => (
          <Link key={t.href} href={t.href} className={path === t.href ? "on" : ""}>
            {t.label}
          </Link>
        ))}
      </nav>
      <Link href="/" className="ax-exit">
        查看商店 &rarr;
      </Link>
    </div>
  );
}
