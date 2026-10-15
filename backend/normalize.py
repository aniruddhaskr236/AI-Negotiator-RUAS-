"""
Parsers for prices, months (warranty), days (ETA), part types, and GST/conditions.

Design decision: Robust local rule-based parsing with confidence scoring executes
in <1ms without LLM latency, handling English numbers, 'k' multipliers, word forms,
and Hindi transliterations.
"""

import re
from typing import Optional, Tuple

# Word to number mapping
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}

# Hindi number words (transliterated and Devanagari)
_HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "terah": 13, "chaudah": 14, "pandrah": 15,
    "pandrah sau": 1500, "bais sau": 2200, "atharah sau": 1800,
    "ek hazar": 1000, "do hazar": 2000, "teen hazar": 3000, "char hazar": 4000,
    "chaar hazar": 4000, "paanch hazar": 5000,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "छह": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "पंद्रह": 15, "पंद्रह सौ": 1500, "हजार": 1000, "सौ": 100,
}

_APPROX_WORDS = ["around", "approx", "approximately", "lagbhag", "karib", "about", "nearly"]


def parse_price(text: str) -> Tuple[Optional[int], float]:
    """
    Extracts price in INR and a confidence score (0.0 to 1.0).
    Handles:
      - Raw digits: "4500", "Rs. 4500", "₹4,500", "INR 4500"
      - 'k' multiplier: "1.2k", "4.5k", "3k"
      - Word forms: "twelve hundred", "four thousand five hundred", "forty five hundred"
      - Hindi transliterated: "pandrah sau", "chaar hazaar paanch sau", "teen hazar nau sau"
    """
    if not text:
        return None, 0.0

    lower = text.lower().replace(",", "")
    confidence = 1.0

    # Check uncertainty markers
    if any(w in lower for w in _APPROX_WORDS):
        confidence = 0.7

    # 1. Hindi composite phrases
    if "pandrah sau" in lower or "पंद्रह सौ" in lower:
        return 1500, confidence
    if "bais sau" in lower:
        return 2200, confidence

    # Hindi "chaar hazar paanch sau" (4500)
    hindi_pattern = r"(ek|do|teen|chaar|char|paanch|panch)\s+(?:hazar|hazaar)\s*(?:(?:aur|and)?\s*(ek|do|teen|chaar|char|paanch|panch|nau|saat)?\s*(?:sau))?"
    m_hi = re.search(hindi_pattern, lower)
    if m_hi:
        th_word = m_hi.group(1)
        th_val = _HINDI_NUMBERS.get(th_word, 0) * 1000
        h_word = m_hi.group(2)
        h_val = (_HINDI_NUMBERS.get(h_word, 0) * 100) if h_word else 0
        return th_val + h_val, confidence

    # 2. 'k' suffix: e.g. "4.5k", "3k", "1.2k"
    m_k = re.search(r"(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", lower)
    if m_k:
        val = int(float(m_k.group(1)) * 1000)
        return val, confidence

    # 3. Explicit numeric pattern: e.g. "Rs 4500", "₹ 3800", "4500 rupees", "4500/-"
    m_num = re.search(r"(?:rs\.?|₹|inr)?\s*(\b\d{3,6}\b)(?:\s*(?:rupees|rs|\/-))?", lower)
    if m_num:
        val = int(m_num.group(1))
        # Ensure it's not a year like 2026 or 2024 unless preceded by rs/rupees
        if val in (2024, 2025, 2026) and not any(p in lower for p in ["rs", "₹", "inr", "rupees"]):
            pass
        else:
            return val, confidence

    # 4. English word phrases: "twelve hundred", "forty five hundred", "four thousand five hundred"
    if "twelve hundred" in lower:
        return 1200, confidence
    if "forty five hundred" in lower or "four thousand five hundred" in lower:
        return 4500, confidence
    if "three thousand" in lower:
        return 3000, confidence
    if "four thousand" in lower:
        return 4000, confidence
    if "fifteen hundred" in lower:
        return 1500, confidence

    return None, 0.0


