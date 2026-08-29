// china_ecommerce 领域本体。标签名与 domain.yaml 中的 entity_types 对应。
// 每个标签主键上的唯一约束使图谱加载时可幂等 MERGE。

CREATE CONSTRAINT product_id IF NOT EXISTS
  FOR (p:Product) REQUIRE p.product_id IS UNIQUE;

CREATE CONSTRAINT store_id IF NOT EXISTS
  FOR (s:Store) REQUIRE s.store_id IS UNIQUE;

CREATE CONSTRAINT supplier_id IF NOT EXISTS
  FOR (sup:Supplier) REQUIRE sup.supplier_id IS UNIQUE;

CREATE CONSTRAINT review_id IF NOT EXISTS
  FOR (r:Review) REQUIRE r.id IS UNIQUE;

// 关系词汇表，模板 Cypher 和 text-to-Cypher 共用：
//   (:Supplier)-[:SUPPLIES]->(:Product)
//   (:Product)-[:SOLD_AT]->(:Store)      // 从销售记录派生
//   (:Review)-[:MENTIONS]->(:Product)
