"""中文生产方案的成本模型必须可复现且保持业务量级合理。"""
from mlops.cost_model import build, text_turn_cost


def test_selected_stack_is_reported():
    model = build()
    assert model["stack"]["generation"] == "deepseek-chat"
    assert model["stack"]["embedding"] == "qwen-text-embedding-v3"


def test_routing_is_near_free():
    b = text_turn_cost()
    assert b["routing"] < b["generation"]


def test_human_agent_is_orders_of_magnitude_over_the_ai():
    assert build()["cost_ratio"]["human_vs_ai"] > 100
