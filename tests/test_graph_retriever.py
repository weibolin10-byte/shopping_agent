"""M5.3 graph retriever: resolve an entity named in the query to a graph node and attach its
neighborhood as a labeled evidence block, offline on the fakes. Proves relational questions are
answered from the graph, the block is domain agnostic, an unrelated question adds nothing, and a
mention only in retrieved text enriches but does not rescue a weak answer from abstaining.
"""
from adapters.base import LLMResult
from adapters.factory import make_embedder, make_graph, make_llm, make_store
from data.lakehouse import build_lakehouse
from knowledge.graph_loader import load_graph
from pipeline.answer import answer_question
from retrieval.graph import make_graph_retriever
from retrieval.sparse import SparseEncoder


class CitingLLM:
    def generate(self, prompt, *, system=None, max_tokens=512):
        return LLMResult(text="裕元工业供应这款跑鞋 [1].", prompt_tokens=1, completion_tokens=1,
                         model="fake")


def _retriever_for(domain, tmp_path):
    db = str(tmp_path / "lh.duckdb")
    build_lakehouse(domain, db)
    graph = make_graph("memory")
    load_graph(domain, db, graph)
    return make_graph_retriever(domain, graph)


def _store_with(text):
    embedder = make_embedder("fake")
    encoder = SparseEncoder()
    store = make_store("memory")
    dense = embedder.embed([text])[0]
    sparse = encoder.encode(text)
    store.upsert([{"id": "D1", "text": text, "payload": {"doc_type": "review"},
                   "dense": dense, "sparse": {"indices": sparse.indices, "values": sparse.values}}])
    return embedder, store


def test_resolves_entity_and_renders_relation(tmp_path):
    retriever = _retriever_for("china_ecommerce", tmp_path)
    block, from_query = retriever.evidence("Nike Air Zoom Pegasus 40 跑步鞋由哪个供应商生产？")
    assert block is not None and from_query is True
    assert block["doc_type"] == "graph"
    assert "裕元工业" in block["text"] and "SUPPLIES" in block["text"]


def test_unrelated_query_resolves_nothing(tmp_path):
    retriever = _retriever_for("china_ecommerce", tmp_path)
    block, from_query = retriever.evidence("what is the boiling point of water")
    assert block is None and from_query is False


def test_variant_grain_entity_resolves_once(tmp_path):
    # Pegasus 40 exists as several size variants sharing one name; resolution must return a
    # single representative, not one per size, so variants do not crowd out other entities.
    retriever = _retriever_for("china_ecommerce", tmp_path)
    resolved = retriever.resolve("介绍一下Nike Air Zoom Pegasus 40 跑步鞋")
    products = [node for node in resolved if node.label == "Product"]
    assert len(products) == 1
    assert products[0].properties["name"] == "Nike Air Zoom Pegasus 40 跑步鞋"


def test_two_named_entities_both_resolve(tmp_path):
    retriever = _retriever_for("china_ecommerce", tmp_path)
    block, _ = retriever.evidence(
        "对比Nike Air Zoom Pegasus 40 跑步鞋和Adidas Ultraboost Light 跑步鞋")
    assert block is not None
    assert "Pegasus 40" in block["text"] and "Ultraboost Light" in block["text"]


def test_empty_graph_yields_no_evidence(tmp_path):
    build_lakehouse("china_ecommerce", str(tmp_path / "lh.duckdb"))
    retriever = make_graph_retriever("china_ecommerce", make_graph("memory"))  # nothing loaded
    block, from_query = retriever.evidence("Nike Air Zoom Pegasus 40 跑步鞋由哪个供应商生产？")
    assert block is None and from_query is False


def test_relational_question_answers_from_graph_without_vectors(tmp_path):
    retriever = _retriever_for("china_ecommerce", tmp_path)
    result = answer_question("Nike Air Zoom Pegasus 40 跑步鞋由哪个供应商生产？",
                             embedder=make_embedder("fake"), store=make_store("memory"),
                             llm=CitingLLM(), graph_retriever=retriever,
                             trace_path=str(tmp_path / "t.jsonl"))
    assert result.tier == "auto"
    assert result.trace["graph"] is True
    assert result.contexts[0]["doc_type"] == "graph"
    assert "裕元工业" in result.contexts[0]["text"]
    assert result.citations[0]["id"].startswith("graph:")  # the model cited [1], the graph block


def test_chunk_only_mention_does_not_rescue_abstain(tmp_path):
    # The query names no entity, but the one retrieved chunk mentions a product. The graph block
    # is added as enrichment, yet the weak answer must still abstain (chunk hop is not authority).
    retriever = _retriever_for("china_ecommerce", tmp_path)
    embedder, store = _store_with("Nike Air Zoom Pegasus 40 跑步鞋适合日常训练")
    result = answer_question("退换货政策是什么",
                             embedder=embedder, store=store, llm=make_llm("fake"),
                             graph_retriever=retriever, trace_path=str(tmp_path / "t.jsonl"))
    assert result.trace["graph"] is True     # the block was attached (the chunk named a product)
    assert result.abstained                  # but it did not suppress the abstain


def test_pipeline_without_graph_is_unchanged(tmp_path):
    result = answer_question("Nike Air Zoom Pegasus 40 跑步鞋由哪个供应商生产？",
                             embedder=make_embedder("fake"), store=make_store("memory"),
                             llm=make_llm("fake"), trace_path=str(tmp_path / "t.jsonl"))
    assert result.trace["graph"] is False
    assert result.abstained  # no vectors, no graph -> honest abstain
