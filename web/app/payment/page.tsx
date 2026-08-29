"use client";

import InfoPage from "../InfoPage";

const METHODS = [
  "微信支付",
  "支付宝",
  "银联卡",
  "Visa",
  "Mastercard",
  "Apple Pay",
  "花呗分期",
  "京东白条",
];

export default function PaymentPage() {
  return (
    <InfoPage
      title="支付方式"
      intro="支持多种支付方式，安全加密保障交易。所有价格以人民币（¥）结算。"
      ask="支持哪些支付方式？"
    >
      <div className="info-sec">
        <h3>支持的支付方式</h3>
        <div className="pill-row">
          {METHODS.map((m) => (
            <span key={m} className="pill">
              {m}
            </span>
          ))}
        </div>
      </div>

      <div className="info-sec">
        <h3>分期付款</h3>
        <p>
          满50元订单可使用花呗分期，享受3-12期免息分期，结算时选择即可。查询额度不影响信用评分。
        </p>
      </div>

      <div className="info-sec">
        <h3>安全保障</h3>
        <p>
          所有支付通过加密连接处理，我们不会存储您的完整卡号。订单发货时才会扣款，下单时仅做预授权。
          本平台为演示商店，请勿输入真实支付信息。
        </p>
      </div>
    </InfoPage>
  );
}
