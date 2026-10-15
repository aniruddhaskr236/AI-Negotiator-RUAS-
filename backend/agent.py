"""
Agent utterance generator with mandatory AI disclosure, number guard, and template fallbacks.

Design decision: The Number Guard audits every generated utterance against
verified session quotes before sending it to the shop. If an LLM attempts
to hallucinate an uncollected price, the Number Guard catches it and falls back
to a safe verified template.
"""

import asyncio
import re
from typing import List, Optional, Tuple

from backend.config import logger
from backend.llm import call_llm
from backend.models import Turn
from backend.negotiation import NegotiationAction
from backend.normalize import parse_price

# ---------------------------------------------------------------------------
# Deterministic Template Fallbacks (En, Hi, Kn)
# ---------------------------------------------------------------------------

TEMPLATES = {
    "greet": {
        "en": "Hello! I'm an AI assistant calling on behalf of a customer. Is it okay if I ask a few quick questions about {need}?",
        "hi": "Namaste! Main ek customer ki taraf se call kar raha AI assistant hoon. Kya main {need} ke baare me kuch sawal pooch sakta hoon?",
        "kn": "Namaskara! Naanu customer paravagi call maduthiruva AI assistant. {need} bagge kelavu prashnegala kelabahuda?",
    },
    "ask_price": {
        "en": "Could you please tell me your price for {need}?",
        "hi": "{need} ke liye aapka kya charge hoga bhai?",
        "kn": "{need} ge eshtu charge aagutthe?",
    },
    "ask_warranty": {
        "en": "Got it. How much warranty do you provide on this repair?",
        "hi": "Theek hai. Is repair par kitne mahine ki warranty milegi?",
        "kn": "Sari. Ee repair ge eshtu tingala warranty ide?",
    },
    "ask_part_type": {
        "en": "Is the replacement part an original OEM screen or a compatible aftermarket one?",
        "hi": "Kya yeh original display hai ya first copy aftermarket screen hai?",
        "kn": "Idu original company screen aa athava copy screen aa?",
    },
    "confirm_conflict": {
        "en": "Just to be clear, earlier you mentioned {old_v}, but now it is {new_v}. Could you please confirm the final figure?",
        "hi": "Pehle aapne {old_v} bola tha, abhi {new_v} bol rahe hain. Final kya rate hai bhai?",
        "kn": "Modalu {old_v} helidri, eega {new_v} heltidiri. Final price yavudu?",
    },
    "counter_with_real_quote": {
        "en": "Another reputed repair shop offered Rs {comp_p} with {comp_w} months warranty. Can you match or beat that price?",
        "hi": "Dusre shop se hume Rs {comp_p} aur {comp_w} mahine ki warranty ka quote mila hai. Kya aap isse kam kar sakte hain?",
        "kn": "Bereda shop alli Rs {comp_p} matthe {comp_w} tingala warranty kottidare. Neevu adakkinta kammi madoke aaguttha?",
    },
    "ask_best_discount": {
        "en": "Understood. Is there any discount or best price you can offer if we confirm today?",
        "hi": "Achha, agar hum aaj hi karaate hain toh kuch discount mil sakta hai kya?",
        "kn": "Sari, naavu ivatte madisidre enadru discount siguttha?",
    },
    "close": {
        "en": "Thank you for the information. I will share all the details with my customer and let them decide. Have a great day!",
        "hi": "Shukriya bhai saari jaankari ke liye. Main customer ko bata deta hoon, wo decide karenge. Dhanyawad!",
        "kn": "Information kottiddakke thanks. Naanu customer ge thilisi decide madtheeni. Dhanyavadagalu!",
    },
}


def get_template_fallback(
    intent: str,
    lang: str = "en",
    need: str = "screen replacement",
    comp_price: Optional[int] = None,
    comp_warranty: Optional[int] = None,
    old_v: Optional[str] = None,
    new_v: Optional[str] = None,
) -> str:
    """Returns a deterministic safe sentence for a given intent and language."""
    lang_key = lang if lang in ("en", "hi", "kn") else "en"
    intent_dict = TEMPLATES.get(intent, TEMPLATES["close"])
    text_pattern = intent_dict.get(lang_key, intent_dict["en"])

    return text_pattern.format(
        need=need,
        comp_p=comp_price or 0,
        comp_w=comp_warranty or 3,
        old_v=old_v or "",
        new_v=new_v or "",
    )


