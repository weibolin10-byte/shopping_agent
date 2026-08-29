"use client";

import InfoPage from "../InfoPage";

// All contact details are synthetic. The phone numbers are deliberately fake (repeated-digit demo
// numbers) so nobody dials a real line.
const CHANNELS = [
  { label: "客服电话", value: "400-888-0000", note: "每日 9:00-21:00（北京时间）" },
  { label: "免费热线", value: "800-820-0000", note: "全国免长途费" },
  { label: "电子邮箱", value: "support@sportbrand.demo", note: "1个工作日内回复" },
  { label: "在线客服", value: "右下角 AI 助手", note: "全天候即时响应" },
];

export default function ContactPage() {
  return (
    <InfoPage
      title="联系我们"
      intro="人工客服每周7天在线。AI 助手可即时解答大部分问题，需要时可为您转接人工专员。"
    >
      <div className="help-grid">
        {CHANNELS.map((c) => (
          <section key={c.label} className="help-card">
            <h3>{c.label}</h3>
            <p className="contact-value">{c.value}</p>
            <p className="info-note" style={{ margin: 0 }}>
              {c.note}
            </p>
          </section>
        ))}
      </div>

      <div className="info-sec">
        <h3>转接人工</h3>
        <p>
          在 AI 助手中输入 <strong>&quot;转人工&quot;</strong>，即可转接客服专员。
          提供您的邮箱，专员可以调取您的订单记录，继续为您处理。
        </p>
        <p className="info-note">
          以上为演示项目的联系方式，电话号码均为虚构，请勿拨打。
        </p>
      </div>
    </InfoPage>
  );
}