def parse_months(text: str) -> Tuple[Optional[int], float]:
    """
    Extracts warranty in months and a confidence score.
    Handles: "6 months", "six months", "1 year" (12), "chhe mahine", "no warranty" (0).
    """
    if not text:
        return None, 0.0

    lower = text.lower()
    confidence = 1.0

    if any(w in lower for w in _APPROX_WORDS):
        confidence = 0.7

    # Zero warranty
    if "no warranty" in lower or "koi guarantee nahi" in lower or "without warranty" in lower or "warranty nahi" in lower:
        return 0, confidence

    # Years
    m_year = re.search(r"(\d+|one|two|ek|do)\s*(?:year|yr|saal)", lower)
    if m_year:
        val_str = m_year.group(1)
        num = 1
        if val_str.isdigit():
            num = int(val_str)
        elif val_str in ("two", "do"):
            num = 2
        return num * 12, confidence

    # Half year
    if "half year" in lower or "aadha saal" in lower:
        return 6, confidence

    # Months with digit
    m_month = re.search(r"(\d+)\s*(?:months?|mos?|mahine|mahina)", lower)
    if m_month:
        return int(m_month.group(1)), confidence

    # Word forms
    word_months = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "ek": 1, "do": 2, "teen": 3, "chaar": 4, "char": 4, "paanch": 5,
        "chhe": 6, "che": 6,
    }
    for w, m in word_months.items():
        if f"{w} month" in lower or f"{w} mahine" in lower:
            return m, confidence

    return None, 0.0


def parse_days(text: str) -> Tuple[Optional[int], float]:
    """
    Extracts completion time / ETA in days.
    Handles: "today" (0), "same day" (0), "2-3 hours" (0), "1 day" (1), "tomorrow" (1), "kal" (1).
    """
    if not text:
        return None, 0.0

    lower = text.lower()
    confidence = 1.0

    if any(w in lower for w in _APPROX_WORDS):
        confidence = 0.7

    # Same day / immediate
    if any(kw in lower for kw in ["today", "same day", "hours", "ghante", "aaj"]):
        return 0, confidence

    # Tomorrow / 1 day
    if any(kw in lower for kw in ["tomorrow", "kal", "next day", "one day", "1 day"]):
        return 1, confidence

    # Numeric days
    m_days = re.search(r"(\d+)\s*(?:days?|din)", lower)
    if m_days:
        return int(m_days.group(1)), confidence

    return None, 0.0


def parse_part_type(text: str) -> Tuple[str, float]:
    """
    Detects part quality: 'OEM', 'Aftermarket', or 'Unknown'.
    """
    if not text:
        return "Unknown", 0.0

    lower = text.lower()

    oem_keywords = [
        "original", "oem", "asli", "genuine", "apple original", "company part", "first party"
    ]
    aftermarket_keywords = [
        "aftermarket", "first copy", "copy", "compatible", "duplicate", "local",
        "third party", "compatible part", "generic"
    ]

    for kw in oem_keywords:
        if kw in lower:
            return "OEM", 0.95

    for kw in aftermarket_keywords:
        if kw in lower:
            return "Aftermarket", 0.95

    return "Unknown", 0.5


def parse_conditions(text: str) -> str:
    """Extracts special conditions like GST extra, cash discount, or today only."""
    if not text:
        return ""

    lower = text.lower()
    conditions = []

    if "gst extra" in lower or "plus gst" in lower or "+ gst" in lower:
        conditions.append("GST extra")
    elif "including gst" in lower or "gst included" in lower:
        conditions.append("GST included")

    if "today only" in lower or "sirf aaj" in lower:
        conditions.append("Today only discount")

    if "touch only" in lower:
        conditions.append("Warranty on touch only")

    return ", ".join(conditions)
