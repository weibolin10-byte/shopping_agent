"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { FREE_SHIP, useCart } from "../cart";
import { fetchStore } from "../catalog";
import { useRequireGate } from "../gate";
import StoreFooter from "../StoreFooter";
import StoreHeader from "../StoreHeader";

export default function CheckoutPage() {
  const gateOk = useRequireGate();
  const { lines, subtotal, clear } = useCart();
  const [brand, setBrand] = useState("");
  const [done, setDone] = useState<string | null>(null);
  useEffect(() => {
    fetchStore().then((s) => setBrand(s.brand));
  }, []);
  if (!gateOk) return null;

  const shipping = subtotal >= FREE_SHIP || subtotal === 0 ? 0 : 8;

  function placeOrder(e: React.FormEvent) {
    e.preventDefault();
    const order = "AS" + Math.floor(100000 + Math.random() * 900000);
    clear();
    setDone(order);
  }

  if (done) {
    return (
      <>
        <StoreHeader brand={brand} />
        <main className="checkout done">
          <div className="confirm">
            <div className="check">✓</div>
            <h1>订单已确认</h1>
            <p>
              感谢您的订购。确认单号 <strong>{done}</strong> 已发送至您的邮箱。
            </p>
            <p className="section-sub">
              上海发货，商品出库后您将收到物流跟踪信息。
            </p>
            <Link href="/" className="btn btn-primary">
              继续购物
            </Link>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <StoreHeader brand={brand} />
      <main className="checkout">
        <h1>结算</h1>
        {lines.length === 0 ? (
          <p className="section-sub">
            购物车是空的。<Link href="/">去逛逛</Link>。
          </p>
        ) : (
          <form className="co-grid" onSubmit={placeOrder}>
            <div className="co-fields">
              <h3>联系方式</h3>
              <input required type="email" placeholder="邮箱" aria-label="邮箱" />
              <h3>收货地址</h3>
              <input required placeholder="收货人姓名" aria-label="收货人姓名" />
              <input required placeholder="详细地址" aria-label="详细地址" />
              <div className="co-2">
                <input required placeholder="城市" aria-label="城市" />
                <input required placeholder="邮政编码" aria-label="邮政编码" />
              </div>
              <select aria-label="省份" defaultValue="SH">
                <option value="SH">上海</option>
                <option value="BJ">北京</option>
                <option value="GD">广东</option>
                <option value="ZJ">浙江</option>
                <option value="JS">江苏</option>
                <option value="OTHER">其他</option>
              </select>
              <h3>支付方式</h3>
              <input required placeholder="银行卡号" aria-label="银行卡号" inputMode="numeric" />
              <div className="co-2">
                <input required placeholder="有效期 MM / YY" aria-label="有效期" />
                <input required placeholder="CVC" aria-label="CVC" />
              </div>
              <p className="co-note">演示结算，不会产生真实支付。</p>
            </div>
            <aside className="co-summary">
              <h3>订单</h3>
              {lines.map((l) => (
                <div key={`${l.id}-${l.size}-${l.color}`} className="co-line">
                  <span>
                    {l.name} × {l.qty}
                  </span>
                  <span>¥{(l.price * l.qty).toFixed(0)}</span>
                </div>
              ))}
              <div className="co-line">
                <span>运费</span>
                <span>{shipping === 0 ? "包邮" : `¥${shipping}`}</span>
              </div>
              <div className="co-line co-total">
                <span>合计</span>
                <span>¥{(subtotal + shipping).toFixed(0)}</span>
              </div>
              <button type="submit" className="btn btn-primary co-pay">
                提交订单
              </button>
            </aside>
          </form>
        )}
      </main>
      <StoreFooter brand={brand} />
    </>
  );
}
