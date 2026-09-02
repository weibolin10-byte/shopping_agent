"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import Avatar, { AvatarState } from "./Avatar";
import { API_BASE, categoryLabel, fetchStore, PageContext, Product } from "./catalog";
import ImageTile from "./ImageTile";
import { Markdown } from "./markdown";

type Citation = { n: number; id: string; doc_type?: string | null };
type Suggestion = { text: string; lang: string; kind: string };

type FinalEvent = {
  type: "final";
  message_id?: string;
  tier: string;
  answer?: string;
  confidence?: number;
  grounding?: number;
  citations?: Citation[];
  session_id?: string;
  trace_id?: string;
  lane?: string;
  action?: "answer" | "clarify" | "abstain" | "escalate" | "workflow";
  clarification?: { reason?: string; missing_slots?: string[] } | null;
  degraded?: boolean;
};

type StreamEvent =
  | { type: "token"; text: string }
  | FinalEvent
  | { type: "error"; message?: string };

type Message = {
  role: "me" | "bot";
  text: string;
  final?: FinalEvent;
  feedback?: "up" | "down";
  recs?: Product[];
  followups?: string[];
  agent?: boolean; // from the AI care specialist, after an escalation
};

const AGENT_INTRO =
  "你好，我是智能商城的 AI 客服专家。👋 接下来由我为您服务。请告诉我您遇到的问题，" +
  "如果是关于订单的，我会立即帮您查询。";

const HELP_TOPIC_LABELS: Record<string, string> = {
  shipping: "配送说明",
  returns: "退换货",
  sizing: "尺码与版型",
  payment: "支付方式",
  care: "商品保养",
  warranty: "品质保证",
  membership: "会员中心",
  support: "联系客服",
};

function helpTopicLabel(topic: string): string {
  return HELP_TOPIC_LABELS[topic] || topic;
}

// Escape regex special chars in a product-name label.
const escRegex = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Build a matcher for a product label: word boundaries + optional plural for English names,
// plain substring match for Chinese names (which have no word boundaries).
function labelRegex(lab: string): RegExp {
  if (/[\u4e00-\u9fa9]/.test(lab)) return new RegExp(escRegex(lab), "gi");
  return new RegExp(`\\b${escRegex(lab)}s?\\b`, "gi");
}

