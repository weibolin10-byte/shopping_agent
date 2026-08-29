"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useCart } from "../../cart";
import { categoryLabel, colorHex, fetchProduct, fetchStore, ProductDetail } from "../../catalog";
import { useChat } from "../../ChatProvider";
import { useRequireGate } from "../../gate";
import ImageTile from "../../ImageTile";
import StoreFooter from "../../StoreFooter";
import StoreHeader from "../../StoreHeader";

export default function ProductPage({ params }: { params: { id: string } }) {
  const gateOk = useRequireGate();
  const [p, setP] = useState<ProductDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [brand, setBrand] = useState("");
  const [size, setSize] = useState("");
  const [color, setColor] = useState("");
  const [added, setAdded] = useState(false);
  const { add } = useCart();
  const { openWith, setContext } = useChat();

  useEffect(() => {
    fetchProduct(params.id).then((d) => {
      if (!d) {
        setMissing(true);
        return;
      }
      setP(d);
      setSize(d.sizes[0] || "OS");
      setColor(d.color || (d.colors && d.colors[0]) || "");
    });
    fetchStore().then((s) => setBrand(s.brand));
  }, [params.id]);

  useEffect(() => {
    if (p) setContext({ kind: "product", id: p.id, name: p.name, category: p.category });
    return () => setContext(null);
  }, [p, setContext]);

  if (!gateOk) return null; // redirecting to the landing gate
  if (missing) {
    return (
      <>
        <StoreHeader brand={brand} />
        <main className="pdp">
          <p className="section-sub">
            未找到该商品。<Link href="/">返回商店</Link>。
          </p>
        </main>
      </>
    );
  }
  if (!p) {
    return (
      <>
        <StoreHeader brand={brand} />
        <main className="pdp">
          <p className="section-sub">正在加载...</p>
        </main>
      </>
    );
  }

  const short = p.name;
  const stock = p.stock ?? 0;
  const stockLabel = stock <= 0 ? "暂时缺货" : stock < 10 ? `库存紧张，仅剩 ${stock} 件` : "现货充足";

  const addToCart = () => {
    add({ id: p.id, name: p.name, price: p.price || 0, color, size });
    setAdded(true);
    setTimeout(() => setAdded(false), 1400);
  };

  return (
    <>
      <StoreHeader brand={brand} />
      <main className="pdp">
        <div className="pdp-media">
          <ImageTile category={p.category} color={color} name={p.name} className="pdp-tile" />
        </div>
        <div className="pdp-info">
          <Link href="/" className="back">
            ← 返回商店
          </Link>
          <h1>{short}</h1>
          <div className="pdp-meta">
            {categoryLabel(p.category)}
            {p.gender && p.gender !== "unisex" ? ` · ${p.gender === "women" ? "女士" : p.gender === "men" ? "男士" : p.gender}` : ""}
            {p.weather ? ` · ${p.weather}` : ""}
          </div>
          <div className="pdp-price">{p.price != null ? `¥${p.price.toFixed(0)}` : ""}</div>
          <p className={`pdp-stock ${stock <= 0 ? "out" : stock < 10 ? "low" : "ok"}`}>{stockLabel}</p>
          {p.description && <p className="pdp-desc">{p.description}</p>}

          {p.colors && p.colors.length > 0 && (
            <div className="pdp-opts">
              <div className="opt-label">颜色：{color}</div>
              <div className="opt-row">
                {p.colors.map((c) => (
                  <button
                    key={c}
                    className={`sw-pick ${c === color ? "on" : ""}`}
                    style={{ background: colorHex(c) }}
                    onClick={() => setColor(c)}
                    aria-label={c}
                    title={c}
                  />
                ))}
              </div>
            </div>
          )}

          <div className="pdp-opts">
            <div className="opt-label">尺码</div>
            <div className="opt-row">
              {p.sizes.map((s) => (
                <button
                  key={s}
                  className={`size-pick ${s === size ? "on" : ""}`}
                  onClick={() => setSize(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="pdp-actions">
            <button className="btn btn-primary" onClick={addToCart} disabled={stock <= 0}>
              {added ? "已加入购物车 ✓" : stock <= 0 ? "暂时缺货" : "加入购物车"}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() =>
                openWith(`${short} 适合我吗？`, {
                  kind: "product",
                  id: p.id,
                  name: p.name,
                  category: p.category,
                })
              }
            >
              问问这件商品
            </button>
          </div>

          {p.reviews && p.reviews.length > 0 && (
            <div className="pdp-reviews">
              <h3>用户评价</h3>
              {p.reviews.map((r, i) => (
                <div key={i} className="review">
                  <span className="stars">{"★".repeat(r.rating || 5)}</span>
                  <span>{r.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
      <StoreFooter brand={brand} />
    </>
  );
}
