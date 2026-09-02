"""The master orchestrator's routing decision.

Every turn is routed by a cheap-first cascade, so the common case costs nothing and only genuine
ambiguity pays for a model call:

  Layer 0  deterministic intercept: an explicit request to reach a person. $0.
  Layer 1  the deterministic intent guards (complaint / account / shopping). $0, the majority.
  Layer 2  a small-model tie-break, only when the layers above do not decide. One cheap 8B call.

`route()` returns a RouteDecision naming the lane, a confidence, and which layer decided. When two
intent guards fire it returns a multi-task plan (complaint first) for the heavy path to fan out.
When even the small model cannot separate two lanes it returns a strict two-option clarify, so the
brain asks instead of guessing.

Safety and smalltalk are handled by the guards that run BEFORE routing (the input guard in the
graph, the smalltalk intercept in the fast path), so `route()` only chooses among service lanes and
assumes the query is already a standalone, non-malicious turn. Rewrite a follow-up before calling.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag.guards import account_intent, shopping_intent

# The service lanes the orchestrator routes among. Smalltalk and refusals never reach here.
LANES = ("stylist", "care", "complaint", "answers", "escalation")

# An explicit ask to reach a person. It needs an escalation verb near a human noun, an
# unambiguous phrase, or a bare human-noun message, so "a jacket for a tall person" or "in-person
# pickup" do not trip it while "human please" and a lone "representative" do.
# Human-support nouns for the escalation intercept. Kept narrow on purpose: "staff", "reps",
# "operator", "advisor", and "employee" are excluded because they collide with shopping vocabulary
# ("staff picks", "gym reps", "operator manual", "style advisor", "employee discount").
_HUMAN = r"(human|person|people|agent|representative|manager|supervisor)"

# A refusal to be handed to a person must NOT escalate ("I don't want to talk to a human").
# A genuine refusal of a person, not a discourse "No, I want a human". It needs a negated desire or
# verb landing near the human noun, or "no need for a human", so "No, connect me to an agent" and
# "not a bot, a human please" still escalate.
_NO_HUMAN = re.compile(
    r"\b(don'?t|do not|never|no need|rather not|no longer|stop)\b[^.?!]{0,16}\b(want|need|talk|"
    r"speak|chat|deal|transfer|connect|use)\b[^.?!]{0,12}\b" + _HUMAN + r"\b"
    r"|\bwithout (a |an |talking to |speaking to )?" + _HUMAN + r"\b"
    r"|\bno need for (a |an )?" + _HUMAN + r"\b", re.I)

# An explicit request to reach a person. High precision on purpose: the frontend and the 8B
# tie-break catch the rest, so a false positive (which files a real case) is the worse error. The
# earlier "to a <human>" and "want/need a <human>" branches were removed: they hijacked gift
# recipients ("a scarf to give to a supervisor") and style requests ("I need an advisor for my
# outfit"). Escalation now needs a support verb landing on a human noun, or an unambiguous phrase.
_ESCALATE = re.compile(
    r"\b(speak|talk|connect|transfer\w*|chat)\b[ ,]*(to|with|me to|me with)[ ,]*"
    r"(a |an |the |your )?" + _HUMAN + r"\b"
    r"|\b(real|actual|live) (person|human|agent|representative|rep|employee|staff)\b"
    r"|\b(a |an )?" + _HUMAN + r" (please|now|right now|asap|pls)\b"
    r"|\bhuman (being|help|support|agent|one)\b"
    r"|\bcustomer (service|care|support) (rep|reps|representative|agent|team|person)\b"
    r"|\b(speak|talk|chat) (to|with) (someone|somebody|anybody|a real person)\b"
    r"|\bsomeone (real|from (your|the) team|on (this|the) (chat|line))\b"
    r"|\bescalate (this|it|me|my|to)\b"
    r"|\b((no more|stop with the|done with the) (bot|chatbot|robot)|get me off (this|the) "
    r"(bot|chat))\b"
    r"|\byour (supervisor|manager)\b"
    # Chinese escalation cues: 人工客服/真人/转人工
    r"|(转人工|转给人工|接人工|换人工|找人工|要人工|人工客服|人工服务|人工台)"
    r"|(找个?真人|要真人|换真人|跟真人|和真人|接真人|不是机器人|别.{0,4}机器人)"
    r"|(找客服|要客服|叫客服|请客服|客服来|客服呢|客服在哪|客服在吗)"
    r"|(主管|经理|负责人|领导|上级).{0,6}(回电|电话|联系|说话|来|接|找我|给我)"
    r"|(别扯|别说|不要跟我|不想跟).{0,10}(机器|自动|废话|这些)"
    r"|^\s*(人工|真人)\s*[。.!！?？]*\s*$", re.I)

# A looser second pass for "get me a human" / "I need a human" style asks. The human noun must sit
# at a clause boundary (end, punctuation, or a help/talk word), so "get me a human please" matches
# but "get me the manager cut blazer" does not (the noun is followed by a product word).
_ESCALATE_LOOSE = re.compile(
    r"\b(get|give) (me )?(a |an |the )?" + _HUMAN
    + r"\b\s*([.!?,]|please|now|asap|on (this|the) (chat|line|call)|$)"
    r"|\bi (want|need|wanna)\b[ ,]*(to (speak|talk) to )?(a |an )?" + _HUMAN
    + r"\b\s*([.!?,]|please|now|not an ai|on (this|the) (chat|line|call)|$)"
    r"|\b(hand|refer|put|transfer)\b[ ,]*(me |this |it )?(over |off |through )?"
    r"(to|with)[ ,]*(a |an |the |your )?" + _HUMAN
    + r"\b\s*([.!?,]|please|now|right away|asap|agent|rep|representative|$)", re.I)

# Router-only lane cues that supplement the shared intent guards. The linear brain's guards are
# tuned narrowly for its recommend-versus-abstain logic; routing wants wider coverage so common
# phrasings land deterministically instead of paying for the small-model tie-break. Kept here, not
# in rag.guards, so the linear path is untouched. Domain-neutral (no product nouns or brand words).
_STYLIST_CUE = re.compile(
    r"\b(style|styling|outfit|wardrobe|capsule)\b"
    r"|\b(go|goes|pair|pairs|match)\b\s+(with|together)\b"
    r"|\bwhat\b[^.?!]{0,30}\bgo(es)?\s+with\b"
    r"|\bwhat (shoes|pants|top|tops|shirt|shirts|colou?rs?|accessor\w+|to wear)\b"
    r"|\bhow (do i|to|would you|should i)\b[^.?!]{0,24}\b(style|wear|dress|pair)\b"
    r"|\b(any ideas|ideas for|smart casual|black tie|dressed up|trending|which of your|"
    r"petite)\b"
    # Chinese stylist / recommendation cues: 推荐、搭、选、买什么、有什么好、礼物
    r"|(推荐|推薦|推选|举荐|安利|种草|性价比高)"
    r"|(怎么搭|如何搭|搭配|穿搭|整套|一套|配什么|配啥|搭啥)"
    r"|(买什么|买啥|选什么|选啥|挑什么|挑款|入手什么|有什么好(的|看|选|买|穿)|"
    r"什么.*(好|合适|适合).{0,6}(推荐|跑鞋|鞋|裤|衣|服|内衣|外套)|"
    r"预算.{0,8}(以内|以下|左右|块|元))"
    r"|(礼物|送人|送给|给.{1,4}(买|挑|选|送)|生日(礼物)?|节日礼物)"
    r"|(入门|新手|刚开始|初学).{0,10}(选|买|推荐|跑步|瑜伽|健身)"
    r"|(冬天|夏天|春秋|户外|跑步|爬山|健身|瑜伽|通勤).{0,8}(穿|搭|装备|推荐)"
    # Chinese cross-brand / product comparison (stylist, not factual answers):
    #   "Lululemon的运动内衣和Nike的哪个支撑性更好"
    #   "Align和Wunder Train有什么区别"
    #   "Under Armour和Nike的紧身衣哪个排汗更好"
    r"|([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff]{1,12})的?.{0,8}"
    r"(和|跟|与|对比|比较|versus|vs)\s*"
    r"([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff]{1,12}).{0,12}"
    r"(哪个更|哪种更|哪款更|哪双更|哪个比较|哪种比较|哪款比较|"
    r"更(好|合适|适合|值得|推荐|舒服|保暖|透气|排汗|支撑|软|硬|耐穿|划算)|"
    r"区别|差别|差异|怎么选|如何选|选哪个|选哪种|选哪款)"
    r"|([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff]{1,12})"
    r"\s*(和|跟|与)\s*"
    r"([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff]{1,12})"
    r".{0,6}(有什么区别|有啥区别|有什么不同|有啥不同|区别是)",
    re.I)

# Order ids are two capitals plus digits, matched case-sensitively so a lowercase product code
# ("ab1234") is not mistaken for an order. Checked separately in _intent_lanes because the rest of
# the care cue is case-insensitive.
_ORDER_ID = re.compile(r"\b[A-Z]{2}\d{4,}\b")
_CARE_CUE = re.compile(
    r"\bmy (order|orders|package|parcel|deliver\w*|shipment|tracking|return|returns|account|"
    r"subscription|refund|store credit|loyalty)\b"
    r"|\b(return|send back|sending back|take back) (my|this|it|these|them|the)\b"
    r"|\bwant (my|a) (refund|money back)\b|\b(refund|money back) (please|on my|for my)\b"
    r"|\bwhen (will|is|does) my (order|package|parcel|delivery|stuff|shipment)\b[^.?!]{0,20}"
    r"\b(arrive|arriving|ship|shipped|get here|here|coming|deliver\w*)\b"
    r"|\b(eta on my|tracking (number|info|for my)|loyalty points|store credit|order status)\b"
    r"|\bleft the warehouse\b|\b(did|has|have) my (return|order|package|parcel|refund)\b"
    r"|\bmy (last|recent|previous) (purchase|order)\b"
    r"|\b(what did i buy|what i bought|total on my)\b"
    # Chinese account / order / after-sales cues.
    # Order-status / account actions are strong care signals; bare policy
    # questions (退换货政策、包邮条件) intentionally do NOT match here because
    # they are factual answers and the answers lane handles them with retrieval.
    r"|(我的)?(订单|快递|物流|包裹).{0,8}(到哪|到哪了|到什么|状态|发货|送货|签收|进度|查|看|追踪|跟踪)"
    r"|(查|找|看|追踪|跟踪).{0,4}(我的)?(订单|快递|物流|包裹|单号|退款|退货|积分|余额)"
    r"|(我的|咱).{0,4}(退款|积分|余额|优惠券|账户|账号|会员|收货地址|地址)"
    r"|(退|换)(款|货).{0,6}(到|到账|没|进度|流程|申请了?)"
    r"|(没|未|还没|还未).{0,6}(收到|发货|送到|到货|到账|退款)"
    # Chinese account self-service: change shipping address / phone after an order
    r"|(改|修改|换|变更|更新).{0,6}(收货地址|配送地址|送货地址|地址|电话|手机号|联系方式|收件人)"
    r"|(刚搬家|搬(家|了)|换地址|地址填错|地址错了|写错地址)"
    r"|(RF|EM|YZ|PC)\d{4,}", re.I)

# A complaint. Garment-damage words ("torn", "stain", "ripped") are matched ONLY in a problem frame
# (arrived/came/is/has), so catalog styles like "ripped jeans" or "stain-resistant" do not read as
# complaints. (The shared problem_intent guard still fires on bare damage words for the linear
# path; that is its long-standing behavior and out of scope here.)
_COMPLAINT_CUE = re.compile(
    r"\b(arrived|came|showed up|shipped|received|has a|had a|got a|there'?s a|with a)\b[^.?!]{0,18}"
    r"\b(hole|torn|ripped|stain(ed)?|scuff\w*|peel\w*|unravel\w*|frayed|defect\w*|damaged|"
    r"broken|cracked|falling apart)\b(?!\s*-\s*(resistant|proof|repellent|in)\b)"
    r"|\b(wrong (size|colou?r|item|order)|not what i ordered|someone else'?s (order|package))\b"
    r"|\b(charged|billed)\b[^.?!]{0,24}\b(twice|two times|again|double|duplicate|extra)\b"
    r"|\b(double|duplicate|extra) (charge|charges|payment|billing)\b"
    r"|\bnever (arrived|received|got|showed up|authorized|authorised|signed up)\b"
    r"|\b(says|marked) (delivered|shipped)\b[^.?!]{0,24}\b(but|nothing|missing|empty|not here)\b"
    r"|\btracking\b[^.?!]{0,18}\b(hasn'?t|not|stopped)\b[^.?!]{0,10}\b(moved|updated|update)\b"
    r"|\bstill (waiting|no (package|refund|update))\b"
    r"|\brefund\b[^.?!]{0,30}\b(still|hasn'?t|weeks|not (here|received))\b"
    r"|\bcancel\w*\b[^.?!]{0,24}\b(without|no (reason|explanation|warning))\b"
    r"|\b(this is (ridiculous|unacceptable)|fed up|so frustrated|ruined my)\b"
    r"|\b(zipper|strap|button|buttons|seam|seams|sole|heel|stitching|clasp|zip|elastic|thread)\b"
    r"[^.?!]{0,14}\b(broke|snapped|tore|torn|split|came (apart|undone|off)|unravel\w*|"
    r"stopped working)\b"
    r"|\b(broke|snapped|tore|split|unravel\w*|came apart) (after|on|within|the first|during)\b"
    r"|\bfell (off|apart)\b|\bwrong address\b"
    # Chinese complaint cues: 质量/损坏/发错/重复扣款/没收到
    r"|(发错货|发错了|寄错|装错|货不对板|不是我(订|买|拍)的|别人的订单|别人的包裹)"
    r"|(质量(太差|问题|不好|真差)|太差劲|离谱|什么东西|骗人|坑人|黑心)"
    r"|((开线|脱线|起球|掉色|褪色|破洞|破损|坏了|裂了|断了|松了|掉了).{0,6}"
    r"(刚|才|一次|洗了|穿了|收到))"
    r"|(刚(收到|拆开|拆封)).{0,12}(开线|脱线|起球|掉色|破损|破洞|坏|瑕疵|缺陷|脏)"
    r"|((扣|收).{0,4}(两次|两次钱|两笔|重复)|重复(扣款|扣费|收费|付款)|双(倍|重)(扣|收费))"
    r"|(显示已签收|显示签收|物流显示).{0,12}(但|却|可是|然而)?(没|未|没有|根本).{0,4}(收到|拿到|见)"
    r"|(一个星期|一周|十几天|半个月|好几天|这么久).{0,8}(还没|还未|仍未|都没).{0,4}"
    r"(发|发货|到|送到|到货|收到|更新|消息|动静)"
    r"|(说好|承诺|答应).{0,8}(三天|次日|当天|今天|明天).{0,8}(到|发|送).{0,12}(现在|结果|可是|还没)"
    r"|(客服呢|客服在哪|怎么回事|给个说法|必须|赶紧|马上|立刻).{0,8}(退款|退货|赔偿|解决|处理)"
    r"|(退款|退货).{0,12}(超时|十天|一周|没到账|未到账).{0,12}(升级|处理|解决|投诉)"
    r"|(洗了一次|穿了一次|穿.{0,3}次|才穿|才洗|没用几次).{0,12}"
    r"(起球|掉色|变形|缩水|破|坏|开胶|断底)",
    re.I)

# Confidence per single-intent lane. Complaint is most certain (its cues are specific), a shopping
# request least (its cues are broad), so a low-confidence stylist route is re-checked first.
_INTENT_CONF = {"complaint": 0.85, "care": 0.8, "stylist": 0.75}


@dataclass
class RouteDecision:
    lane: str
    confidence: float
    layer: int  # 0 deterministic intercept, 1 intent guard, 2 small-model tie-break
    reason: str
    tasks: list[str] = field(default_factory=list)  # more than one when the turn needs a plan
    clarify: dict | None = None  # {"axis","a","b"} when asking beats guessing


def _intent_lanes(query: str) -> list[str]:
    """The service lanes whose deterministic intent fires, in resolution priority: a complaint
    leads (empathy before anything else), then an own-account lookup, then a shopping request."""
    lanes = []
    # complaint uses ONLY the frame-anchored cue, not the shared problem_intent guard, which fires
    # on bare damage words ("ripped jeans") that are catalog styles as often as complaints. A bare
    # damage word is genuinely ambiguous, so it is deferred to the small-model tie-break instead of
    # being decided confidently at layer 1.
    if _COMPLAINT_CUE.search(query):
        lanes.append("complaint")
    if account_intent(query) or _CARE_CUE.search(query) or _ORDER_ID.search(query):
        lanes.append("care")
    if shopping_intent(query) or _STYLIST_CUE.search(query):
        lanes.append("stylist")
    return lanes


def route(query: str, *, history: list | None = None, signed_in: bool = False,
          small_llm=None, tiebreak_system: str | None = None) -> RouteDecision:
    q = (query or "").strip()
    if not q:
        return RouteDecision("answers", 0.3, 0, "empty query")

    # Layer 0: an explicit request to reach a person outranks every other signal, unless it is a
    # refusal ("I don't want to talk to a human"), which must not escalate or file a case.
    if (_ESCALATE.search(q) or _ESCALATE_LOOSE.search(q)) and not _NO_HUMAN.search(q):
        return RouteDecision("escalation", 0.95, 0, "explicit request for a person")

    # Layer 1: the deterministic intent guards. One match decides. Two competing matches become a
    # multi-task plan (complaint first) that the heavy path fans out and stitches back together.
    lanes = _intent_lanes(q)
    if len(lanes) == 1:
        return RouteDecision(lanes[0], _INTENT_CONF[lanes[0]], 1, "intent guard: " + lanes[0])
    if len(lanes) > 1:
        return RouteDecision(lanes[0], 0.7, 1, "multiple intents, complaint-first plan",
                             tasks=lanes)

    # Layer 2: nothing fired. A cheap model tie-breaks into a lane or asks; with no model available
    # (offline, tests) fall back to the answers lane, which self-gates on facts, policy, and
    # catch-all and never fabricates.
    if small_llm is not None:
        decided = _model_tiebreak(q, small_llm, system=tiebreak_system)
        if decided is not None:
            return decided
    return RouteDecision("answers", 0.5, 1, "no intent fired, answers catch-all")


# Promoted from the prompt-optimization loop (docs/prompt-optimization.md): a conservative tie-break
# that prefers answers on general questions and reserves unclear for genuinely two-intent turns,
# rather than guessing a specialist lane. Human-reviewed and promoted from the candidate at
# mlops/prompt_registry/tiebreak_system.candidate.json (held-out routing test 73.9% -> 79.5%).
_TIEBREAK_SYSTEM = (
    "You are a strict router for a shopping assistant. Read the shopper's message and reply with "
    "ONLY a JSON object {\"lane\": L} where L is one of: stylist (specific product combination or "
    "gift ideas), care (direct reference to their own order or account), complaint (explicit "
    "problem, delay, or billing issue), answers (general or policy question, or seeking "
    "information), escalation (they explicitly ask to reach a human, agent, or representative), "
    "unclear (genuinely ambiguous between two specific intents). Prioritize answers "
    "for general inquiries and defer to unclear only when a message clearly conveys multiple "
    "distinct intents. No prose, only the JSON."
)


def _model_tiebreak(query: str, small_llm, system: str | None = None) -> RouteDecision | None:
    """One cheap classification call for the minority of turns the deterministic layers cannot
    place. On 'unclear' it returns a two-option clarify rather than a guess. Any parse or model
    failure returns None so the caller falls back to the answers catch-all. `system` overrides the
    tie-break prompt so a candidate from the prompt-optimization loop can be scored without an
    edit."""
    try:
        raw = small_llm.generate(query, system=system or _TIEBREAK_SYSTEM, max_tokens=40).text
    except Exception:
        return None
    match = re.search(r'"lane"\s*:\s*"([a-z]+)"', raw or "")
    lane = match.group(1) if match else ""
    if lane == "escalation":
        # an explicit human request the English-only Layer 0 regexes missed (a non-English phrasing
        # or a typo); the tie-break is the safety net so it can still reach a person
        return RouteDecision("escalation", 0.7, 2, "small-model tie-break, human request")
    if lane in ("stylist", "care", "complaint", "answers"):
        return RouteDecision(lane, 0.65, 2, "small-model tie-break")
    if lane == "unclear":
        # the most common genuine ambiguity: a gift idea versus a problem with an order. Ask the
        # one question that splits them instead of guessing and risking the wrong tone.
        return RouteDecision("answers", 0.4, 2, "ambiguous, clarify",
                             clarify={"axis": "intent",
                                      "a": "a product or gift suggestion",
                                      "b": "help with an existing order"})
    return None