// Is a JWT still valid (not within 30s of expiry)? A cached-but-expired token would otherwise be
// trusted on load, boot the chat, then 401 on the first message and dead-end at "连接中...".
// An unparseable token is trusted (the server will 401 it, which triggers a clean reconnect).
function tokenAlive(t: string): boolean {
  try {
    const payload = JSON.parse(atob((t.split(".")[1] || "").replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp !== "number" || payload.exp * 1000 > Date.now() + 30_000;
  } catch {
    return true;
  }
}

// Turn an internal citation id (CK33, graph:Product:P007, metric:...) into a human-readable source.
function citeLabel(c: Citation): string {
  const id = c.id || "";
  if (id.startsWith("graph:")) return "产品数据";
  if (id.startsWith("metric:")) return "店铺数据";
  if (/^CK/i.test(id)) return "店铺政策";
  if (/^(CATR|CAT)/i.test(id)) return "商品目录";
  if (/^OC/i.test(id)) return "购物指南";
  if (/^(PD|PC)/i.test(id)) return "产品信息";
  if (/^OD/i.test(id) || c.doc_type === "order") return "订单记录";
  if (/^(R\d|RV|RG)/i.test(id)) return "用户评价";
  if (c.doc_type === "review") return "用户评价";
  if (c.doc_type === "product") return "产品信息";
  if (c.doc_type === "guide") return "店铺信息";
  return id;
}

// Collapse citations to unique human-readable sources (many CK ids all read as "店铺政策").
function dedupeCites(cites?: Citation[]): Citation[] {
  if (!cites) return [];
  const seen = new Set<string>();
  const out: Citation[] = [];
  for (const c of cites) {
    const label = citeLabel(c);
    if (seen.has(label)) continue;
    seen.add(label);
    out.push(c);
    if (out.length >= 4) break;
  }
  return out;
}

// Products the assistant named in its answer, matched by catalog name, so we can show them as cards.
function recsFromAnswer(text: string, products: Product[]): Product[] {
  if (!text) return [];
  const low = text.toLowerCase();
  const seen = new Set<string>();
  const hits: { p: Product; at: number }[] = [];
  for (const p of products) {
    const full = p.name.toLowerCase();
    // match the SAME way the inline linker does, so a product gets a card exactly when it gets a link
    let at = -1;
    const m = low.match(labelRegex(full));
    if (m && m.index != null) at = m.index;
    if (at >= 0 && !seen.has(p.id)) {
      seen.add(p.id);
      hits.push({ p, at });
    }
  }
  // order the cards by where each product first appears in the answer, so the card row matches the
  // order of the bulleted recommendations rather than catalog order
  return hits.sort((a, b) => a.at - b.at).slice(0, 4).map((h) => h.p);
}

// On-device shopper memory: accumulate who they shop for and what they like, from their OWN messages,
// so the assistant can pick up across visits. Stored only in localStorage; the sole thing sent to the
// server is the short derived note below, as trusted context.
const REL_GENDER: Record<string, string> = {
  妈妈: "一位女性", 母亲: "一位女性", 老婆: "一位女性", 妻子: "一位女性", 女友: "一位女性",
  姐姐: "一位女性", 妹妹: "一位女性", 女儿: "一位女性", 奶奶: "一位女性", 外婆: "一位女性",
  阿姨: "一位女性", 侄女: "一位女性",
  爸爸: "一位男性", 父亲: "一位男性", 老公: "一位男性", 丈夫: "一位男性", 男友: "一位男性",
  哥哥: "一位男性", 弟弟: "一位男性", 儿子: "一位男性", 爷爷: "一位男性", 外公: "一位男性",
  叔叔: "一位男性", 侄子: "一位男性",
};
function updateShopperProfile(query: string): string {
  let prof: { recipients: Record<string, string>; likes: string[] };
  try {
    prof = JSON.parse(localStorage.getItem("aster_profile") || "null") || { recipients: {}, likes: [] };
  } catch {
    prof = { recipients: {}, likes: [] };
  }
  prof.recipients = prof.recipients || {};
  prof.likes = prof.likes || [];
  for (const rel of Object.keys(REL_GENDER)) {
    if (query.includes(rel)) prof.recipients[rel] = REL_GENDER[rel];
  }
  const interestRe = /(跑步|瑜伽|普拉提|动感单车|骑行|徒步|健身|训练|旅行|通勤|游泳|攀岩|高尔夫|滑雪|婚礼|正式场合|约会)/g;
  const likes = query.match(interestRe);
  for (const l of likes || []) if (!prof.likes.includes(l)) prof.likes.push(l);
  prof.likes = prof.likes.slice(-6);
  try {
    localStorage.setItem("aster_profile", JSON.stringify(prof));
  } catch {
    /* ignore */
  }
  const rec = Object.entries(prof.recipients).map(([r, g]) => `${r}（${g}）`);
  const parts: string[] = [];
  if (rec.length) parts.push("曾为 " + rec.slice(0, 3).join("、") + " 购物");
  if (prof.likes.length) parts.push("提到的兴趣：" + prof.likes.join("、"));
  return parts.join("；");
}

// Topic-narrowing follow-ups: after a policy answer, drill into that same topic rather than
// jumping to random suggestions, so each question can go deeper.
const TOPIC_MAP: Record<string, string[]> = {
  returns: ["退款需要多长时间？", "可以换其他尺码吗？", "收到的商品有损坏怎么办？"],
  shipping: ["什么条件下包邮？", "加急配送多久能到？", "配送到我的城市要多久？"],
  sizing: ["尺码表在哪里？", "紧身裤尺码偏小吗？", "介于两个尺码之间怎么选？"],
  payment: ["可以分期付款吗？", "支持微信支付吗？", "有礼品卡吗？"],
  care: ["可以烘干吗？", "羊毛制品怎么洗？", "洗涤会影响质保吗？"],
  warranty: ["质保涵盖哪些内容？", "如何申请质保？", "有质量问题怎么退货？"],
  membership: ["如何累积积分？", "会员有哪些权益？", "会员是免费的吗？"],
  discounts: ["有学生折扣吗？", "可以价保吗？", "有促销活动吗？"],
  stores: ["门店在哪里？", "可以到店自提吗？", "门店支持退货吗？"],
  order: ["我的订单在哪里？", "可以修改订单吗？", "如何跟踪物流？"],
  gift: ["送她什么礼物？", "送他什么礼物？", "100元以下有什么礼物？"],
};
const TOPIC_PATTERNS: [string, RegExp][] = [
  ["order", /(订单|物流|跟踪|快递|没收到|未收到|还没到|在哪里|发货)/i],
  ["returns", /(退货|退款|换货|return|refund|exchange)/i],
  ["warranty", /(质保|保修|缺陷|保证|损坏|故障|破损|warranty|defect|guarantee)/i],
  ["membership", /(会员|积分|忠诚度|奖励|member|membership|points|reward)/i],
  ["payment", /(支付|付款|分期|花呗|支付宝|微信支付|visa|paypal|payment|installment)/i],
  ["care", /(洗涤|保养|烘干|柔顺剂|羊毛|缩水|wash|care|dry|merino|shrink)/i],
  ["discounts", /(折扣|优惠|学生|促销|优惠券|价保|discount|student|promo|sale|coupon)/i],
  ["stores", /(门店|自提|提货|实体店|store|pickup|location)/i],
  ["gift", /(礼物|礼品|送礼|gift|present)|送(给)?(妈妈|爸爸|女友|男友|老婆|老公|朋友)/i],
  ["shipping", /(配送|运费|包邮|快递|发货|送达|加急|仓库|ship|shipping|deliver|express|warehouse)/i],
  ["sizing", /(尺码|尺寸|版型|合身|偏小|测量|size|sizing|fit|measurement)/i],
];

function detectTopic(text: string): string {
  for (const [key, rx] of TOPIC_PATTERNS) if (rx.test(text)) return key;
  return "";
}

// After recommending products, offer refinement follow-ups (narrow by color / price / use / a
// specific pick), not generic policy questions. Relevant to what the shopper is actually browsing.
function productFollowups(p: Product, recs: Product[]): string[] {
  const short = p.name;
  const useByCat: Record<string, string> = {
    jackets: "哪款最适合冬天保暖？",
    leggings: "哪款最适合健身？",
    bras: "哪款支撑性最好？",
    tops: "哪款最适合炎热天气？",
    bottoms: "哪款最适合旅行？",
    shorts: "哪款有口袋？",
    bags: "哪款最适合健身？",
    hoodies: "哪款最舒适？",
    accessories: "哪款最保暖？",
  };
  const out = [`${short} 有其他颜色吗？`];
  out.push(recs.length > 1 ? (useByCat[p.category] || "你最推荐哪一款？") : "看看类似的推荐");
  // only offer a cheaper option when something shown is actually over ¥100; otherwise suggest a
  // pairing, so it does not read as a reflexive discount nudge
  out.push(recs.some((r) => (r.price ?? 0) > 100) ? "100元以内有什么推荐？" : "这件搭配什么好？");
  return out;
}

// Sticky, narrowing follow-ups. A HARD policy topic (order, returns, shipping...) always wins.
// Otherwise a product recommendation gets refinement follow-ups. Soft topics and suggestions are the fallback.
const HARD_TOPICS = new Set([
  "order", "returns", "warranty", "shipping", "payment", "membership", "discounts", "stores",
]);
function followupsFor(
  query: string,
  final: FinalEvent,
  recs: Product[],
  suggestions: Suggestion[],
  lastTopic: string,
): { followups: string[]; topic: string } {
  const unsure = final.tier !== "auto";
  const detected = detectTopic(query);
  if (detected && HARD_TOPICS.has(detected)) return { followups: TOPIC_MAP[detected], topic: detected };
  if (!unsure && recs.length > 0) return { followups: productFollowups(recs[0], recs), topic: "" };
  if (detected) return { followups: TOPIC_MAP[detected], topic: detected };
  if (lastTopic && TOPIC_MAP[lastTopic]) return { followups: TOPIC_MAP[lastTopic], topic: lastTopic };
  return { followups: suggestions.slice(0, 3).map((s) => s.text), topic: lastTopic };
}

// Minimal shape of the browser SpeechRecognition.
type SpeechAlt = { transcript: string };
type SpeechRes = { [j: number]: SpeechAlt; isFinal: boolean };
type SpeechResult = { resultIndex: number; results: { [i: number]: SpeechRes; length: number } };
type Recognizer = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: (e: SpeechResult) => void;
  onerror: (e: { error?: string }) => void;
  onend: () => void;
  start: () => void;
  abort: () => void;
};

// Strip markdown and emoji so the voice speaks clean text.
function plainSpeak(text: string): string {
  return text
    .replace(/\s*\[\d+(?:\s*,\s*\d+)*\](?:\s*(?:,\s*)?(?:and\s+|&\s+)?\[\d+(?:\s*,\s*\d+)*\])*/g, "")
    .replace(/https?:\/\/\S+/gi, "") // never read a URL aloud character by character
    .replace(/\b\d{10,}\b/g, "") // never spell out a long tracking number
    .replace(/\s+([,.;:!?，。；：！？])/g, "$1")
    .replace(/([,;:])(?:\s*[,;:])+/g, "$1")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/^\s*[*-]\s+/gm, "")
    .replace(/^\s*\d+[.)]\s+/gm, "")
    .replace(/[\p{Extended_Pictographic}\u{FE0F}\u{20E3}\u{200D}]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}
