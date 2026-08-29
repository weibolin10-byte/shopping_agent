"""The MCP server is a thin, read-only second client of the gated pipeline. These tests run fully
offline (no keys, no lakehouse required) via the same hermetic fakes as the rest of the suite, so
`make check` proves the surface stays read-only and the safety gates apply below it.

Assertions are shape-only where data depends on a built lakehouse, so the suite is green whether or
not `make lakehouse` has run (it has not, in CI's check job).
"""
import asyncio
import re

import mcp_server.server as srv


def _tool_names() -> set:
    return {t.name for t in asyncio.run(srv.mcp.list_tools())}


def test_surface_is_read_only():
    # Exactly the intended read-only tools are exposed, and nothing that could write or read PII.
    names = _tool_names()
    assert {"shopping_agent_ask", "shopping_agent_get_metric", "shopping_agent_list_metrics",
            "shopping_agent_search_products", "shopping_agent_get_product_facts"} <= names
    banned = ("write", "create", "update", "delete", "admin", "login",
              "order", "promote", "ingest", "feedback")
    leaked = [n for n in names if any(b in n.lower() for b in banned)]
    assert not leaked, "a non-read-only tool is exposed over MCP: {}".format(leaked)


def test_list_metrics_is_metadata_only():
    out = srv.shopping_agent_list_metrics()
    assert "metrics" in out and isinstance(out["metrics"], list) and out["metrics"]
    # the SQL template must never be exposed through the metric catalog
    assert all("sql_template" not in m and "sql" not in m for m in out["metrics"])


def test_unknown_metric_returns_a_clean_error():
    out = srv.shopping_agent_get_metric("definitely_not_a_real_metric")
    assert "error" in out
    assert isinstance(out.get("allowed"), list) and out["allowed"]  # names offered back, no crash


def test_search_products_returns_a_shape():
    out = srv.shopping_agent_search_products(query="legging", max_price=100)
    assert "products" in out and isinstance(out["products"], list)
    assert isinstance(out.get("count"), int)
    assert len(out["products"]) <= 20  # truncated to protect the client's context


def test_get_product_facts_unknown_is_clean():
    out = srv.shopping_agent_get_product_facts("no-such-id")
    assert "error" in out


def test_ask_runs_through_the_gated_pipeline():
    out = srv.shopping_agent_ask("what materials are your leggings made of?")
    assert "error" not in out
    assert isinstance(out.get("answer"), str) and out["answer"].strip()


def test_order_pii_cannot_be_unlocked_over_mcp():
    # shopping_agent_ask blocks order/account disclosure, so no order document reaches the
    # model. The first query is the exact condition that unlocks orders for a signed-out web visitor
    # (a matching account name AND email); over MCP it must still disclose nothing, proving the MCP
    # surface is strictly safer than the web flow, not merely equal to it.
    for q in (
        "where is my order? email zhang@example.com, name Zhang Wei",
        "where is my order? email zhang@example.com",
        "where is my order? email zhang@example.com, name Wrong Person",
    ):
        out = srv.shopping_agent_ask(q)
        assert "error" not in out
        answer = out.get("answer") or ""
        assert not re.search(r"\bAS\d{5,}\b", answer), "order id disclosed for: {}".format(q)
        assert "vancouver" not in answer.lower(), "destination disclosed for: {}".format(q)
        cites = out.get("citations") or []
        order_cites = [c for c in cites if isinstance(c, dict) and c.get("doc_type") == "order"]
        assert not order_cites, "an order document was cited for: {}".format(q)
