from app.orders import OrderService
from app.stock import StockBook, StockDecision


def test_closed_store_is_unavailable_even_when_the_snapshot_has_stock(client):
    before = client.get("/stores/09815/stock/oat_milk").json()
    assert before["quantity_on_hand"] == 72
    assert before["store_open"] is False

    response = client.post(
        "/orders",
        json={
            "store_id": "9815",
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
    assert "South Lake Union - Westlake & Mercer is closed" in body["message"]
    after = client.get("/stores/09815/stock/oat_milk").json()
    assert after["reserved_quantity"] == before["reserved_quantity"]


def test_capitol_hill_can_sell_one_oat_drink_and_the_next_one_is_too_late(client):
    payload = {
        "store_id": "11307",
        "items": [
            {"component_id": "espresso_signature", "quantity": 1},
            {"component_id": "oat_milk", "quantity": 1},
        ],
    }

    first = client.post("/orders", json=payload)
    second = client.post("/orders", json=payload)

    assert first.status_code == 201
    assert first.json()["outcome"] == "barista_queue"
    assert second.status_code == 409
    assert second.json()["outcome"] == "unavailable"
    assert "Oatmilk" in second.json()["message"]
    oat = client.get("/stores/11307/stock/oat_milk").json()
    assert oat["available"] == 0


def test_two_drinks_need_two_oat_milks_so_the_last_one_does_not_slip_through(client):
    before = client.get("/stores/11307/stock/oat_milk").json()
    assert before["available"] == 1

    response = client.post(
        "/orders",
        json={
            "store_id": "11307",
            "items": [
                {"component_id": "espresso_signature", "quantity": 2},
                {"component_id": "oat_milk", "quantity": 1},
            ],
        },
    )

    assert response.status_code == 409
    assert response.json()["stock_checked"] is True
    after = client.get("/stores/11307/stock/oat_milk").json()
    assert after["reserved_quantity"] == before["reserved_quantity"]


def test_an_add_in_that_is_short_blocks_the_order(client):
    response = client.post(
        "/orders",
        json={
            "store_id": "10482",
            "items": [
                {"component_id": "espresso_signature", "quantity": 1},
                {"component_id": "two_pct_milk", "quantity": 1},
                {"component_id": "vanilla_syrup", "quantity": 500},
            ],
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert "Vanilla Syrup" in body["message"]
    assert "We did not place this order" in body["message"]


def test_unknown_item_is_unavailable(client):
    response = client.post(
        "/orders",
        json={
            "store_id": "10482",
            "items": [
                {"component_id": "espresso_signature", "quantity": 1},
                {"component_id": "soy_milk", "quantity": 1},
            ],
        },
    )

    assert response.status_code == 409
    assert "soy_milk" in response.json()["message"]
    milk = client.get("/stores/10482/stock/two_pct_milk").json()
    assert milk["reserved_quantity"] == 3


def test_no_order_reaches_the_queue_when_the_stock_check_fails(monkeypatch):
    book = StockBook.load()
    service = OrderService(book)

    def fail(store_id, items):
        return StockDecision(
            ok=False,
            reason="out_of_stock",
            message="Forced stock failure. We did not place this order.",
            store_id=store_id,
            store_name="First Hill - Madison & Boylston",
            store_open=True,
        )

    def reserve_must_not_run(store_id, items):
        raise AssertionError("reserved an order the stock check rejected")

    monkeypatch.setattr(book, "check", fail)
    monkeypatch.setattr(book, "reserve", reserve_must_not_run)

    result = service.place("10482", [("espresso_signature", 1), ("oat_milk", 1)])

    assert result.outcome == "unavailable"
    assert result.stock_checked is True
    assert result.order_id is None


def test_two_milks_are_not_accepted(client):
    response = client.post(
        "/orders",
        json={
            "store_id": "10482",
            "items": [
                {"component_id": "espresso_signature", "quantity": 1},
                {"component_id": "oat_milk", "quantity": 1},
                {"component_id": "almond_milk", "quantity": 1},
            ],
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["outcome"] == "unavailable"
    assert body["reason"] == "milk_choice"
    assert body["stock_checked"] is False
    assert body["order_id"] is None