// Significant words, for a fuzzy echo check that survives punctuation and casing differences.
function normWords(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 1);
}
function makeRecognizer(): Recognizer | null {
  if (typeof window === "undefined") return null;
  const SR =
    (window as unknown as { SpeechRecognition?: new () => Recognizer }).SpeechRecognition ||
    (window as unknown as { webkitSpeechRecognition?: new () => Recognizer }).webkitSpeechRecognition;
  return SR ? new SR() : null;
}
// Speak text and resolve when the voice finishes, so the loop waits before listening again.
function speakAsync(text: string): Promise<void> {
  return new Promise((resolve) => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!text || !synth) {
      resolve();
      return;
    }
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearTimeout(guard);
      resolve();
    };
    const guard = setTimeout(finish, Math.min(30_000, 2_000 + 120 * text.length));
    u.onend = finish;
    u.onerror = finish;
    synth.speak(u);
  });
}

// Module scope, so it resets on a page (re)load but survives closing and reopening the widget.
let chatSessionStarted = false;

export default function ChatWidget({
  open,
  setOpen,
  seed,
  context = null,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  seed?: string | null;
  context?: PageContext;
}) {
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [brand, setBrand] = useState("");
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    setMounted(true);
    fetchStore().then((s) => {
      setBrand(s.brand);
      setProducts(s.products);
    });
  }, []);

  useEffect(() => {
    if (token) return;
    let alive = true;
    const controller = new AbortController();
    const connect = (tries = 0) => {
      if (!alive) return;
      const cached = localStorage.getItem("shopping_agent_token");
      if (cached && tokenAlive(cached)) {
        setToken(cached);
        return;
      }
      if (cached) localStorage.removeItem("shopping_agent_token");
      fetch(`${API_BASE}/api/demo-login`, { method: "POST", signal: controller.signal })
        .then((r) => {
          if (r.status === 404) {
            localStorage.removeItem("aster_gate");
            localStorage.removeItem("shopping_agent_token");
            window.location.assign("/");
            return null;
          }
          return r.ok ? r.json() : null;
        })
        .then((d) => {
          if (d?.access_token) localStorage.setItem("shopping_agent_token", d.access_token);
          if (d?.name) localStorage.setItem("shopping_agent_name", d.name);
          const now = localStorage.getItem("shopping_agent_token");
          if (!alive) return;
          if (now) setToken(now);
          else setTimeout(() => connect(tries + 1), tries < 8 ? 500 + Math.random() * 300 : 2000);
        })
        .catch((e) => {
          if (e?.name === "AbortError" || !alive) return;
          setTimeout(() => connect(tries + 1), tries < 8 ? 500 + Math.random() * 300 : 2000);
        });
    };
    connect();
    return () => {
      alive = false;
      controller.abort();
    };
  }, [token]);

  useEffect(() => {
    if (!token || products.length) return;
    let alive = true;
    fetchStore().then((s) => {
      if (!alive) return;
      if (s.brand) setBrand(s.brand);
      if (s.products.length) setProducts(s.products);
    });
    return () => {
      alive = false;
    };
  }, [token, products.length]);

  const short = brand || "智能商城";

  function forceConnect() {
    fetch(`${API_BASE}/api/demo-login`, { method: "POST" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.access_token) {
          localStorage.setItem("shopping_agent_token", d.access_token);
          setToken(d.access_token);
        }
      })
      .catch(() => {});
  }

  function signOut() {
    localStorage.removeItem("shopping_agent_token");
    setToken(null);
  }

  if (!mounted) return null;

  return (
    <>
      {!open && (
        <button
          className="fab"
          onClick={() => setOpen(true)}
          aria-label={`打开${short} AI 助手`}
        >
          <span className="dot" />
          &#128172;
        </button>
      )}
      {open && (
        <section className="panel" role="dialog" aria-label={`${short} AI 助手`}>
          <header className="panel-hdr">
            <Avatar state="idle" size={38} />
            <div>
              <div className="t">{short} AI助手</div>
              <div className="s">
                <span className="online-dot" /> 在线
              </div>
            </div>
            <button className="x" onClick={() => setOpen(false)} aria-label="关闭">
              &times;
            </button>
          </header>
          {token ? (
            <Conversation
              token={token}
              onSignOut={signOut}
              seed={seed}
              brand={short}
              products={products}
              context={context}
            />
          ) : (
            <div className="chat-connecting">
              <Avatar state="thinking" size={34} />
              <p>正在连接 AI 助手...</p>
              <button className="chip" type="button" onClick={forceConnect}>
                重试
              </button>
            </div>
          )}
        </section>
      )}
    </>
  );
}

