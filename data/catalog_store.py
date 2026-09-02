"""Authoritative structured product catalog used before document retrieval."""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass

from pipeline.text import lexical_units

_SIZE_ORDER = {size: index for index, size in enumerate(
               ("XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"))}
_MODEL_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-_'.][A-Za-z0-9]+)*")
_GENERIC_MODEL_TOKENS = {"shoe", "shoes", "running", "sports", "men", "women"}
_MAX_PRICE = re.compile(r"(最贵|价格最高|售价最高|最高价)")
_MIN_PRICE = re.compile(r"(最便宜|价格最低|售价最低|最低价)")


@dataclass(frozen=True)
class CatalogRecord:
    product_id: str
    name: str
    fields: dict
    score: float


class StructuredCatalogStore:
    def __init__(self, records: list[dict], *, knowledge_version: str = "catalog-v1") -> None:
        self.records = records
        self.knowledge_version = knowledge_version

    @classmethod
    def from_csv(cls, path: str, *, knowledge_version: str = "catalog-v1"):
        if not os.path.isfile(path):
            return cls([], knowledge_version=knowledge_version)
        with open(path, newline="", encoding="utf-8") as handle:
            return cls(list(csv.DictReader(handle)), knowledge_version=knowledge_version)

    def search(self, query: str, *, limit: int = 8) -> list[CatalogRecord]:
        if self.requires_structured_lookup(query):
            priced = [(float(row.get("price") or 0), row) for row in self.records
                      if row.get("price") not in (None, "")]
            if not priced:
                return []
            target = (max(price for price, _ in priced) if _MAX_PRICE.search(query)
                      else min(price for price, _ in priced))
            return [CatalogRecord(str(row.get("product_id") or ""),
                                  str(row.get("name") or ""), dict(row), 1.0)
                    for price, row in priced if price == target][:limit]
        wanted = set(lexical_units(query))
        if not wanted:
            return []
        ranked: list[CatalogRecord] = []
        for row in self.records:
            searchable = " ".join(str(row.get(k) or "") for k in
                                  ("product_id", "name", "brand", "category", "color",
                                   "colors", "weather", "size", "gender"))
            found = set(lexical_units(searchable))
            overlap = wanted & found
            if not overlap:
                continue
            score = len(overlap) / max(len(wanted), 1)
            ranked.append(CatalogRecord(str(row.get("product_id") or ""),
                                        str(row.get("name") or ""), dict(row), score))
        ranked.sort(key=lambda item: (item.score, item.product_id), reverse=True)
        return ranked[:limit]

    def requires_structured_lookup(self, query: str) -> bool:
        """Whether the answer requires an aggregate over the authoritative catalog."""
        return bool(_MAX_PRICE.search(query) or _MIN_PRICE.search(query))

    def resolve_product_ids(self, query: str) -> set[str]:
        """Resolve explicitly named products without treating a generic category as an entity."""
        normalized = query.lower()
        query_tokens = {token.lower() for token in _MODEL_TOKEN.findall(query)}
        query_units = set(lexical_units(query))
        candidates: list[tuple[int, float, str]] = []
        for row in self.records:
            name = str(row.get("name") or "")
            brand = str(row.get("brand") or "")
            name_tokens = {token.lower() for token in _MODEL_TOKEN.findall(name)}
            brand_tokens = {token.lower() for token in _MODEL_TOKEN.findall(brand)}
            distinctive = {token for token in name_tokens - brand_tokens - _GENERIC_MODEL_TOKENS
                           if len(token) >= 3 or token.isdigit()}
            exact_name = bool(name and name.lower() in normalized)
            model_overlap = distinctive & query_tokens
            if not exact_name and not model_overlap:
                continue
            # A shared family word such as ``Air`` or the suffix ``FIT`` is not enough to make
            # every product in that family the same entity. Rank candidate names by complete
            # lexical overlap and keep only the strongest match. Chinese category words provide
            # the tie-break for names such as Dri-FIT T恤 vs Dri-FIT One 紧身裤.
            name_units = set(lexical_units(name))
            overlap_count = len(query_units & name_units)
            coverage = overlap_count / max(len(name_units), 1)
            candidates.append((overlap_count + int(exact_name) * 1000,
                               coverage, name.lower()))
        if not candidates:
            return set()
        best = max((count, coverage) for count, coverage, _ in candidates)
        matched_names = {name for count, coverage, name in candidates
                         if (count, coverage) == best}
        return {str(row.get("product_id")) for row in self.records
                if str(row.get("name") or "").lower() in matched_names
                and row.get("product_id")}

    def as_hits(self, query: str, *, limit: int = 8,
                product_ids: set[str] | None = None) -> list[dict]:
        ranked = self.search(query, limit=max(limit * 8, limit))
        if product_ids is not None:
            ranked = [item for item in ranked if item.product_id in product_ids]
        groups: dict[str, list[CatalogRecord]] = {}
        for item in ranked:
            groups.setdefault(item.name.strip().lower(), []).append(item)
        hits = []
        for variants in list(groups.values())[:limit]:
            item = variants[0]
            fields = dict(item.fields)
            product_ids = [v.product_id for v in variants]
            sizes = list(dict.fromkeys(str(v.fields.get("size")) for v in variants
                                       if v.fields.get("size")))
            sizes.sort(key=lambda size: (_SIZE_ORDER.get(size.upper(), 999), size))
            colors = list(dict.fromkeys(
                color for v in variants
                for color in str(v.fields.get("colors") or v.fields.get("color") or "").split("|")
                if color))
            stocks = [int(float(v.fields.get("stock") or 0)) for v in variants]
            prices = list(dict.fromkeys(str(v.fields.get("price")) for v in variants
                                        if v.fields.get("price") is not None))
            fields.update({"product_ids": product_ids, "sizes": sizes,
                           "stock_total": sum(stocks), "colors": colors})
            price_text = prices[0] if len(prices) == 1 else "-".join(prices)
            source_id = f"catalog:{item.product_id}"
            text = (f"{item.name}（SKU {'/'.join(product_ids)}），品牌{fields.get('brand')}，"
                    f"尺码{'/'.join(sizes)}，价格{price_text}元，总库存{sum(stocks)}，"
                    f"颜色{'/'.join(colors)}。")
            hits.append({"id": source_id, "score": max(v.score for v in variants),
                         "payload": {"chunk_id": source_id,
                                     "doc_type": "product", "source": "structured_catalog",
                                     "text": text, "structured_fields": fields,
                                     "authority_level": 3,
                                     "knowledge_version": self.knowledge_version}})
        return hits
