"""Private order-service boundary.

Order records never need vector similarity. They are looked up deterministically after the caller's
JWT identity has been resolved, with tenant and user scope applied inside the adapter.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Protocol

# ``\b`` is not usable before an ASCII order id that directly follows a Chinese character:
# Python considers both CJK and ASCII letters ``\w``, so "订单RF100011" has no word boundary.
# Bound only against ASCII letters/digits, which accepts natural Chinese text while still rejecting
# an id embedded inside another Latin identifier.
_ORDER_REF = re.compile(r"(?<![A-Za-z0-9])(?:RF|EM|YZ|PC)[0-9]{4,}(?![A-Za-z0-9])", re.I)
_LEGACY_ORDER_DOC = re.compile(r"^OD[0-9]+$", re.I)


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    user_id: str
    tenant_id: str = "default"
    status: str = "unknown"
    fields: dict = field(default_factory=dict)


class OrderStore(Protocol):
    def find(self, *, user_id: str, tenant_id: str, order_id: str | None = None,
             limit: int = 10) -> list[OrderRecord]: ...


class InMemoryOrderStore:
    def __init__(self, records: list[OrderRecord] | None = None) -> None:
        self.records = records or []

    def find(self, *, user_id: str, tenant_id: str, order_id: str | None = None,
             limit: int = 10) -> list[OrderRecord]:
        return [r for r in self.records if r.user_id.casefold() == user_id.casefold()
                and r.tenant_id == tenant_id
                and (order_id is None or r.order_id == order_id)][:limit]


class JsonOrderStore(InMemoryOrderStore):
    """JSON adapter for bundled seed data; production uses the same interface over SQL/API."""
    @classmethod
    def from_path(cls, path: str) -> "JsonOrderStore":
        if not os.path.isfile(path):
            return cls([])
        records: list[OrderRecord] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                email = str(row.get("email") or "")
                text = str(row.get("text") or "")
                internal_id = str(row.get("id") or "")
                # Domain seed rows have an internal document id such as OD100011 while the real
                # customer-facing order id (RF100011) lives in ``text``.  Prefer an explicit
                # order_id, then scan the text of legacy order-detail rows. Profiles and
                # summary rows also mention order ids but are not orders and must not be indexed.
                explicit_id = str(row.get("order_id") or "")
                if not explicit_id and not _LEGACY_ORDER_DOC.fullmatch(internal_id):
                    continue
                ref = _ORDER_REF.search(explicit_id or text)
                records.append(OrderRecord(
                    order_id=(ref.group(0).upper() if ref else internal_id),
                    user_id=email, tenant_id=str(row.get("tenant_id") or "default"),
                    status=str(row.get("status") or "unknown"), fields={**row, "text": text}))
        return cls(records)


class PostgresOrderStore:
    """Tenant/user-filtered order repository over a private Postgres table."""
    def __init__(self, connect) -> None:
        self._connect = connect
        with self._connect() as con, con.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS ecommerce_orders ("
                        "tenant_id TEXT NOT NULL, user_id TEXT NOT NULL, order_id TEXT NOT NULL, "
                        "status TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, "
                        "PRIMARY KEY (tenant_id, order_id))")
            cur.execute("CREATE INDEX IF NOT EXISTS ecommerce_orders_scope_idx "
                        "ON ecommerce_orders (tenant_id, user_id)")
            con.commit()

    def find(self, *, user_id: str, tenant_id: str, order_id: str | None = None,
             limit: int = 10) -> list[OrderRecord]:
        sql = ("SELECT order_id, status, payload FROM ecommerce_orders "
               "WHERE tenant_id = %s AND user_id = %s")
        params: list = [tenant_id, user_id]
        if order_id:
            sql += " AND order_id = %s"
            params.append(order_id)
        sql += " ORDER BY order_id DESC LIMIT %s"
        params.append(limit)
        with self._connect() as con, con.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [OrderRecord(str(row[0]), user_id, tenant_id, str(row[1]),
                            row[2] if isinstance(row[2], dict) else json.loads(row[2]))
                for row in rows]


def make_order_store(backend: str, *, json_path: str, postgres_dsn: str = "") -> OrderStore:
    backend = (backend or "json").strip().lower()
    if backend == "json":
        return JsonOrderStore.from_path(json_path)
    if backend == "postgres":
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("ORDER_BACKEND=postgres requires the production extra") from exc
        return PostgresOrderStore(lambda: psycopg.connect(postgres_dsn))
    raise ValueError(f"unknown order backend: {backend}")


def order_id_from_query(query: str) -> str | None:
    match = _ORDER_REF.search(query or "")
    return match.group(0).upper() if match else None
