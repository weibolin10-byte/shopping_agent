"use client";

import InfoPage from "../InfoPage";

const PERKS = [
  { title: "积分累积", body: "消费1元积1分，积分可在结算时抵扣现金。" },
  { title: "优先购", body: "新品上架及补货优先购买，先人一步。" },
  { title: "会员运费优惠", body: "专属包邮门槛及会员限定运费优惠。" },
  { title: "生日礼券", body: "生日当月专享折扣好礼。" },
];

export default function MembershipPage() {
  return (
    <InfoPage
      title="会员中心"
      intro="免费加入，无需绑卡。每笔订单都能累积积分，优先体验新品。"
      ask="会员有哪些权益？"
    >
      <div className="help-grid">
        {PERKS.map((p) => (
          <section key={p.title} className="help-card">
            <h3>{p.title}</h3>
            <p>{p.body}</p>
          </section>
        ))}
      </div>

      <div className="info-sec">
        <h3>首单优惠</h3>
        <p>
          加入会员或订阅邮件即可享受首单85折，结算时自动抵扣。学生、医护人员及急救人员
          经认证后全年享受85折优惠。
        </p>
      </div>
    </InfoPage>
  );
}
