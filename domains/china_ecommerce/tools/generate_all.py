#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成锐风运动中文领域数据包的所有文件。"""

import csv
import json
import os
import random
from datetime import date, timedelta

random.seed(42)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRUCTURED = os.path.join(BASE, "seed", "structured")
UNSTRUCTURED = os.path.join(BASE, "seed", "unstructured")
EVAL = os.path.join(BASE, "eval")

# ============================================================
# 产品定义
# ============================================================
# 每个产品: (基础名, category, gender, price, color, colors, weather, supplier_id, sizes)
PRODUCTS = [
    # 紧身裤 leggings (女款, 5个)
    ("锐风流云紧身裤", "leggings", "women", 199, "黑色", "黑色|藏青|深紫", "all-season", "SUP01", ["S", "M", "L"]),
    ("锐风透气紧身裤", "leggings", "women", 159, "薄荷绿", "薄荷绿|炭灰|黑色", "hot", "SUP02", ["S", "M", "L"]),
    ("锐风轻盈瑜伽裤", "leggings", "women", 179, "深灰", "深灰|雾蓝|豆沙粉", "all-season", "SUP01", ["S", "M", "L"]),
    ("锐风压缩跑步裤", "leggings", "women", 229, "黑色", "黑色|藏青|深灰", "cold", "SUP02", ["S", "M", "L"]),
    ("锐风高腰健身裤", "leggings", "women", 189, "黑色", "黑色|墨绿|酒红", "mild", "SUP01", ["S", "M", "L"]),
    # 女款上衣 tops (4个)
    ("锐风速干T恤", "tops", "women", 89, "白色", "白色|黑色|薄荷绿", "hot", "SUP02", ["S", "M", "L"]),
    ("锐风透气背心", "tops", "women", 69, "白色", "白色|黑色|灰色", "hot", "SUP01", ["S", "M", "L"]),
    ("锐风美利奴长袖", "tops", "women", 159, "燕麦色", "燕麦色|黑色|墨绿", "cold", "SUP02", ["S", "M", "L"]),
    ("锐风训练长袖", "tops", "women", 119, "白色", "白色|深灰|藏青", "mild", "SUP02", ["S", "M", "L"]),
    # 男款上衣 tops (3个)
    ("锐风男士速干T恤", "tops", "men", 99, "黑色", "黑色|深灰|藏青", "hot", "SUP02", ["M", "L", "XL"]),
    ("锐风男士训练背心", "tops", "men", 79, "黑色", "黑色|白色|深灰", "hot", "SUP01", ["M", "L", "XL"]),
    ("锐风男士美利奴长袖", "tops", "men", 169, "炭灰", "炭灰|黑色|军绿", "cold", "SUP02", ["M", "L", "XL"]),
    # 女款卫衣 hoodies (2个)
    ("锐风云感卫衣", "hoodies", "women", 199, "浅灰", "浅灰|黑色|燕麦色", "mild", "SUP01", ["S", "M", "L"]),
    ("锐风拉链连帽衫", "hoodies", "women", 229, "黑色", "黑色|深灰|雾霾蓝", "cold", "SUP02", ["S", "M", "L"]),
    # 男款卫衣 hoodies (2个)
    ("锐风男士经典卫衣", "hoodies", "men", 209, "深灰", "深灰|黑色|藏青", "mild", "SUP01", ["M", "L", "XL"]),
    ("锐风男士拉链连帽衫", "hoodies", "men", 249, "黑色", "黑色|军绿|炭灰", "cold", "SUP02", ["M", "L", "XL"]),
    # 外套 jackets (3个)
    ("锐风防水冲锋衣", "jackets", "unisex", 359, "黑色", "黑色|藏青|军绿", "rain", "SUP02", ["M", "L", "XL"]),
    ("锐风轻薄羽绒服", "jackets", "unisex", 399, "黑色", "黑色|深灰|藏青", "cold", "SUP02", ["M", "L", "XL"]),
    ("锐风防风夹克", "jackets", "unisex", 269, "黑色", "黑色|深灰|雾霾蓝", "mild", "SUP01", ["M", "L", "XL"]),
    # 短裤 shorts (3个)
    ("锐风跑步短裤", "shorts", "women", 89, "黑色", "黑色|藏青|深灰", "hot", "SUP01", ["S", "M", "L"]),
    ("锐风运动短裤", "shorts", "men", 79, "黑色", "黑色|深灰|军绿", "hot", "SUP01", ["M", "L", "XL"]),
    ("锐风竞速短裤", "shorts", "men", 99, "藏青", "藏青|黑色|深灰", "hot", "SUP02", ["M", "L", "XL"]),
    # 运动内衣 bras (2个)
    ("锐风高强支撑内衣", "bras", "women", 119, "黑色", "黑色|深灰|藏青", "all-season", "SUP01", ["S", "M", "L"]),
    ("锐风轻盈瑜伽内衣", "bras", "women", 89, "豆沙粉", "豆沙粉|黑色|薄荷绿", "hot", "SUP02", ["S", "M", "L"]),
    # 包袋 bags (2个, OS)
    ("锐风运动腰包", "bags", "unisex", 79, "黑色", "黑色|深灰|军绿", "all-season", "SUP01", ["OS"]),
    ("锐风训练背包", "bags", "unisex", 199, "黑色", "黑色|深灰|藏青", "all-season", "SUP02", ["OS"]),
    # 配件 accessories (3个, OS)
    ("锐风运动帽", "accessories", "unisex", 59, "黑色", "黑色|深灰|白色", "all-season", "SUP01", ["OS"]),
    ("锐风运动袜三双装", "accessories", "unisex", 69, "黑色", "黑色|白色|灰色", "all-season", "SUP01", ["OS"]),
    ("锐风保暖针织帽", "accessories", "unisex", 69, "黑色", "黑色|深灰|燕麦色", "cold", "SUP02", ["OS"]),
]

