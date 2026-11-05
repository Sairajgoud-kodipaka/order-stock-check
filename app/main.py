"""Order service. Every accepted order has already asked stock."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from app.milk import MILK_RULE
from app.orders import OrderResult, OrderService
from app.stock import DEFAULT_SNAPSHOT, FIRST_HILL_STORE_ID, StockBook


class ItemIn(BaseModel):
    component_id: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)


class OrderIn(BaseModel):
    store_id: str = Field(min_length=1)
    items: list[ItemIn] = Field(min_length=1)


def create_app(snapshot_path: Path | None = None) -> FastAPI:
    stock = StockBook.load(snapshot_path or DEFAULT_SNAPSHOT)
    orders = OrderService(stock)
    app = FastAPI(title="Order stock check", version="1.0.0")
    app.state.stock = stock
    app.state.orders = orders

    @app.get("/")
    def root() -> dict:
        return {
            "service": "order-stock-check",
            "snapshot": stock.snapshot_name,
            "milk_rule": "/milk-rule",
            "first_hill_milk": f"/stores/{FIRST_HILL_STORE_ID}/milk",
            "place_order": "POST /orders",
        }

    @app.get("/milk-rule")
    def milk_rule() -> dict:
        return MILK_RULE

    @app.get("/stores/{store_id}/milk")
    def store_milk(store_id: str) -> dict:
        report = stock.milk_report(store_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Unknown store.")
        return report

    @app.get("/stores/{store_id}/stock/{component_id}")
    def component_stock(store_id: str, component_id: str) -> dict:
        view = stock.component_view(store_id, component_id)
        if view is None:
            raise HTTPException(status_code=404, detail="Unknown store or item.")
        return view

    @app.post("/orders")
    def place_order(body: OrderIn, response: Response) -> dict:
        result = orders.place(
            body.store_id,
            [(item.component_id, item.quantity) for item in body.items],
        )
        response.status_code = _status_code(result)
        return result.as_dict()

    return app


def _status_code(result: OrderResult) -> int:
    if result.outcome == "barista_queue":
        return 201
    if result.reason == "unknown_store":
        return 404
    return 409


app = create_app()