def audit_number_guard(
    candidate_text: str,
    action: NegotiationAction,
    current_shop_price: Optional[int],
) -> bool:
    """
    Number Guard Hard Rule:
    Verifies that any price stated in the candidate text strictly corresponds to:
    1. The authorized competing quote (action.competing_quote), OR
    2. The shop's own stated price (current_shop_price)
    Returns True if valid, False if a hallucinated price is detected.
    """
    found_price, _ = parse_price(candidate_text)
    if found_price is None:
        return True  # No price cited, completely safe

    allowed_prices = set()
    if action.competing_quote is not None:
        allowed_prices.add(action.competing_quote)
    if current_shop_price is not None:
        allowed_prices.add(current_shop_price)

    # If the text cites a number not in the allowed session quotes, reject it
    if found_price not in allowed_prices:
        logger.warning(
            "Number Guard REJECTED candidate text. Hallucinated price: %s (Allowed: %s)",
            found_price,
            allowed_prices,
        )
        return False

    return True


async def generate_agent_utterance(
    need: str,
    action: NegotiationAction,
    dialogue_history: List[Turn],
    target_lang: str = "en",
    current_shop_price: Optional[int] = None,
) -> Tuple[str, Optional[str]]:
    """
    Generates the next agent utterance.
    Enforces:
    - Mandatory AI disclosure on greeting
    - Number Guard check against hallucinated prices
    - Safe template fallbacks
    Returns: (utterance_in_target_lang, english_translation)
    """
    # 1. GREET is always exact and deterministic to guarantee full disclosure
    if action.intent == "greet":
        text = get_template_fallback("greet", lang=target_lang, need=need)
        trans = get_template_fallback("greet", lang="en", need=need) if target_lang != "en" else None
        return text, trans

    # 2. Template fallback default
    fallback_text = get_template_fallback(
        intent=action.intent,
        lang=target_lang,
        need=need,
        comp_price=action.competing_quote,
        comp_warranty=action.competing_warranty,
        old_v=action.conflict_old_value,
        new_v=action.conflict_new_value,
    )
    fallback_en = (
        get_template_fallback(
            intent=action.intent,
            lang="en",
            need=need,
            comp_price=action.competing_quote,
            comp_warranty=action.competing_warranty,
            old_v=action.conflict_old_value,
            new_v=action.conflict_new_value,
        )
        if target_lang != "en"
        else None
    )

    # 3. LLM Generation
    system_prompt = (
        "You are an AI negotiation assistant calling a phone repair shop on behalf of a customer. "
        "Rules: Speak in 1 or 2 polite, concise sentences. "
        f"Language: {target_lang}. "
        "Never invent competing prices. "
        "Never commit to buy; say you will inform the customer. "
    )

    prompt = (
        f"Goal: {action.intent}. "
        f"Repair Need: {need}. "
        f"Competing quote if any: {action.competing_quote}. "
        f"Shop's latest price: {current_shop_price}. "
        f"Recent conversation turns: {[t.text for t in dialogue_history[-4:]]}. "
        "Provide your next response in 1-2 short sentences."
    )

    try:
        # 3s timeout on LLM call with an overall 4s budget
        candidate = await asyncio.wait_for(
            call_llm(prompt=prompt, system=system_prompt, timeout=3.0),
            timeout=4.0,
        )
        candidate = candidate.strip().strip('"')

        # Real-time budget: at most 25 words
        words = candidate.split()
        if len(words) > 25:
            candidate = " ".join(words[:25])
            if not candidate.endswith((".", "?", "!")):
                candidate += "."

        # Check Number Guard
        if audit_number_guard(candidate, action, current_shop_price):
            # Check agreement to buy guard
            lower_c = candidate.lower()
            if any(forbidden in lower_c for forbidden in ["i will buy", "deal done", "book it", "confirm order", "i agree to buy"]):
                logger.warning("Agent utterance contained forbidden purchase agreement. Using fallback.")
                return fallback_text, fallback_en

            return candidate, None
        else:
            return fallback_text, fallback_en

    except Exception as exc:
        logger.warning("LLM utterance generation failed or budget exceeded (%s), using safe template", exc)
        return fallback_text, fallback_en
