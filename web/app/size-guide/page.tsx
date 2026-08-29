"use client";

import InfoPage from "../InfoPage";

// Body measurements in centimeters. Fit notes match what the reviews and occasion guides say, so the
// assistant and the chart agree.
const TOPS = [
  { size: "XS", chest: "79-84", waist: "61-66" },
  { size: "S", chest: "86-91", waist: "69-74" },
  { size: "M", chest: "94-99", waist: "76-81" },
  { size: "L", chest: "102-107", waist: "84-89" },
  { size: "XL", chest: "109-114", waist: "91-97" },
];
const BOTTOMS = [
  { size: "XS", waist: "61-66", hip: "86-91" },
  { size: "S", waist: "69-74", hip: "94-99" },
  { size: "M", waist: "76-81", hip: "102-107" },
  { size: "L", waist: "84-89", hip: "109-114" },
  { size: "XL", waist: "91-97", hip: "117-122" },
];

export default function SizeGuidePage() {
  return (
    <InfoPage
      title="尺码表"
      intro="以下为身体尺寸（厘米），非服装尺寸。介于两个尺码之间？紧身裤为压缩版型略偏小，喜欢宽松建议选大一码；外套如需内搭建议选大一码。"
      ask="我介于两个尺码之间，应该怎么选？"
    >
      <div className="info-sec">
        <h3>上装、运动内衣及外套</h3>
        <table className="sizetable">
          <thead>
            <tr>
              <th>尺码</th>
              <th>胸围（cm）</th>
              <th>腰围（cm）</th>
            </tr>
          </thead>
          <tbody>
            {TOPS.map((r) => (
              <tr key={r.size}>
                <td>{r.size}</td>
                <td>{r.chest}</td>
                <td>{r.waist}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="info-sec">
        <h3>紧身裤、短裤及运动裤</h3>
        <table className="sizetable">
          <thead>
            <tr>
              <th>尺码</th>
              <th>腰围（cm）</th>
              <th>臀围（cm）</th>
            </tr>
          </thead>
          <tbody>
            {BOTTOMS.map((r) => (
              <tr key={r.size}>
                <td>{r.size}</td>
                <td>{r.waist}</td>
                <td>{r.hip}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="info-note">
          包袋及大部分配饰为均码。紧身裤为压缩版型，喜欢宽松建议选大一码。每个商品页面会标注该商品的版型偏大或偏小。
        </p>
      </div>
    </InfoPage>
  );
}
