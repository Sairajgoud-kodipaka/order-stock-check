from app.milk import MilkProblem, apply_milk_rule


def test_rule_uses_two_percent_when_the_customer_does_not_choose_a_milk():
    resolved = apply_milk_rule([("espresso_signature", 1)])

    assert resolved.milk_id == "two_pct_milk"
    assert resolved.milk_defaulted is True
    assert ("two_pct_milk", 1) in resolved.items


def test_rule_keeps_the_milk_the_customer_chose():
    resolved = apply_milk_rule([("espresso_signature", 2), ("oat_milk", 1)])

    assert resolved.milk_id == "oat_milk"
    assert resolved.milk_defaulted is False
    assert ("oat_milk", 2) in resolved.items


def test_rule_asks_for_one_milk_when_two_are_sent():
    resolved = apply_milk_rule(
        [("espresso_signature", 1), ("oat_milk", 1), ("almond_milk", 1)]
    )

    assert isinstance(resolved, MilkProblem)
    assert "Choose one milk" in resolved.message
    assert "did not place this order" in resolved.message