# 产品中文描述模板
PRODUCT_DESCRIPTIONS = {
    "锐风流云紧身裤": "锐风流云紧身裤。采用高弹磨毛针织面料，高腰设计不移位，四向弹力贴合身形，深蹲不透光。适合跑步、瑜伽、日常训练等多场景穿着。价格199元，有黑色、藏青、深紫三色。冷水洗涤，避免烘干，以保持压缩弹性。",
    "锐风透气紧身裤": "锐风透气紧身裤。后腰网眼透气设计，速干排汗面料让炎热天气运动不再闷热。修身剪裁，侧缝口袋可放手机。价格159元，有薄荷绿、炭灰、黑色三色。冷水机洗，悬挂晾干。",
    "锐风轻盈瑜伽裤": "锐风轻盈瑜伽裤。裸感面料轻盈如第二层肌肤，超高腰设计收腹提臀，剪裁流畅无缝摩擦。专为瑜伽、普拉提和低强度训练设计。价格179元，有深灰、雾蓝、豆沙粉三色。冷水轻柔洗涤，平铺晾干。",
    "锐风压缩跑步裤": "锐风压缩跑步裤。梯度压缩面料支撑腿部肌肉，减少长距离跑步震颤，后腰口袋可存放能量胶和钥匙。加绒内里适合秋冬晨跑。价格229元，有黑色、藏青、深灰三色。冷水洗涤，不要使用柔顺剂。",
    "锐风高腰健身裤": "锐风高腰健身裤。宽边高腰设计稳固不下滑，中等压缩度兼顾塑形与舒适，侧边条纹增加设计感。适合健身房力量训练和有氧运动。价格189元，有黑色、墨绿、酒红三色。冷水洗涤，反面清洗保持面料光滑。",
    "锐风速干T恤": "锐风速干T恤。后背透气孔设计，超轻速干面料快速排汗，女款修身剪裁搭配弧形下摆。适合炎热天气跑步和户外训练。价格89元，有白色、黑色、薄荷绿三色。悬挂晾干即可保持版型。",
    "锐风透气背心": "锐风透气背心。无袖设计解放双臂，网眼面料透气散热，宽松版型不贴身。适合高温瑜伽和健身房训练。价格69元，有白色、黑色、灰色三色。冷水机洗，快速晾干。",
    "锐风美利奴长袖": "锐风美利奴长袖。细支美利奴羊毛调节体温，多次穿着仍无异味，拇指扣袖口方便叠穿。可作冬季跑步打底或单穿搭配运动裤。价格159元，有燕麦色、黑色、墨绿三色。冷水洗涤，平铺晾干。",
    "锐风训练长袖": "锐风训练长袖。弹力速干面料，肩部无缝设计减少摩擦，拇指孔设计增加包覆。适合春秋户外训练和健身房。价格119元，有白色、深灰、藏青三色。冷水洗涤，避免高温烘干。",
    "锐风男士速干T恤": "锐风男士速干T恤。透气网眼后背，超轻速干针织面料，男款常规版型适合各类运动。高温天跑步和训练的首选。价格99元，有黑色、深灰、藏青三色。悬挂晾干即可保持版型。",
    "锐风男士训练背心": "锐风男士训练背心。宽肩带设计不勒肩，速干面料透气排汗，直筒剪裁适合力量训练。价格79元，有黑色、白色、深灰三色。冷水机洗，快速晾干。",
    "锐风男士美利奴长袖": "锐风男士美利奴长袖。细支美利奴羊毛天然调温抑菌，男款合身剪裁，拇指扣袖口可叠穿外套。冬季户外运动的理想打底。价格169元，有炭灰、黑色、军绿三色。冷水羊毛档洗涤，平铺晾干。",
    "锐风云感卫衣": "锐风云感卫衣。中磅抓绒内里柔软如云朵，女款微短款版型搭配宽大帽兜，春秋早晚的舒适外层。价格199元，有浅灰、黑色、燕麦色三色。反面冷水机洗，低温烘干可保持绒面。",
    "锐风拉链连帽衫": "锐风拉链连帽衫。全拉链设计方便穿脱，加绒内里保暖，修身不臃肿，高领护颈。适合秋冬户外运动前后保暖。价格229元，有黑色、深灰、雾霾蓝三色。冷水洗涤，拉链拉上后清洗。",
    "锐风男士经典卫衣": "锐风男士经典卫衣。中重磅棉混纺抓绒，男款常规版型，袋鼠口袋和罗纹袖口，日常和运动两穿。价格209元，有深灰、黑色、藏青三色。冷水机洗，反面清洗保持面料。",
    "锐风男士拉链连帽衫": "锐风男士拉链连帽衫。全拉链加绒外套，防风袖口和下摆，男款直筒版型，内搭T恤或长袖均可。秋冬户外运动保暖层。价格249元，有黑色、军绿、炭灰三色。冷水洗涤，低温烘干。",
    "锐风防水冲锋衣": "锐风防水冲锋衣。全压胶防水外壳，硬帽檐和立体剪裁袖，男女同款可叠穿卫衣。面料持续防雨且无廉价雨衣的塑料感。价格359元，有黑色、藏青、军绿三色。建议每年补充防泼水剂，勿用柔顺剂。",
    "锐风轻薄羽绒服": "锐风轻薄羽绒服。保暖不臃肿，合成棉填充即使受潮也保持蓬松，加长后摆和高立领设计。适合严寒天气户外和通勤。价格399元，有黑色、深灰、藏青三色。非压缩存放以保持蓬松度。",
    "锐风防风夹克": "锐风防风夹克。轻量防风面料，可收纳至自身口袋，立体剪裁不影响运动。适合春秋户外跑步和通勤。价格269元，有黑色、深灰、雾霾蓝三色。冷水轻柔洗涤，悬挂晾干。",
    "锐风跑步短裤": "锐风跑步短裤。超轻梭织面料，侧边开叉不束缚步幅，宽边松紧腰带不卷边，内置口袋可放钥匙。价格89元，有黑色、藏青、深灰三色。速干面料洗后次日可穿。",
    "锐风运动短裤": "锐风运动短裤。轻量速干面料，宽松版型适合各类运动，侧边口袋设计，男款内衬防走光。价格79元，有黑色、深灰、军绿三色。冷水机洗，快速晾干。",
    "锐风竞速短裤": "锐风竞速短裤。竞速级轻量化面料，人体工学剪裁减少风阻，后腰防水口袋可放手机。适合中长跑和竞速训练。价格99元，有藏青、黑色、深灰三色。冷水洗涤，悬挂晾干。",
    "锐风高强支撑内衣": "锐风高强支撑内衣。高强度支撑适合跑步和跳跃运动，宽肩带不压肩，透气网眼后背设计。价格119元，有黑色、深灰、藏青三色。大量出汗后尽快清洗保护弹性。",
    "锐风轻盈瑜伽内衣": "锐风轻盈瑜伽内衣。低强度支撑，丝滑速干面料，细肩带美背设计，搭配背心也好看。适合瑜伽、普拉提和日常穿着。价格89元，有豆沙粉、黑色、薄荷绿三色。冷水轻柔洗涤，避免烘干。",
    "锐风运动腰包": "锐风运动腰包。耐磨防泼水尼龙材质，可调节腰带可跨腰或跨胸，能装手机、钥匙和卡包。价格79元，有黑色、深灰、军绿三色。湿布擦拭清洁即可。",
    "锐风训练背包": "锐风训练背包。防泼水涂层帆布，独立鞋仓和笔记本隔层，底部可自立。装得下运动鞋和换洗衣物，不像传统健身包。价格199元，有黑色、深灰、藏青三色。仅局部清洁。",
    "锐风运动帽": "锐风运动帽。速干透气面料，可调节后扣，弯檐设计防晒，男女同款。价格59元，有黑色、深灰、白色三色。手洗后晾干。",
    "锐风运动袜三双装": "锐风运动袜三双装。足弓压缩支撑，网眼透气区域，毛圈缓冲足底。每包三双，黑色、白色、灰色各一双。价格69元。冷水洗涤，避免高温烘干。",
    "锐风保暖针织帽": "锐风保暖针织帽。紧密罗纹针织双层保暖，完整包覆耳朵，不易变形。男女同款，冬季户外和通勤均可。价格69元，有黑色、深灰、燕麦色三色。手洗后平铺整形晾干。",
}

