"""
Scripted shop personas for testing and automated demo runs (SCRIPTED_SHOPS=1).

Design decision: Keeping shop definitions deterministic enables reliable,
reproducible end-to-end testing without external network or human telephone dependencies.
"""

from typing import Any, Dict, List

DEFAULT_SHOPS = [
    {
        "shop_id": "1",
        "shop_name": "Sri Ganesh Mobiles",
        "lang": "en",
        "opening_quote": 4500,
        "warranty_months": 6,
        "part_type": "OEM",
        "conditions": "GST extra",
        "eta_days": 1,
        "persona_type": "honest",
    },
    {
        "shop_id": "2",
        "shop_name": "Mobile Hub Indiranagar",
        "lang": "en",
        "opening_quote": 3900,
        "warranty_months": 3,
        "part_type": "Aftermarket",
        "conditions": "Today only discount",
        "eta_days": 2,
        "persona_type": "pushy",
    },
    {
        "shop_id": "3",
        "shop_name": "City Fix Corner",
        "lang": "hi",
        "opening_quote": 4100,
        "warranty_months": 1,
        "part_type": "Unknown",
        "conditions": "GST not confirmed",
        "eta_days": 3,
        "persona_type": "evasive",
    },
]


def get_shop_persona(shop_id: str) -> Dict[str, Any]:
    """Retrieve persona definition by shop_id with fallback."""
    for s in DEFAULT_SHOPS:
        if s["shop_id"] == shop_id:
            return dict(s)
    return {
        "shop_id": shop_id,
        "shop_name": f"Shop {shop_id}",
        "lang": "en",
        "opening_quote": 4000,
        "warranty_months": 3,
        "part_type": "OEM",
        "conditions": "",
        "eta_days": 1,
        "persona_type": "honest",
    }