function Conversation({
  token,
  onSignOut,
  seed,
  brand,
  products,
  context,
}: {
  token: string;
  onSignOut: () => void;
  seed?: string | null;
  brand: string;
  products: Product[];
  context?: PageContext;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      if (typeof window === "undefined") return [];
      if (!chatSessionStarted) {
        chatSessionStarted = true;
        localStorage.removeItem("aster_chat");
        localStorage.removeItem("aster_agent");
        return [];
      }
      const raw = localStorage.getItem("aster_chat");
      const parsed = raw ? JSON.parse(raw) : null;
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [voiceOn, setVoiceOn] = useState(false);
  const [voiceState, setVoiceState] = useState<"greeting" | "listening" | "thinking" | "speaking">(
    "greeting",
  );
  const [heard, setHeard] = useState("");
  const [name, setName] = useState(
    () => (typeof localStorage !== "undefined" && localStorage.getItem("shopping_agent_name")) || "",
  );
  const [agentMode, setAgentMode] = useState<boolean>(() => {
    try {
      return typeof window !== "undefined" && localStorage.getItem("aster_agent") === "1";
    } catch {
      return false;
    }
  });
  const [micOn, setMicOn] = useState(true);
  const streamRef = useRef<HTMLDivElement | null>(null);
  const seededRef = useRef<string | null>(null);
  const lastTopicRef = useRef("");
  const recogRef = useRef<Recognizer | null>(null);
  const voiceLiveRef = useRef(false);
  const processingRef = useRef(false);
  const speakingRef = useRef(false);
  const utterRef = useRef(0);
  const lastSpokenRef = useRef("");
  const spokeEndRef = useRef(0);
  const micDeadRef = useRef(false);
  const micOnRef = useRef(true);
  const handlerRef = useRef<(t: string) => void>(() => {});
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const speakSeqRef = useRef(0);
  const speakDoneRef = useRef<null | (() => void)>(null);
  const [speakLevel, setSpeakLevel] = useState(0);
  const agentModeRef = useRef(false);
  const bargedRef = useRef(false);
  const sessionRef = useRef<string>("");

  useEffect(() => {
    const saved = localStorage.getItem("shopping_agent_session");
    const session = saved || crypto.randomUUID().replaceAll("-", "");
    sessionRef.current = session;
    localStorage.setItem("shopping_agent_session", session);
  }, []);

  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  useEffect(() => {
    fetch(`${API_BASE}/api/suggestions`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        const all = (d.suggestions || []) as Suggestion[];
        const zh = all.filter((s) => s.lang === "zh" || /[\u4e00-\u9fa9]/.test(s.text));
        setSuggestions(zh.length ? zh : all);
      })
      .catch(() => {});
    const saved = localStorage.getItem("aster_name");
    if (saved) setName(saved);
  }, [token]);

  useEffect(() => {
    try {
      if (messages.length) localStorage.setItem("aster_chat", JSON.stringify(messages.slice(-40)));
    } catch {
      /* storage full */
    }
  }, [messages]);

  useEffect(() => {
    agentModeRef.current = agentMode;
    try {
      localStorage.setItem("aster_agent", agentMode ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [agentMode]);

  function clearChat() {
    setMessages([]);
    setAgentMode(false);
    agentModeRef.current = false;
    lastTopicRef.current = "";
    try {
      localStorage.removeItem("aster_chat");
      localStorage.setItem("aster_agent", "0");
      localStorage.removeItem("aster_profile");
      localStorage.removeItem("aster_visited");
      const session = crypto.randomUUID().replaceAll("-", "");
      sessionRef.current = session;
      localStorage.setItem("shopping_agent_session", session);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (seed && seededRef.current !== seed) {
      seededRef.current = seed;
      setInput(seed);
    }
  }, [seed]);

  async function send(q: string): Promise<string> {
    if (!q.trim() || loading) return "";
    // light personalization: remember a name the shopper explicitly gives.
    const nameHit = /(?:my name is|call me|我叫)\s+([\u4e00-\u9fa9A-Za-z][\u4e00-\u9fa9A-Za-z'’\-]{0,19})/i.exec(q);
    const notAName =
      /^(an?|the|me|you|i|it|when|what|where|why|how|who|if|back|now|soon|later|today|tonight|tomorrow|anytime|whenever|asap|about|that|this|please|maybe|not|no|yes|ok|okay|sir|maam|madam|dude|guys?|again|here|there)$/i;
    if (nameHit) {
      const raw = nameHit[1];
      if (/^[\u4e00-\u9fa9]+$/.test(raw) || !notAName.test(raw)) {
        const nm = /^[\u4e00-\u9fa9]+$/.test(raw) ? raw : raw[0].toUpperCase() + raw.slice(1).toLowerCase();
        localStorage.setItem("aster_name", nm);
        setName(nm);
        if (q.trim().length <= nameHit[0].length + 4) {
          const reply = `很高兴认识你，${nm}。今天有什么可以帮您选购的吗？`;
          setInput("");
          setMessages((m) => [...m, { role: "me", text: q }, { role: "bot", text: reply }]);
          return reply;
        }
      }
    }
    const qt = q.trim();
    const asksNature = /^(are|is|am)\s+(you|this|it|i|u)\b/i.test(qt) || /(你是|这是).*(机器人|ai|人工智能|真人|人工)/i.test(qt);
    const shortHuman =
      qt.split(/\s+/).length <= 4 &&
      /(人工客服|转人工|客服|人工|human|agent|representative|real person|advisor|operator|manager|specialist)/i.test(q);
    const verbHuman =
      /(转接|转|找|联系).{0,10}(人工|客服|专员|真人)|(talk|speak|chat|connect|transfer|reach|escalate)\b.{0,20}\b(human|person|agent|representative|rep|advisor|operator|manager|supervisor|specialist)\b/i.test(
        q,
      );
    const refusesHuman =
      /(不用|不需要|不必|别).{0,8}(人工|客服|专员)|(don'?t|do not|never|without|no need|rather not|no thanks?)\b[^.?!]{0,24}\b(human|person|agent|representative|rep|advisor|operator|manager|specialist)\b/i.test(
        q,
      );
    if (!agentMode && !asksNature && !refusesHuman && (shortHuman || verbHuman)) {
      setInput("");
      setMessages((m) => [...m, { role: "me", text: q }, { role: "bot", agent: true, text: AGENT_INTRO }]);
      setAgentMode(true);
      agentModeRef.current = true;
      return AGENT_INTRO;
    }
    const careLike =
      /(订单|退货|退款|快递|物流|损坏|破损|错发|漏发|投诉|取消|账户|账单|扣款|order|return|refund|package|parcel|delivery|tracking|broken|damaged|defect|wrong item|missing|charged|billing|complaint|cancel)/i.test(
        q,
      );
    const shoppingLike =
      /(礼物|礼品|买|购买|购物|推荐|建议|有没有|有什么|搭配|款式|穿搭|尺码表|gift|present|buy|purchase|shopping|looking for|recommend|suggest|show me|outfit|style|size guide)/i.test(
        q,
      );
    let handedBack = false;
    if (agentMode && shoppingLike && !careLike && !verbHuman && !shortHuman && !refusesHuman) {
      setAgentMode(false);
      agentModeRef.current = false;
      handedBack = true;
    }
    const inAgent = agentMode && !handedBack;
    setInput("");
    setMessages((m) => [...m, { role: "me", text: q }, { role: "bot", text: "", agent: inAgent }]);
    setLoading(true);
    let qSend = q;
    if (context?.kind === "product" && !inAgent) {
      const nm = context.name;
      const pronoun = /(它|这个|那件|这款|该商品|it|its|this|that|the one|the item|the product)/i.test(q);
      const stem = (s: string) => s.toLowerCase().replace(/s$/, "");
      const ctxCat = stem(context.category || "");
      const otherThing = products.some((pp) => {
        const c = stem(pp.category || "");
        return (
          !!c && c !== ctxCat && c !== "top" && c !== "bottom" && new RegExp(`\\b${c}s?\\b`, "i").test(q)
        );
      });
      if (pronoun && !otherThing && !q.toLowerCase().includes(nm.toLowerCase())) {
        qSend = `${q}（关于${nm}）`;
      }
    }
    let result = "";
    const patchBot = (fn: (m: Message) => Message) =>
      setMessages((all) => {
        const copy = [...all];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === "bot") {
            copy[i] = fn(copy[i]);
            break;
          }
        }
        return copy;
      });
    const history = messages
      .filter((mm) => mm.text && mm.text.trim())
      .slice(-6)
      .map((mm) => ({ role: mm.role === "me" ? "user" : "assistant", content: mm.text }));
    const shopperNotes = updateShopperProfile(q);
    const ctrl = new AbortController();
    let watchdog = setTimeout(() => ctrl.abort(), 30_000);
    const armIdle = () => {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => ctrl.abort(), 60_000);
    };
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: authHeaders,
        signal: ctrl.signal,
        body: JSON.stringify({
          query: qSend,
          ...(sessionRef.current ? { session_id: sessionRef.current } : {}),
          ...(inAgent ? { persona: "agent" } : {}),
          ...(voiceLiveRef.current ? { concise: true } : {}),
          ...(history.length ? { history } : {}),
          ...(shopperNotes ? { notes: shopperNotes } : {}),
        }),
      });
      if (res.status === 401) {
        const m = "您的会话已过期，正在重新连接，请重新发送。";
        patchBot((b) => ({ ...b, text: m }));
        onSignOut();
        return m;
      }
      if (res.status === 429) {
        const m = "您发送得太快了，请稍后再试。";
        patchBot((b) => ({ ...b, text: m }));
        return m;
      }
      if (!res.ok || !res.body) {
        const m = "抱歉，出了点问题，请重试。";
        patchBot((b) => ({ ...b, text: m }));
        return m;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let received = false;
      let acc = "";
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          armIdle();
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split(/\r?\n\r?\n/);
          buffer = chunks.pop() ?? "";
          for (const chunk of chunks) {
            const line = chunk.trim();
            if (!line.startsWith("data:")) continue;
            let event: StreamEvent;
            try {
              event = JSON.parse(line.slice(5).trim()) as StreamEvent;
            } catch {
              continue;
            }
            received = true;
            if (event.type === "token") {
              acc += event.text;
              patchBot((b) => ({ ...b, text: b.text + event.text }));
            } else if (event.type === "final") {
              const fe = event;
              if (fe.session_id) {
                sessionRef.current = fe.session_id;
                localStorage.setItem("shopping_agent_session", fe.session_id);
              }
              const answer = fe.answer ?? acc;
              result = answer;
              const recs = recsFromAnswer(answer, products);
              const fu = followupsFor(q, fe, recs, suggestions, lastTopicRef.current);
              lastTopicRef.current = fu.topic;
              patchBot((b) => ({
                ...b,
                text: fe.answer ?? b.text,
                final: fe,
                recs,
                followups: fu.followups,
              }));
            } else if (event.type === "error") {
              result = "抱歉，出了点问题。";
              patchBot((b) => ({ ...b, text: result }));
            }
          }
        }
      } finally {
        reader.cancel().catch(() => {});
      }
      if (!received) {
        result = "未收到响应，请重试。";
        patchBot((b) => ({ ...b, text: result }));
      }
    } catch {
      result = "无法连接 AI 助手，请确认 API 是否正在运行。";
      patchBot((b) => ({ ...b, text: result }));
    } finally {
      clearTimeout(watchdog);
      setLoading(false);
    }
    return result;
  }

  async function sendFeedback(idx: number, verdict: "up" | "down") {
    const msg = messages[idx];
    if (!msg?.final?.message_id || msg.feedback) return;
    setMessages((all) => all.map((m, i) => (i === idx ? { ...m, feedback: verdict } : m)));
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ message_id: msg.final.message_id, verdict }),
      });
    } catch {
      /* best effort */
    }
  }

  function escalate() {
    if (agentMode) return;
    setAgentMode(true);
    setMessages((m) => [...m, { role: "bot", agent: true, text: AGENT_INTRO }]);
  }
  function endAgent() {
    setAgentMode(false);
    agentModeRef.current = false;
    setMessages((m) => [
      ...m,
      { role: "bot", text: "已为您切回购物助手。😊 还有什么可以帮您找到的吗？" },
    ]);
  }

  async function speak(text: string, persona?: string): Promise<void> {
    const clean = plainSpeak(text);
    if (!clean) return;
    const seq = ++speakSeqRef.current;
    const ttsCtrl = new AbortController();
    const ttsTimer = setTimeout(() => ttsCtrl.abort(), 8_000);
    try {
      const res = await fetch(`${API_BASE}/api/tts`, {
        method: "POST",
        headers: authHeaders,
        signal: ttsCtrl.signal,
        body: JSON.stringify({ text: clean.slice(0, 1200), persona: persona || null }),
      });
      if (speakSeqRef.current !== seq) {
        clearTimeout(ttsTimer);
        return;
      }
      if (res.ok && res.status !== 204) {
        const blob = await res.blob();
        clearTimeout(ttsTimer);
        const played = await playWithLipSync(blob, seq);
        if (played || speakSeqRef.current !== seq) return;
      } else {
        clearTimeout(ttsTimer);
      }
    } catch {
      clearTimeout(ttsTimer);
    }
    if (speakSeqRef.current !== seq) return;
    let t = 0;
    const iv = window.setInterval(() => {
      if (speakSeqRef.current !== seq) return;
      t += 0.4;
      setSpeakLevel(0.2 + 0.22 * Math.abs(Math.sin(t)));
    }, 90);
    try {
      await speakAsync(clean);
    } finally {
      clearInterval(iv);
      if (speakSeqRef.current === seq) setSpeakLevel(0);
    }
  }

  function playWithLipSync(blob: Blob, seq: number): Promise<boolean> {
    return new Promise((resolve) => {
      if (speakSeqRef.current !== seq) {
        resolve(false);
        return;
      }
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioElRef.current = audio;
      let srcNode: MediaElementAudioSourceNode | null = null;
      let analyser: AnalyserNode | null = null;
      let rafId = 0;
      let played = false;
      let settled = false;
      const finish = (ok: boolean) => {
        if (settled) return;
        settled = true;
        if (rafId) cancelAnimationFrame(rafId);
        try {
          srcNode?.disconnect();
          analyser?.disconnect();
        } catch {
          /* already torn down */
        }
        try {
          URL.revokeObjectURL(url);
        } catch {
          /* ignore */
        }
        if (speakSeqRef.current === seq) setSpeakLevel(0);
        if (audioElRef.current === audio) audioElRef.current = null;
        if (speakDoneRef.current === onBargeIn) speakDoneRef.current = null;
        resolve(ok && played);
      };
      const onBargeIn = () => finish(false);
      speakDoneRef.current = onBargeIn;
      audio.onended = () => finish(true);
      audio.onerror = () => finish(false);
      (async () => {
        try {
          const Ctx =
            window.AudioContext ||
            (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          let ctx = audioCtxRef.current;
          if (!ctx) {
            ctx = new Ctx();
            audioCtxRef.current = ctx;
          }
          if (ctx.state === "suspended") await ctx.resume();
          if (speakSeqRef.current !== seq) {
            finish(false);
            return;
          }
          srcNode = ctx.createMediaElementSource(audio);
          analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          srcNode.connect(analyser);
          analyser.connect(ctx.destination);
          const data = new Uint8Array(analyser.frequencyBinCount);
          let last = 0;
          const tick = () => {
            if (speakSeqRef.current !== seq || settled) return;
            analyser!.getByteTimeDomainData(data);
            let sum = 0;
            for (let i = 0; i < data.length; i++) {
              const v = (data[i] - 128) / 128;
              sum += v * v;
            }
            const level = Math.min(1, Math.sqrt(sum / data.length) * 2.4);
            const now = performance.now();
            if (now - last > 45) {
              setSpeakLevel(Math.round(level * 100) / 100);
              last = now;
            }
            rafId = requestAnimationFrame(tick);
          };
          rafId = requestAnimationFrame(tick);
        } catch {
          /* Web Audio unavailable: play raw */
        }
        try {
          await audio.play();
          played = true;
        } catch {
          finish(false);
        }
      })();
    });
  }

  function stopSpeaking() {
    speakSeqRef.current++;
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    const a = audioElRef.current;
    if (a) {
      try {
        a.pause();
      } catch {
        /* ignore */
      }
      audioElRef.current = null;
    }
    setSpeakLevel(0);
    const done = speakDoneRef.current;
    speakDoneRef.current = null;
    if (done) done();
  }

  async function handleUtterance(text: string) {
    if (!voiceLiveRef.current || !micOnRef.current) return;
    const barged = bargedRef.current;
    bargedRef.current = false;
    if (barged) {
      stopSpeaking();
    } else {
      if (processingRef.current && !speakingRef.current) return;
      if (speakingRef.current) {
        const spoken = new Set(normWords(lastSpokenRef.current));
        const words = normWords(text);
        const overlap = words.length ? words.filter((w) => spoken.has(w)).length / words.length : 0;
        if (words.length < 2) return;
        if (overlap > 0.6) return;
        stopSpeaking();
      } else if (Date.now() - spokeEndRef.current < 1500) {
        const spoken = new Set(normWords(lastSpokenRef.current));
        const words = normWords(text);
        const overlap = words.length ? words.filter((w) => spoken.has(w)).length / words.length : 0;
        if (words.length < 2 || overlap > 0.6) return;
      }
    }
    const myId = ++utterRef.current;
    processingRef.current = true;
    speakingRef.current = false;
    setHeard(text);
    setVoiceState("thinking");
    const answer = await send(text);
    if (!voiceLiveRef.current || myId !== utterRef.current) return;
    speakingRef.current = true;
    const spoken = plainSpeak(answer);
    lastSpokenRef.current = spoken;
    setVoiceState("speaking");
    await speak(spoken, agentModeRef.current ? "agent" : undefined);
    if (myId !== utterRef.current) return;
    speakingRef.current = false;
    spokeEndRef.current = Date.now();
    processingRef.current = false;
    if (voiceLiveRef.current) setVoiceState("listening");
  }
  handlerRef.current = handleUtterance;

  function startListening() {
    const rec = makeRecognizer();
    if (!rec) return;
    rec.lang = "zh-CN";
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    let netErr = 0;
    let hadNetError = false;
    rec.onresult = (e) => {
      let finalText = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        interim += t;
        if (e.results[i].isFinal) finalText += t;
      }
      if (interim.trim()) netErr = 0;
      if (speakingRef.current && micOnRef.current && interim.trim() && typeof window !== "undefined") {
        const spoken = new Set(normWords(lastSpokenRef.current));
        const words = normWords(interim);
        const newWords = words.filter((w) => !spoken.has(w));
        const spokenRaw = " " + lastSpokenRef.current.toLowerCase() + " ";
        const hit = /(停|等等|等一下|别说了|stop|wait|hold on|pause)/i.exec(interim);
        const realInterrupt = !!hit && !spokenRaw.includes(" " + hit[0].toLowerCase() + " ");
        if (newWords.length >= 2 || realInterrupt) {
          stopSpeaking();
          bargedRef.current = true;
        }
      }
      if (finalText.trim()) handlerRef.current(finalText.trim());
    };
    rec.onerror = (e) => {
      const err = e?.error || "";
      if (err === "not-allowed" || err === "service-not-allowed" || err === "audio-capture") {
        micDeadRef.current = true;
        stopVoice();
        setMessages((m) => [
          ...m,
          { role: "bot", text: "无法访问麦克风，请允许麦克风权限，或用文字输入您的问题。" },
        ]);
      } else if (err === "network") {
        hadNetError = true;
        netErr += 1;
        if (netErr >= 3) {
          micDeadRef.current = true;
          stopVoice();
          setMessages((m) => [
            ...m,
            { role: "bot", text: "语音服务暂时无法连接，已关闭麦克风。您可以用文字提问，或稍后再试语音。" },
          ]);
        }
      }
    };
    rec.onend = () => {
      if (!voiceLiveRef.current || micDeadRef.current) return;
      const delay = hadNetError ? 1500 : 0;
      hadNetError = false;
      window.setTimeout(() => {
        if (!voiceLiveRef.current || micDeadRef.current) return;
        try {
          rec.start();
        } catch {
          /* already started */
        }
      }, delay);
    };
    recogRef.current = rec;
    try {
      rec.start();
    } catch {
      /* already started */
    }
  }

  async function startVoice() {
    if (!makeRecognizer()) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: "当前浏览器不支持语音对话，请用文字输入。" },
      ]);
      return;
    }
    setVoiceOn(true);
    voiceLiveRef.current = true;
    processingRef.current = false;
    speakingRef.current = false;
    micDeadRef.current = false;
    micOnRef.current = true;
    setMicOn(true);
    bargedRef.current = false;
    setHeard("");
    setVoiceState("greeting");
    speakingRef.current = true;
    let firstTime = false;
    try {
      firstTime = !localStorage.getItem("aster_visited");
    } catch {
      /* ignore */
    }
    const who = name ? " " + name : "";
    const greeting = agentModeRef.current
      ? `你好${who}，我是客服专员，请问有什么可以帮您？`
      : firstTime
        ? `你好${who}，我是运动品牌集合的 AI 购物助手，很高兴认识你。需要我帮你找什么？`
        : `欢迎回来${who}。今天想找些什么？`;
    lastSpokenRef.current = greeting;
    await speak(greeting, agentModeRef.current ? "agent" : undefined);
    speakingRef.current = false;
    spokeEndRef.current = Date.now();
    if (firstTime && !agentModeRef.current && voiceLiveRef.current) {
      try {
        localStorage.setItem("aster_visited", "1");
      } catch {
        /* ignore */
      }
    }
    if (!voiceLiveRef.current) return;
    setVoiceState("listening");
    startListening();
  }

  function stopVoice() {
    voiceLiveRef.current = false;
    utterRef.current++;
    processingRef.current = false;
    speakingRef.current = false;
    recogRef.current?.abort();
    stopSpeaking();
    setVoiceOn(false);
  }

  function toggleMute() {
    const on = !micOnRef.current;
    micOnRef.current = on;
    setMicOn(on);
  }

  useEffect(() => {
    return () => {
      voiceLiveRef.current = false;
      // eslint-disable-next-line react-hooks/exhaustive-deps
      speakSeqRef.current++;
      recogRef.current?.abort();
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
      audioElRef.current?.pause();
      speakDoneRef.current?.();
      speakDoneRef.current = null;
      audioCtxRef.current?.close().catch(() => {});
      audioCtxRef.current = null;
    };
  }, []);

  const empty = messages.length === 0;
  const voiceLabel =
    voiceState === "greeting"
      ? "说点什么吧..."
      : voiceState === "listening"
        ? "聆听中..."
        : voiceState === "thinking"
          ? "思考中..."
          : "说话中...";

  if (voiceOn) {
    const avatarState: AvatarState =
      voiceState === "speaking" ? "speaking" : voiceState === "thinking" ? "thinking" : "idle";
    const lastBot = [...messages].reverse().find((m) => m.role === "bot" && m.text);
    return (
      <div className="voice">
        <div style={{ width: "100%" }}>
          <div className={`voice-ring ${voiceState}`}>
            <Avatar state={avatarState} size={104} level={speakLevel} persona={agentMode ? "tiffany" : "sara"} />
          </div>
          <div className="state">
            {!micOn && voiceState !== "speaking" ? "麦克风已静音" : voiceLabel}
          </div>
          {(heard || lastBot) && (
            <div className="voice-live">
              {heard && <div className="vl-said">&ldquo;{heard}&rdquo;</div>}
              {lastBot && (
                <div className="vl-ans">
                  <Markdown text={lastBot.text} products={products} />
                </div>
              )}
              {lastBot?.recs && lastBot.recs.length > 0 && (
                <div className="recs">
                  {lastBot.recs.map((p) => (
                    <Link key={p.id} className="rec" href={`/product/${p.id}`}>
                      <ImageTile category={p.category} color={p.color} name={p.name} className="rec-img" />
                      <div className="rb">
                        <div className="rn">{p.name}</div>
                        <div className="rp">{p.price != null ? `¥${p.price.toFixed(0)}` : ""}</div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="voice-hint">您可以随时说话，甚至可以中途打断我。</div>
        </div>
        <div className="voice-controls">
          <button
            className={micOn ? "icon-btn" : "icon-btn muted"}
            onClick={toggleMute}
            aria-label={micOn ? "静音麦克风" : "取消静音"}
            title={micOn ? "静音" : "取消静音"}
          >
            {micOn ? "🎤" : "🔇"}
          </button>
          <button className="btn btn-primary" onClick={stopVoice}>
            结束
          </button>
        </div>
      </div>
    );
  }

  // context-aware openers, so the first prompts match the page the shopper came from
  const short2 = (s: string) => s;
  const ctxSuggest: string[] =
    context?.kind === "product"
      ? [`${short2(context.name)}适合我吗？`, "尺码标准吗？", "有货吗？"]
      : context?.kind === "category"
        ? [`适合冷天的${categoryLabel(context.category)}？`, `100元以内的${categoryLabel(context.category)}`]
        : context?.kind === "help"
          ? [`请告诉我更多关于${helpTopicLabel(context.topic)}的信息`]
          : [];
  const ctxLabel =
    context?.kind === "product"
      ? `正在查看：${short2(context.name)}`
      : context?.kind === "category"
        ? `正在浏览：${categoryLabel(context.category)}`
        : context?.kind === "help"
          ? `帮助 · ${helpTopicLabel(context.topic)}`
          : "";

  return (
    <>
      {agentMode && (
        <div className="agent-banner">
          <span>
            <b>客服专员</b> · {brand}
          </span>
          <button onClick={endAgent}>返回购物助手</button>
        </div>
      )}
      {!agentMode && messages.length > 0 && (
        <div className="chat-toolbar">
          <button className="chat-clear" onClick={clearChat}>
            清空对话
          </button>
        </div>
      )}
      <div
        className="stream"
        ref={streamRef}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="对话"
      >
        {empty && (
          <div className="greet">
            {ctxLabel && <div className="ctx-chip">{ctxLabel}</div>}
            <div className="big">
              {name ? `欢迎回来，${name}！` : "你好，"}我是{brand ? "AI 购物助手" : "您的助手"}。😊
            </div>
            {context?.kind === "product"
              ? `对${short2(context.name)}有任何疑问吗？我可以帮您了解版型、颜色、尺码、库存或穿搭效果。`
              : context?.kind === "category"
                ? `正在浏览${categoryLabel(context.category)}？我可以帮您找到合适的商品、对比选项或查询尺码。您最看重什么？`
                : "今天有什么可以帮您的？可以问我商品、尺码、配送、礼物推荐或穿搭建议，也可以点麦克风进行语音对话。"}
          </div>
        )}
        {empty && (
          <div className="sugg">
            {[...ctxSuggest, ...suggestions.map((s) => s.text)].slice(0, 5).map((t, i) => (
              <button key={`${i}-${t}`} type="button" onClick={() => send(t)}>
                {t}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{ display: "contents" }}>
            {m.role === "bot" && !m.text && loading ? (
              <div className="msg bot think typing">
                <Avatar state="thinking" size={22} persona={agentMode ? "tiffany" : "sara"} />
                <span className="dots">
                  <i /><i /><i />
                </span>
              </div>
            ) : (
              <>
                {m.agent && <div className="agent-tag">客服专员</div>}
                <div className={`msg ${m.role}${m.agent ? " agent" : ""}`}>
                  {m.role === "bot" ? <Markdown text={m.text} products={m.recs ?? products} /> : m.text}
                </div>
              </>
            )}
            {m.final && (
              <div className="meta-row">
                {dedupeCites(m.final.citations).map((c) => (
                  <span key={c.n} className="cite" title={c.id}>
                    {citeLabel(c)}
                  </span>
                ))}
                {m.final.message_id && (
                  <span className="thumbs">
                    <button
                      aria-label="有帮助"
                      disabled={!!m.feedback}
                      onClick={() => sendFeedback(i, "up")}
                    >
                      &#128077;
                    </button>
                    <button
                      aria-label="没帮助"
                      disabled={!!m.feedback}
                      onClick={() => sendFeedback(i, "down")}
                    >
                      &#128078;
                    </button>
                    {m.feedback && <span>谢谢</span>}
                  </span>
                )}
              </div>
            )}
            {i === messages.length - 1 && m.final?.tier === "abstain" && !agentMode && (
              <button className="escalate-btn" type="button" onClick={escalate}>
                💬 转人工客服
              </button>
            )}
            {m.recs && m.recs.length > 0 && (
              <div className="recs">
                {m.recs.map((p) => (
                  <Link key={p.id} className="rec" href={`/product/${p.id}`}>
                    <ImageTile category={p.category} color={p.color} name={p.name} className="rec-img" />
                    <div className="rb">
                      <div className="rn">{p.name}</div>
                      <div className="rp">
                        {categoryLabel(p.category)}
                        {p.price != null ? ` · ¥${p.price.toFixed(0)}` : ""}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            {m.followups && m.followups.length > 0 && (
              <div className="sugg">
                {m.followups.map((f, k) => (
                  <button key={k} type="button" onClick={() => send(f)}>
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <button
          type="button"
          className="icon-btn"
          onClick={startVoice}
          aria-label="开始语音对话"
          title="与助手对话"
        >
          🎙
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="问我商品、尺码、配送..."
          aria-label="您的问题"
        />
        <button type="submit" className="icon-btn send" disabled={loading} aria-label="发送">
          &#8593;
        </button>
      </form>
      <span className="chat-credit">基于 Agentic RAG 构建</span>
    </>
  );
}
