"""Takes an order only after the stock book says the store can make it."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from app.milk import MilkProblem, apply_milk_rule
from app.stock import Shortage, StockBook, StockConflict


@dataclass
class OrderResult:
    outcome: str
    message: str
    stock_checked: bool
    store_id: str
    reason: str
    store_name: str | None = None
    order_id: str | None = None
    missing: list[Shortage] = field(default_factory=list)
    milk_id: str | None = None
    milk_defaulted: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        return payload


class OrderService:
    def __init__(self, stock: StockBook) -> None:
        self.stock = stock

    def place(self, store_id: str, items: list[tuple[str, int]]) -> OrderResult:
        resolved = apply_milk_rule(items)
        if isinstance(resolved, MilkProblem):
            store = self.stock.canonical_store_id(store_id)
            view = self.stock.milk_report(store_id) if store else None
            return OrderResult(
                outcome="unavailable",
                message=resolved.message,
                stock_checked=False,
                store_id=store or str(store_id).strip(),
                store_name=None if view is None else view["store_name"],
                reason="milk_choice",
            )

        decision = self.stock.check(store_id, resolved.items)
        if not decision.ok:
            return self._unavailable(decision, resolved.milk_id, resolved.milk_defaulted)

        try:
            self.stock.reserve(store_id, resolved.items)
        except StockConflict as exc:
            return self._unavailable(exc.decision, resolved.milk_id, resolved.milk_defaulted)

        milk_name = self._milk_name(decision.store_id, resolved.milk_id)
        message = f"Your order is in the barista queue at {decision.store_name}."
        if milk_name:
            message += f" The milk is {milk_name}."
        return OrderResult(
            outcome="barista_queue",
            message=message,
            stock_checked=True,
            store_id=decision.store_id,
            store_name=decision.store_name,
            order_id=str(uuid.uuid4()),
            milk_id=resolved.milk_id,
            milk_defaulted=resolved.milk_defaulted,
            reason="accepted",
        )

    def _unavailable(self, decision, milk_id: str | None, milk_defaulted: bool) -> OrderResult:
        return OrderResult(
            outcome="unavailable",
            message=decision.message,
            stock_checked=True,
            store_id=decision.store_id,
            store_name=decision.store_name,
            missing=list(decision.shortages),
            milk_id=milk_id,
            milk_defaulted=milk_defaulted,
            reason=decision.reason,
        )

    def _milk_name(self, store_id: str, milk_id: str | None) -> str | None:
        if milk_id is None:
            return None
        row = self.stock.get(store_id, milk_id)
        if row is None:
            return milk_id
        return row.component_name
