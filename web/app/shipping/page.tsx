"use client";

import InfoPage from "../InfoPage";

// Delivery estimates match the company_knowledge / occasions docs the assistant retrieves, so the
// page and the chatbot never disagree.
const RATES = [
  { name: "标准配送", price: "满150元包邮，否则8元", time: "2-8 个工作日" },
  { name: "加急配送", price: "15元", time: "1-2 个工作日" },
];
const CITIES = [
  { city: "上海及长三角", time: "1-2 个工作日" },
  { city: "北京及华北", time: "2-3 个工作日" },
  { city: "广州及华南", time: "2-3 个工作日" },
  { city: "成都及西南", time: "3-4 个工作日" },
  { city: "其他地区", time: "3-8 个工作日" },
];

export default function ShippingPage() {
  return (
    <InfoPage
      title="配送说明"
      intro="上海发货，全国配送。满150元包邮，支持加急配送。"
      ask="配送方式有哪些？大概需要多长时间？"
    >
      <div className="info-sec">
        <h3>运费标准</h3>
        <table className="sizetable">
          <thead>
            <tr>
              <th>配送方式</th>
              <th>费用</th>
              <th>预计时效</th>
            </tr>
          </thead>
          <tbody>
            {RATES.map((r) => (
              <tr key={r.name}>
                <td>{r.name}</td>
                <td>{r.price}</td>
                <td>{r.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="info-sec">
        <h3>各地区预计送达时间</h3>
        <table className="sizetable">
          <thead>
            <tr>
              <th>目的地</th>
              <th>标准配送</th>
            </tr>
          </thead>
          <tbody>
            {CITIES.map((c) => (
              <tr key={c.city}>
                <td>{c.city}</td>
                <td>{c.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="info-note">
          订单发货后，您将收到包含物流跟踪链接的邮件。天气及物流原因可能导致延迟1-2天；如遇物流异常，可向 AI 助手提供邮箱查询状态。
        </p>
      </div>
    </InfoPage>
  );
}
