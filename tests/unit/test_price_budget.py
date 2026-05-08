from eventflow.domain.price_budget import budget_band, parse_price_to_minor_units


def test_parse_price_minor_basic():
    assert parse_price_to_minor_units(None) is None
    assert parse_price_to_minor_units("") is None
    assert parse_price_to_minor_units("free") == 0
    assert parse_price_to_minor_units("$25") == 2500
    assert parse_price_to_minor_units("25.50") == 2550
    assert parse_price_to_minor_units("GA — $40") == 4000


def test_budget_band():
    assert budget_band(spent_minor=100, budget_minor=None) == "unset"
    assert budget_band(spent_minor=100, budget_minor=0) == "unset"
    assert budget_band(spent_minor=50, budget_minor=100) == "under"
    assert budget_band(spent_minor=86, budget_minor=100) == "tight"
    assert budget_band(spent_minor=101, budget_minor=100) == "over"
