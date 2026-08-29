"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { FREE_SHIP, useCart } from "../cart";
import { fetchStore } from "../catalog";
import { useRequireGate } from "../gate";
import StoreFooter from "../StoreFooter";
import StoreHeader from "../StoreHeader";

export default function CartPage() {
  const gateOk = useRequireGate();
  const { lines, subtotal, setQty, remove } = useCart();
  const [brand, setBrand] = useState("");
  useEffect(() => {
    fetchStore().then((s) => setBrand(s.brand));
  }, []);
  if (!gateOk) return null;

  const toFree = Math.max(0, FREE_SHIP - subtotal);
  const shipping = subtotal >= FREE_SHIP || subtotal === 0 ? 0 : 8;

  return (
    <>
      <StoreHeader brand={brand} />
      <main className="cartpage">
        <h1>购物车</h1>
        {lines.length === 0 ? (
          <p className="section-sub">
            购物车是空的。<Link href="/">去逛逛</Link>。
          </p>
        ) : (
          <div className="cart-grid">
            <div className="cart-lines">
              {lines.map((l) => (
                <div key={`${l.id}-${l.size}-${l.color}`} className="cart-line">
                  <div className="cl-info">
                    <div className="cl-name">{l.name}</div>
                    <div className="cl-meta">
                      {l.color} · 尺码 {l.size}
                    </div>
                  </div>
                  <div className="cl-qty">
                    <button onClick={() => setQty(l.id, l.size, l.color, l.qty - 1)} aria-label="减少">
                      −
                    </button>
                    <span>{l.qty}</span>
                    <button onClick={() => setQty(l.id, l.size, l.color, l.qty + 1)} aria-label="增加">
                      +
                    </button>
                  </div>
                  <div className="cl-price">¥{(l.price * l.qty).toFixed(0)}</div>
                  <button
                    className="cl-remove"
                    onClick={() => remove(l.id, l.size, l.color)}
                    aria-label="移除"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
            <aside className="cart-summary">
              <div className="cs-row">
                <span>小计</span>
                <span>¥{subtotal.toFixed(0)}</span>
              </div>
              <div className="cs-row">
                <span>运费</span>
                <span>{shipping === 0 ? "包邮" : `¥${shipping}`}</span>
              </div>
              {toFree > 0 && (
                <div className="cs-free">再买 ¥{toFree.toFixed(0)} 即可包邮</div>
              )}
              <div className="cs-row cs-total">
                <span>合计</span>
                <span>¥{(subtotal + shipping).toFixed(0)}</span>
              </div>
              <Link href="/checkout" className="btn btn-primary cs-checkout">
                去结算
              </Link>
              <Link href="/" className="cs-continue">
                继续购物
              </Link>
            </aside>
          </div>
        )}
      </main>
      <StoreFooter brand={brand} />
    </>
  );
}