# 产品属性用于生成评价
PRODUCT_ATTRS = {}
for name, cat, gender, price, color, colors, weather, sup, sizes in PRODUCTS:
    PRODUCT_ATTRS[name] = {"category": cat, "gender": gender, "price": price, "colors": colors, "weather": weather}

# ============================================================
# 生成 products.csv
# ============================================================
def gen_products_csv():
    rows = []
    pid = 1
    for name, cat, gender, price, color, colors, weather, sup, sizes in PRODUCTS:
        for size in sizes:
            stock = random.randint(15, 95)
            rows.append({
                "product_id": f"P{pid:03d}",
                "name": name,
                "category": cat,
                "gender": gender,
                "size": size,
                "price": f"{price}.0",
                "color": color,
                "colors": colors,
                "weather": weather,
                "stock": stock,
                "supplier_id": sup,
            })
            pid += 1
    path = os.path.join(STRUCTURED, "products.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["product_id","name","category","gender","size","price","color","colors","weather","stock","supplier_id"])
        w.writeheader()
        w.writerows(rows)
    print(f"products.csv: {len(rows)} rows")
    return rows

# ============================================================
# 生成 stores.csv
# ============================================================
def gen_stores_csv():
    rows = [
        {"store_id": "ST01", "name": "锐风上海旗舰店", "city": "上海", "country": "CN"},
        {"store_id": "ST02", "name": "锐风北京体验店", "city": "北京", "country": "CN"},
        {"store_id": "ST03", "name": "锐风广州天河店", "city": "广州", "country": "CN"},
    ]
    path = os.path.join(STRUCTURED, "stores.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["store_id","name","city","country"])
        w.writeheader()
        w.writerows(rows)
    print(f"stores.csv: {len(rows)} rows")

# ============================================================
# 生成 suppliers.csv
# ============================================================
def gen_suppliers_csv():
    rows = [
        {"supplier_id": "SUP01", "name": "华纺纺织", "country": "CN", "material": "锦纶混纺"},
        {"supplier_id": "SUP02", "name": "绿洲针织", "country": "CN", "material": "棉混纺"},
    ]
    path = os.path.join(STRUCTURED, "suppliers.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["supplier_id","name","country","material"])
        w.writeheader()
        w.writerows(rows)
    print(f"suppliers.csv: {len(rows)} rows")

# ============================================================
# 生成 sales.csv
# ============================================================
def gen_sales_csv(product_rows):
    rows = []
    pid_list = [r["product_id"] for r in product_rows]
    start = date(2025, 6, 1)
    end = date(2026, 6, 15)
    delta = (end - start).days
    sid = 1
    for _ in range(130):
        d = start + timedelta(days=random.randint(0, delta))
        pid = random.choice(pid_list)
        store = random.choice(["ST01", "ST02", "ST03"])
        qty = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
        returned = random.random() < 0.12
        rows.append({
            "sale_id": f"S{sid:04d}",
            "product_id": pid,
            "store_id": store,
            "quantity": qty,
            "returned": "true" if returned else "false",
            "sold_at": d.isoformat(),
        })
        sid += 1
    path = os.path.join(STRUCTURED, "sales.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sale_id","product_id","store_id","quantity","returned","sold_at"])
        w.writeheader()
        w.writerows(rows)
    print(f"sales.csv: {len(rows)} rows")

# ============================================================
# 生成 products.jsonl
# ============================================================
def gen_products_jsonl(product_rows):
    seen = set()
    lines = []
    pd_id = 1
    for row in product_rows:
        name = row["name"]
        if name in seen:
            continue
        seen.add(name)
        desc = PRODUCT_DESCRIPTIONS.get(name, f"{name}。锐风运动出品，品质保证。价格{row['price']}元。")
        lines.append(json.dumps({
            "id": f"PD{pd_id:03d}",
            "lang": "zh",
            "product_id": row["product_id"],
            "category": row["category"],
            "text": desc,
        }, ensure_ascii=False))
        pd_id += 1
    path = os.path.join(UNSTRUCTURED, "products.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"products.jsonl: {len(lines)} lines")
    # Also create products_catalog.jsonl (same shape, slightly different angle)
    lines2 = []
    pd_id2 = 1
    for row in product_rows:
        name = row["name"]
        if row["size"] != "M" and row["size"] != "OS":
            continue
        desc = PRODUCT_DESCRIPTIONS.get(name, "")
        # Add gender-specific catalog angle
        if row["gender"] == "men":
            desc2 = desc + " 男款剪裁，适合运动休闲穿搭。"
        elif row["gender"] == "women":
            desc2 = desc + " 女款修身设计，兼顾功能与美观。"
        else:
            desc2 = desc + " 男女同款，适合所有人。"
        lines2.append(json.dumps({
            "id": f"PC{pd_id2:03d}",
            "lang": "zh",
            "product_id": row["product_id"],
            "category": row["category"],
            "gender": row["gender"],
            "text": desc2,
        }, ensure_ascii=False))
        pd_id2 += 1
    path2 = os.path.join(UNSTRUCTURED, "products_catalog.jsonl")
    with open(path2, "w", encoding="utf-8") as f:
        f.write("\n".join(lines2) + "\n")
    print(f"products_catalog.jsonl: {len(lines2)} lines")

# ============================================================
# 评价生成辅助
# ============================================================
POSITIVE_TEMPLATES = [
    "这件{name}真的很好穿，{detail}，已经推荐给朋友了。",
    "{name}超出预期，{detail}，物超所值。",
    "买了{name}之后就经常穿，{detail}，非常满意。",
    "{name}的品质不错，{detail}，值得入手。",
    "非常喜欢{name}，{detail}，下次还会回购。",
    "{name}做工很好，{detail}，穿着很舒服。",
    "入手{name}有一段时间了，{detail}，确实不错。",
    "{name}性价比很高，{detail}，比同类产品好很多。",
]
NEUTRAL_TEMPLATES = [
    "{name}整体还行，{detail}，但{issue}。",
    "{name}中规中矩，{detail}，不过{issue}。",
    "{name}基本满意，{detail}，就是{issue}。",
]
NEGATIVE_TEMPLATES = [
    "{name}有点失望，{issue}，{detail}。",
    "不太推荐{name}，{issue}，{detail}。",
    "{name}质量一般，{issue}，考虑退货。",
]

DETAILS = {
    "leggings": ["面料弹性很好跑步完全不滑落", "高腰设计收腹效果明显", "深蹲不透光很安心", "贴身但不勒很舒适", "洗了几次也没变形"],
    "tops": ["面料速干效果很明显", "透气性好夏天穿不闷热", "版型修身不松垮", "面料柔软贴身很舒服", "出汗后不粘身"],
    "hoodies": ["内里抓绒很柔软", "版型好看搭配什么都行", "面料厚实有质感", "穿着很暖和但不臃肿", "洗后没掉色也没缩水"],
    "jackets": ["防风防雨效果很好", "轻便好收纳不占地方", "剪裁利落不臃肿", "保暖性能超出预期", "细节做工很到位"],
    "shorts": ["面料轻盈跑步不磨腿", "口袋设计很实用", "速干效果好洗了很快干", "腰带不卷边很稳固", "长度适中不走光"],
    "bras": ["支撑力足够跑步不晃", "肩带不压肩很舒服", "面料透气不闷汗", "穿脱方便不勒", "包裹性好不跑杯"],
    "bags": ["容量比想象的大", "材质耐磨做工好", "背带调节方便", "分区合理好找东西", "防水效果不错"],
    "accessories": ["材质舒适不扎皮肤", "做工精细没有线头", "颜色和图片一致", "弹性好不紧绷", "保暖效果很好"],
}

ISSUES = {
    "leggings": ["尺码偏小建议买大一码", "穿久了大腿内侧有点起球", "颜色比图片略深", "裤腰有点紧"],
    "tops": ["白色款出汗后有点透", "尺码偏大建议选小一码", "领口洗了有点松", "面料有点薄"],
    "hoodies": ["洗后缩水了半码", "袖子偏长", "起球比较明显", "帽子有点重"],
    "jackets": ["透气性一般出汗后有点闷", "拉链不太顺滑", "尺码偏小里面穿不了厚衣服", "颜色和图片有偏差"],
    "shorts": ["内衬有点短", "腰带偏紧", "口袋太浅手机容易掉", "面料有点硬"],
    "bras": ["底围偏紧", "肩带不能调节", "高强度运动支撑不够", "洗后有点变形"],
    "bags": ["前袋太浅", "背带有点短", "颜色比图片深", "拉链头有点小"],
    "accessories": ["洗后有点变形", "均码头大的会紧", "颜色比图片暗", "有点起球"],
}

NAMES = ["小王", "小李", "小张", "小陈", "小刘", "小赵", "小周", "小吴", "小孙", "小徐",
         "阿杰", "阿敏", "阿芳", "阿强", "阿丽", "阿磊", "阿静", "阿鹏", "阿雪", "阿伟",
         "大刘", "老王", "李姐", "张哥", "陈姐", "刘哥", "赵姐", "周哥", "吴姐", "孙哥"]

def random_date():
    start = date(2025, 6, 1)
    end = date(2026, 6, 15)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).isoformat()

def gen_review_text(name, category, rating):
    detail = random.choice(DETAILS.get(category, ["质量不错"]))
    issue = random.choice(ISSUES.get(category, ["一般般"]))
    if rating >= 4:
        t = random.choice(POSITIVE_TEMPLATES)
        return t.format(name=name, detail=detail)
    elif rating == 3:
        t = random.choice(NEUTRAL_TEMPLATES)
        return t.format(name=name, detail=detail, issue=issue)
    else:
        t = random.choice(NEGATIVE_TEMPLATES)
        return t.format(name=name, issue=issue, detail=detail)

# ============================================================
# 生成 reviews.jsonl (每产品2-4条, 约80-100条)
# ============================================================
def gen_reviews_jsonl(product_rows):
    # Get unique products
    products = {}
    for row in product_rows:
        if row["name"] not in products:
            products[row["name"]] = row
    lines = []
    rid = 1
    for name, row in products.items():
        cat = row["category"]
        n = random.randint(2, 4)
        for _ in range(n):
            rating = random.choices([5, 4, 3, 2, 1], weights=[40, 30, 18, 8, 4])[0]
            text = gen_review_text(name, cat, rating)
            lines.append(json.dumps({
                "id": f"R{rid:04d}",
                "lang": "zh",
                "product_id": row["product_id"],
                "text": text,
                "rating": rating,
                "date": random_date(),
            }, ensure_ascii=False))
            rid += 1
    path = os.path.join(UNSTRUCTURED, "reviews.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"reviews.jsonl: {len(lines)} lines")

# ============================================================
# 生成 reviews_generated.jsonl (每产品2-3条, 约60-80条)
# ============================================================
def gen_reviews_generated(product_rows):
    products = {}
    for row in product_rows:
        if row["name"] not in products:
            products[row["name"]] = row
    lines = []
    rid = 1
    for name, row in products.items():
        cat = row["category"]
        n = random.randint(2, 3)
        for _ in range(n):
            rating = random.choices([5, 4, 3, 4], weights=[35, 35, 15, 15])[0]
            detail = random.choice(DETAILS.get(cat, ["质量不错"]))
            person = random.choice(NAMES)
            templates = [
                f"{name}很舒服，{detail}。——{person}",
                f"买了{name}马上又下单了一件。——{person}",
                f"{detail}，{name}已经是我的日常款了。——{person}",
                f"轻量透气，{name}物有所值。——{person}",
                f"{name}版型很好，{detail}。——{person}",
            ]
            text = random.choice(templates)
            lines.append(json.dumps({
                "id": f"RG{rid:04d}",
                "lang": "zh",
                "product_id": row["product_id"],
                "text": text,
                "rating": rating,
                "date": random_date(),
            }, ensure_ascii=False))
            rid += 1
    path = os.path.join(UNSTRUCTURED, "reviews_generated.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"reviews_generated.jsonl: {len(lines)} lines")

# ============================================================
# 生成 reviews_voice.jsonl (每产品2条: 1正面1批评)
# ============================================================
VOICE_POSITIVE = {
    "leggings": "穿着{name}做了90分钟高温瑜伽，一次都没拉过裤腰。面料有磨毛的手感但做深蹲完全不透。",
    "tops": "三伏天跑步就靠{name}了，出了一身大汗走回家路上就干了，不像以前穿的棉T恤粘在身上。",
    "hoodies": "{name}里面像裹了条毯子，燕麦色搭配什么都好看。穿去健身房、坐飞机、逛超市都合适，两个月了还跟新的一样。",
    "jackets": "穿{name}遛狗遇到四十分钟暴雨，里面的卫衣全干的。藏青色实物比网站上的颜色更深更好看。",
    "shorts": "{name}轻得像没穿一样，侧边开叉跑起来完全不卡步幅，腰带跑了十公里也没卷边。",
    "bras": "{name}跑半马全程稳稳的，肩带不滑也不压，跑完也没有勒痕。",
    "bags": "背着{name}走了一整天，手机钥匙卡包和防晒霜都装下了，腰带调节扣不会松。",
    "accessories": "{name}戴了一整个冬天，不起球不变形，耳朵包裹得很严实。",
}
VOICE_CRITICAL = {
    "leggings": "{name}版型不错但洗了大概八次大腿内侧就开始起球了，这个价格有点心疼。我都是冷水洗悬挂晾干的。",
    "tops": "提醒一下{name}白色款出汗后基本是透的，里面穿深色内衣会看到。最后换了件深色的。",
    "hoodies": "{name}确实很软，但低温烘干一次后缩了大概半码。虽然也有我的原因，但这个价格希望洗护能更宽容一些。",
    "jackets": "{name}防雨没问题，但完全不透气。快走十分钟上坡里面就汗湿了，更适合站着防雨不适合爬山。",
    "shorts": "{name}前面口袋太浅了，润唇膏掉了两次之后就不敢放东西了。主仓还行但小口袋基本是装饰。",
    "bras": "{name}底围偏紧，我平时穿M码这件M有点勒，建议选大一码。",
    "bags": "{name}前袋太浅基本没用，主仓够用但那个小口袋放不了什么。",
    "accessories": "{name}头围偏大的人戴着会紧，我戴久了额头有压痕。均码对大头不太友好。",
}

def gen_reviews_voice(product_rows):
    products = {}
    for row in product_rows:
        if row["name"] not in products:
            products[row["name"]] = row
    lines = []
    rid = 1
    for name, row in products.items():
        cat = row["category"]
        # Positive
        pos = VOICE_POSITIVE.get(cat, f"{name}穿着很舒服，很满意。").format(name=name)
        lines.append(json.dumps({
            "id": f"RV{rid:04d}",
            "lang": "zh",
            "product_id": row["product_id"],
            "text": pos,
            "rating": 5,
            "date": random_date(),
        }, ensure_ascii=False))
        rid += 1
        # Critical
        crit = VOICE_CRITICAL.get(cat, f"{name}有些不足，但整体还可以。").format(name=name)
        lines.append(json.dumps({
            "id": f"RV{rid:04d}",
            "lang": "zh",
            "product_id": row["product_id"],
            "text": crit,
            "rating": 3,
            "date": random_date(),
        }, ensure_ascii=False))
        rid += 1
    path = os.path.join(UNSTRUCTURED, "reviews_voice.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"reviews_voice.jsonl: {len(lines)} lines")

# ============================================================
# 生成 reviews_curated.jsonl (约25条精选)
# ============================================================
CURATED_REVIEWS = [
    ("锐风压缩跑步裤", "leggings", 5, "冬天晨跑穿锐风压缩跑步裤，里面加绒保暖又压缩，比我以前穿的普通秋裤暖多了，跑步时肌肉也不抖。"),
    ("锐风流云紧身裤", "leggings", 5, "锐风流云紧身裤是我居家最常穿的，又软又舒服，窝在沙发上看电视完全不想脱。"),
    ("锐风云感卫衣", "hoodies", 5, "锐风云感卫衣是最软最舒服的一件，居家追剧必备，穿上就不想出门。"),
    ("锐风男士经典卫衣", "hoodies", 5, "锐风男士经典卫衣保暖性很好，5度的早晨里面穿件T恤出门就够了，比我以前的抓绒还暖。"),
    ("锐风男士美利奴长袖", "tops", 5, "锐风男士美利奴长袖贴身穿很暖和，冬天户外徒步当打底很舒服，面料柔软不像普通羊毛扎人。"),
    ("锐风美利奴长袖", "tops", 4, "锐风美利奴长袖居家也很好穿，柔软保暖不臃肿，冬天在家穿着很舒服。"),
    ("锐风轻薄羽绒服", "jackets", 5, "锐风轻薄羽绒服是最冷天穿的，零下5度内搭美利奴长袖就够了，又轻又暖不像以前穿的羽绒服那么重。"),
    ("锐风拉链连帽衫", "hoodies", 4, "锐风拉链连帽衫在家当外套穿很方便，保暖又不臃肿，客厅到楼下取快递都不用换衣服。"),
    ("锐风男士拉链连帽衫", "hoodies", 5, "锐风男士拉链连帽衫比我以前的抓绒外套暖，冬天户外活动穿正好，里面套件长袖就够了。"),
    ("锐风高腰健身裤", "leggings", 4, "锐风高腰健身裤居家运动两穿，舒服又好看，在家做瑜伽或出门买咖啡都能穿。"),
    ("锐风保暖针织帽", "accessories", 5, "锐风保暖针织帽冬天戴很暖和，包裹耳朵不勒头，搭配冲锋衣或羽绒服都好看。"),
    ("锐风防水冲锋衣", "jackets", 5, "下雨天穿锐风防水冲锋衣，里面完全没湿，防风效果也很好，上海的冬天一件就够了。"),
    ("锐风流云紧身裤", "leggings", 4, "锐风流云紧身裤和锐风高强支撑内衣搭配穿，跑步一套就够了，颜色也很搭。"),
    ("锐风速干T恤", "tops", 5, "夏天穿锐风速干T恤跑步，透气性好速干快，比棉T恤舒服太多，已经买了两件换着穿。"),
    ("锐风跑步短裤", "shorts", 5, "锐风跑步短裤是夏天跑步标配，轻到没感觉，口袋放手机也不晃。"),
    ("锐风轻盈瑜伽裤", "leggings", 5, "锐风轻盈瑜伽裤裸感面料太舒服了，做瑜伽完全不束缚，比我买过的其他牌子都柔软。"),
    ("锐风高强支撑内衣", "bras", 5, "锐风高强支撑内衣支撑力很强，跑步跳绳都不晃，而且不压肩。"),
    ("锐风云感卫衣", "hoodies", 4, "锐风云感卫衣在空调房里穿刚好，柔软轻便，办公室备一件很实用。"),
    ("锐风男士速干T恤", "tops", 5, "锐风男士速干T恤是健身房最常穿的，出汗不粘身，洗了很快干。"),
    ("锐风运动短裤", "shorts", 4, "锐风运动短裤很百搭，打球跑步日常都能穿，面料舒服不磨腿。"),
    ("锐风防风夹克", "jackets", 4, "锐风防风夹克春秋跑步穿正好，挡风又轻便，能揉成一团塞背包里。"),
    ("锐风运动袜三双装", "accessories", 5, "锐风运动袜足底有缓冲，跑步很舒服，三双装性价比高，已经回购了。"),
    ("锐风男士经典卫衣", "hoodies", 4, "锐风男士经典卫衣居家穿很舒服，面料柔软，周末在家整天穿着。"),
    ("锐风透气紧身裤", "leggings", 4, "锐风透气紧身裤夏天穿很凉快，网眼设计确实透气，跑步不闷汗。"),
    ("锐风训练背包", "bags", 5, "锐风训练背包容量很大，鞋仓和衣服分开装很卫生，上班背电脑也合适。"),
]

def gen_reviews_curated():
    lines = []
    # Build name->product_id mapping
    name_to_pid = {}
    for name, cat, gender, price, color, colors, weather, sup, sizes in PRODUCTS:
        pid_num = None
        for i, (n, *_) in enumerate(PRODUCTS):
            if n == name:
                pid_num = sum(len(PRODUCTS[j][8]) for j in range(i)) + 1
                break
        name_to_pid[name] = f"P{pid_num:03d}"

    for i, (name, cat, rating, text) in enumerate(CURATED_REVIEWS):
        lines.append(json.dumps({
            "id": f"RC{i+1:04d}",
            "lang": "zh",
            "product_id": name_to_pid[name],
            "text": text,
            "rating": rating,
            "date": random_date(),
        }, ensure_ascii=False))
    path = os.path.join(UNSTRUCTURED, "reviews_curated.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"reviews_curated.jsonl: {len(lines)} lines")

if __name__ == "__main__":
    product_rows = gen_products_csv()
    gen_stores_csv()
    gen_suppliers_csv()
    gen_sales_csv(product_rows)
    gen_products_jsonl(product_rows)
    gen_reviews_jsonl(product_rows)
    gen_reviews_generated(product_rows)
    gen_reviews_voice(product_rows)
    gen_reviews_curated()
    print("Done!")
