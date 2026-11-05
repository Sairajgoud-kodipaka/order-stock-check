from app.stock import FIRST_HILL_STORE_ID, StockBook


def test_snapshot_math_for_first_hill_milk():
    book = StockBook.load()

    oat = book.get(FIRST_HILL_STORE_ID, "oat_milk")
    almond = book.get(FIRST_HILL_STORE_ID, "almond_milk")
    two_percent = book.get(FIRST_HILL_STORE_ID, "two_pct_milk")

    assert oat.store_name == "First Hill - Madison & Boylston"
    assert oat.store_open is True
    assert (oat.quantity_on_hand, oat.reserved_quantity, oat.available) == (0, 0, 0)
    assert (almond.quantity_on_hand, almond.reserved_quantity, almond.available) == (38, 1, 37)
    assert (two_percent.quantity_on_hand, two_percent.reserved_quantity, two_percent.available) == (96, 3, 93)


def test_first_hill_milk_report_marks_oat_milk_unsellable(client):
    response = client.get(f"/stores/{FIRST_HILL_STORE_ID}/milk")

    assert response.status_code == 200
    body = response.json()
    assert body["store_name"] == "First Hill - Madison & Boylston"
    assert body["rule_id"] == "on_hand_minus_reserved"
    by_id = {milk["component_id"]: milk for milk in body["milks"]}
    assert by_id["oat_milk"]["available"] == 0
    assert by_id["oat_milk"]["sellable"] is False
    assert by_id["almond_milk"]["sellable"] is True
    assert by_id["two_pct_milk"]["sellable"] is True


def test_first_hill_oat_latte_is_unavailable_and_does_not_reserve(client):
    before = client.get(f"/stores/{FIRST_HILL_STORE_ID}/stock/espresso_signature").json()

    response = client.post(
        "/orders",
        json={
            "store_id": FIRST_HILL_STORE_ID,
            "items": [
                {"component_id": "espresso_signature", "quantity": 1},
                {"component_id": "oat_milk", "quantity": 1},
            ],
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert body["stock_checked"] is True
    assert body["order_id"] is None
    assert "Oatmilk" in body["message"]
    assert "We did not place this order" in body["message"]
    assert body["missing"][0]["component_id"] == "oat_milk"
    assert body["missing"][0]["available"] == 0

    after = client.get(f"/stores/{FIRST_HILL_STORE_ID}/stock/espresso_signature").json()
    assert after["reserved_quantity"] == before["reserved_quantity"]


def test_first_hill_latte_with_no_milk_chosen_uses_two_percent_and_reaches_the_queue(client):
    response = client.post(
        "/orders",
        json={
            "store_id": FIRST_HILL_STORE_ID,
            "items": [{"component_id": "espresso_signature", "quantity": 1}],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["outcome"] == "barista_queue"
    assert body["stock_checked"] is True
    assert body["milk_id"] == "two_pct_milk"
    assert body["milk_defaulted"] is True
    assert body["order_id"]
    assert "barista queue" in body["message"]
    assert "2% Milk" in body["message"]
    assert "First Hill - Madison & Boylston" in body["message"]

    milk = client.get(f"/stores/{FIRST_HILL_STORE_ID}/stock/two_pct_milk").json()
    assert milk["reserved_quantity"] == 4
