import pytest
from backend import extract, normalize
from backend.models import Offer, Turn


def test_parse_price_numeric_and_currency():
    """Verify numeric and currency formatting."""
    assert normalize.parse_price("4500")[0] == 4500
    assert normalize.parse_price("Rs. 4500")[0] == 4500
    assert normalize.parse_price("₹4,500")[0] == 4500
    assert normalize.parse_price("INR 3800/-")[0] == 3800


def test_parse_price_k_multiplier():
    """Verify 'k' multipliers."""
    assert normalize.parse_price("1.2k")[0] == 1200
    assert normalize.parse_price("4.5k")[0] == 4500
    assert normalize.parse_price("3k")[0] == 3000


def test_parse_price_english_words():
    """Verify English word forms."""
    assert normalize.parse_price("twelve hundred")[0] == 1200
    assert normalize.parse_price("four thousand five hundred")[0] == 4500
    assert normalize.parse_price("forty five hundred")[0] == 4500
    assert normalize.parse_price("three thousand")[0] == 3000


def test_parse_price_hindi_phrases():
    """Verify Hindi words (pandrah sau, chaar hazaar paanch sau)."""
    assert normalize.parse_price("pandrah sau")[0] == 1500
    assert normalize.parse_price("bais sau")[0] == 2200
    p, conf = normalize.parse_price("chaar hazaar paanch sau")
    assert p == 4500


def test_parse_price_uncertainty():
    """Verify lower confidence on approximate language."""
    p, conf = normalize.parse_price("around 1500 with GST")
    assert p == 1500
    assert conf < 1.0

    p2, conf2 = normalize.parse_price("lagbhag 4000")
    assert p2 == 4000
    assert conf2 < 1.0


def test_parse_months():
    """Verify warranty months parsing."""
    assert normalize.parse_months("6 months")[0] == 6
    assert normalize.parse_months("1 year")[0] == 12
    assert normalize.parse_months("half year")[0] == 6
    assert normalize.parse_months("chhe mahine")[0] == 6
    assert normalize.parse_months("no warranty")[0] == 0


def test_parse_days():
    """Verify ETA days parsing."""
    assert normalize.parse_days("same day repair")[0] == 0
    assert normalize.parse_days("today itself")[0] == 0
    assert normalize.parse_days("tomorrow morning")[0] == 1
    assert normalize.parse_days("kal aayega")[0] == 1
    assert normalize.parse_days("3 days")[0] == 3


def test_parse_part_type():
    """Verify part type classification."""
    assert normalize.parse_part_type("Apple original part")[0] == "OEM"
    assert normalize.parse_part_type("asli display")[0] == "OEM"
    assert normalize.parse_part_type("compatible first copy")[0] == "Aftermarket"
    assert normalize.parse_part_type("standard screen")[0] == "Unknown"


def test_extract_offer_with_evidence():
    """Verify multi-turn offer extraction and evidence timestamp linking."""
    turns = [
        Turn(call_id="c_test", speaker="agent", text="What is the price?", ts=10.0),
        Turn(call_id="c_test", speaker="shop", text="We can do it for 4500 with 6 months warranty, OEM part", ts=12.5),
        Turn(call_id="c_test", speaker="shop", text="If you confirm today, final price is 4200", ts=20.0),
    ]

    offer = extract.extract_offer(turns, call_id="c_test")
    assert offer.first_price == 4500
    assert offer.price == 4200
    assert offer.warranty_months == 6
    assert offer.part_type == "OEM"
    assert "price" in offer.evidence
    assert offer.evidence["price"]["turn_ts"] == 20.0
    assert offer.evidence["warranty"]["turn_ts"] == 12.5


def test_conflict_detection():
    """Verify price and warranty discrepancies generate ConflictEvents."""
    old_offer = Offer(
        call_id="c_test",
        price=4500,
        warranty_months=6,
        evidence={"price": {"turn_ts": 10.0}, "warranty": {"turn_ts": 10.0}},
    )
    new_offer = Offer(
        call_id="c_test",
        price=4200,
        warranty_months=3,
        evidence={"price": {"turn_ts": 25.0}, "warranty": {"turn_ts": 25.0}},
    )

    conflicts = extract.detect_conflicts(old_offer, new_offer, current_turn_ts=25.0)
    assert len(conflicts) == 2
    fields = {c.field for c in conflicts}
    assert "price" in fields
    assert "warranty_months" in fields
    p_conf = next(c for c in conflicts if c.field == "price")
    assert p_conf.old_value == "4500"
    assert p_conf.new_value == "4200"
