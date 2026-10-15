"""
Deterministic ShopSimulator for scripted offline/demo runs (SCRIPTED_SHOPS=1).

Design decision: Simulates three distinct psychological personas without network dependencies:
1. Sri Ganesh Mobiles: Honest, opens Rs 4500 (OEM, 6mo), drops to 4200 then 3800 when pushed.
2. Mobile Hub Indiranagar: Pushy, opens Rs 3900 (Aftermarket, 3mo), changes price mid-call.
3. City Fix Corner: Evasive, opens Rs 4100 (unclear warranty), avoids GST, hangs up after 4 turns.
"""

from typing import Optional, Tuple


class ShopSimulator:
    """Simulates dialogue turns for a specific shop persona."""

    def __init__(self, shop_id: str):
        self.shop_id = str(shop_id)
        self.turn = 0
        self.current_price = 4500 if self.shop_id == "1" else (3900 if self.shop_id == "2" else 4100)

    def respond(
        self,
        agent_utterance: str,
        competing_quote: Optional[int] = None,
    ) -> Tuple[str, str, bool]:
        """
        Generates deterministic shop response.
        Returns: (text, lang, hangup)
        """
        self.turn += 1
        lower_agent = agent_utterance.lower()

        # -------------------------------------------------------------------
        # SHOP 1: Sri Ganesh Mobiles (Honest, OEM, lowers price when pushed)
        # -------------------------------------------------------------------
        if self.shop_id == "1":
            lang = "en"
            if self.turn == 1:
                return (
                    "Haanji, for iPhone 13 original OEM screen replacement it will be Rs 4500 with 6 months warranty. GST extra.",
                    lang,
                    False,
                )
            if competing_quote is not None and competing_quote < self.current_price:
                if self.current_price == 4500:
                    self.current_price = 4200
                    return (
                        f"Okay, since another shop offered Rs {competing_quote}, I can reduce my price to Rs 4200 with the same 6 months warranty.",
                        lang,
                        False,
                    )
                else:
                    self.current_price = 3800
                    return (
                        "Last best price Rs 3800 kar denge bhai for original display. This is my final bottom rate.",
                        lang,
                        False,
                    )
            if "discount" in lower_agent or "best" in lower_agent:
                self.current_price = 4200
                return (
                    "If you come today, I can do it for Rs 4200 with 6 months warranty.",
                    lang,
                    False,
                )
            return ("Rs 3800 is my final price with genuine OEM screen and 6 months warranty. Thank you.", lang, False)

        # -------------------------------------------------------------------
        # SHOP 2: Mobile Hub Indiranagar (Pushy, aftermarket, changes price mid-call)
        # -------------------------------------------------------------------
        if self.shop_id == "2":
            lang = "en"
            if self.turn == 1:
                return (
                    "Hello! We have aftermarket first copy display for 3900 rupees with 3 months warranty. Sirf aaj ke liye offer hai!",
                    lang,
                    False,
                )
            if self.turn == 2:
                # Deliberate conflict injection: changes price to 4200 citing stock
                self.current_price = 4200
                return (
                    "Wait bhai, I just checked inventory, that piece was sold. Next lot is Rs 4200 with 3 months warranty.",
                    lang,
                    False,
                )
            if "confirm" in lower_agent or "earlier" in lower_agent or "rate" in lower_agent:
                return (
                    "Yes, final price is Rs 4200 today only because stock is very limited.",
                    lang,
                    False,
                )
            return (
                "Take it for Rs 4200, this is my final fixed price, cannot reduce further.",
                lang,
                False,
            )

        # -------------------------------------------------------------------
        # SHOP 3: City Fix Corner (Evasive, Hindi, does not confirm GST, hangs up)
        # -------------------------------------------------------------------
        if self.shop_id == "3":
            lang = "hi"
            if self.turn == 1:
                return (
                    "Haan screen mil jayega. 4100 lagega, 2-3 din me ho jayega.",
                    lang,
                    False,
                )
            if self.turn == 2:
                return (
                    "Warranty ka dekhna padega shop aake. GST ka pata nahi bhai, bill bina GST ke milega.",
                    lang,
                    False,
                )
            if self.turn >= 3:
                # Hangs up on turn 3 or 4
                return (
                    "Abhi bahut customer hain shop me, baad me call karo.",
                    lang,
                    True,  # Triggers hangup
                )

        return ("Okay, let me know.", "en", False)
