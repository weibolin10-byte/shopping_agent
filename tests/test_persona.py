"""The engine must carry no brand or persona of its own: the assistant name, specialist name,
brand, and industry all come from the active pack's domain.yaml. This is the domain-swap thesis, so
the answer pipeline introduces itself with the pack's identity, and a pack with no manifest falls
back to a neutral voice instead of a hardcoded one. If these fail, the leak linter would also flag
hardcoded vocab in an engine dir.
"""
from pipeline.answer import _agent_system, _persona, _smalltalk, _system

DOMAIN = "china_ecommerce"


def test_persona_is_read_from_the_pack():
    a = _persona(DOMAIN)
    assert a["assistant"] == "小风" and a["specialist"] == "小晴"
    assert a["brand"] == "运动汇" and a["industry"] == "运动品牌零售平台"


def test_system_prompts_use_the_active_pack_identity():
    prompts = _system(DOMAIN) + _agent_system(DOMAIN)
    assert "小风" in prompts and "小晴" in prompts and "运动汇" in prompts
    # the identity comes from the pack, not from engine code: a slug with no manifest falls back to
    # a neutral voice and never carries the apparel persona, so nothing is hardcoded in the prompt.
    neutral = _system("does_not_exist") + _agent_system("does_not_exist")
    for token in ("小风", "小晴", "运动汇"):
        assert token not in neutral, token


def test_greetings_and_intros_speak_as_the_active_pack():
    assert "小风" in _smalltalk("hi", None, DOMAIN)
    # the escalation care specialist greeting uses the specialist name
    assert "小晴" in _smalltalk("hi", "agent", DOMAIN)
    # "who are you" introduces the pack's assistant
    assert "小风" in _smalltalk("who are you", None, DOMAIN)


def test_greeting_recognizes_either_persona_name():
    # "hey <assistant>" and "hey <specialist>" must both be caught as greetings: the trailing-name
    # group has to space-prefix every alternative, not just the first.
    for q in ("hey 小风", "hi 小晴", "hello 小风"):
        assert _smalltalk(q, None, DOMAIN) is not None, q


def test_missing_persona_falls_back_to_neutral_voice():
    # a pack slug with no manifest must not crash; it yields neutral placeholders
    p = _persona("does_not_exist")
    assert p["assistant"] and p["brand"] and p["industry"]
    assert "小风" not in _system("does_not_exist")
