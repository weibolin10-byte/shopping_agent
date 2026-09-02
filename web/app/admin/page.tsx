"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminNav } from "./nav";
import { useTurnstile } from "../turnstile";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Item = {
  id: string;
  question: string;
  route: string | null;
  domain: string | null;
  status: string;
};

// The login lives in its own component so it mounts together with the Turnstile widget div. If the
// hook ran on a parent that first renders null (the mounted gate), its one-shot effect would fire
// against a missing ref and the widget would never appear, making production admin login impossible.
function AdminLogin({ onToken }: { onToken: (t: string) => void }) {
  const [username, setUsername] = useState("newadmin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { token: captchaToken, widget: captchaWidget, reset: resetCaptcha } = useTurnstile();

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, turnstile_token: captchaToken || undefined }),
      });
      if (res.status === 403) {
        setError("验证码校验失败，请重试。");
        resetCaptcha();
        return;
      }
      if (!res.ok) {
        setError("登录失败。");
        resetCaptcha(); // the captcha token was consumed; the retry needs a fresh one
        return;
      }
      onToken((await res.json()).access_token);
    } catch {
      setError("无法连接服务器。");
    }
  }

  return (
    <main className="admin">
      <form onSubmit={login} className="login">
        <div className="ax-brand">
          {process.env.NEXT_PUBLIC_STORE_NAME || "智能商城"} <span>管理后台</span>
        </div>
        <p className="meta">登录以管理审核队列、质量和健康状态。</p>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
          aria-label="用户名"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
          aria-label="密码"
        />
        {captchaWidget}
        <button type="submit">登录</button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [flywheel, setFlywheel] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    setToken(localStorage.getItem("shopping_agent_admin_token"));
  }, []);

  const auth = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  function signOut() {
    localStorage.removeItem("shopping_agent_admin_token");
    setToken(null); // re-renders AdminLogin
  }

  async function loadQueue(t = token) {
    setError(null);
    const res = await fetch(`${API_BASE}/api/admin/queue`, {
      headers: { Authorization: `Bearer ${t}` },
    });
    if (res.status === 401) {
      signOut(); // the token expired; send the operator back to the login instead of a dead page
      return;
    }
    if (res.status === 403) {
      setError("该账户没有管理员权限。");
      return;
    }
    if (!res.ok) {
      setError("无法加载审核队列。");
      return;
    }
    setItems((await res.json()).items);
  }

  useEffect(() => {
    if (token) loadQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function onToken(t: string) {
    // land on the Overview dashboard after sign-in, not the bare review queue
    localStorage.setItem("shopping_agent_admin_token", t);
    router.push("/admin/analytics");
  }

  async function claim(id: string) {
    const res = await fetch(`${API_BASE}/api/admin/queue/${id}/claim`, {
      method: "POST",
      headers: auth,
    });
    if (!res.ok) setError("无法认领（可能已被他人认领）。");
    loadQueue();
  }

  async function answer(id: string) {
    const body = JSON.stringify({ answer: answers[id] || "" });
    const res = await fetch(`${API_BASE}/api/admin/queue/${id}/answer`, {
      method: "POST",
      headers: auth,
      body,
    });
    if (res.ok) loadQueue();
    else setError("无法提交回答（请先认领，或已被他人处理）。");
  }

  async function runFlywheel() {
    setFlywheel("正在运行...");
    const res = await fetch(`${API_BASE}/api/admin/flywheel`, { method: "POST", headers: auth });
    if (res.status === 401) {
      signOut();
      return;
    }
    if (!res.ok) {
      setFlywheel("飞轮运行失败。");
      return;
    }
    const r = await res.json();
    setFlywheel(`已索引 ${r.indexed} 条回答，评估集增长 ${r.grown}。建议阈值：${r.threshold.suggested}。`);
  }

  if (!mounted) return null;

  if (!token) return <AdminLogin onToken={onToken} />;

  return (
    <main className="admin">
      <AdminNav />
      <h1>审核队列（{items.length}）</h1>
      <p className="ax-intro">
        AI 助手转接给人工的问题，以及您已认领的项目。认领后即可锁定问题、编写验证答案并关闭。
        运行飞轮会将这些回答重新索引，下次 AI 助手即可自行回答同类问题。
      </p>
      <div className="row">
        <button onClick={runFlywheel}>运行飞轮</button>
        <button className="signout" onClick={signOut}>退出登录</button>
        {flywheel && <span className="meta">{flywheel}</span>}
      </div>
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p>暂无待处理问题，系统当前状态良好。</p>}
      {items.map((it) => (
        <div key={it.id} className="queue-item">
          <p className="q">{it.question}</p>
          <p className="meta">
            {it.domain} · {it.route || "未路由"}
          </p>
          <div className="row">
            {/* Claim is always offered: on an open item it locks it, on a stale claimed one it
                takes it over (the server rejects a live claim by someone else). */}
            <button onClick={() => claim(it.id)}>认领</button>
          </div>
          {it.status === "claimed" && (
            <>
              <textarea
                value={answers[it.id] || ""}
                onChange={(e) => setAnswers({ ...answers, [it.id]: e.target.value })}
                placeholder="编写验证后的回答"
              />
              <div className="row">
                <button onClick={() => answer(it.id)}>回答并关闭</button>
              </div>
            </>
          )}
        </div>
      ))}
    </main>
  );
}
