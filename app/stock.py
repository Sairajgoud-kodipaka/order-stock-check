"""What each store has left, loaded from a stock snapshot."""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.milk import MILK_IDS, MILK_RULE, merge_quantities

DEFAULT_SNAPSHOT = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "starbucks_store_stock_snapshot_2025-03-07.csv"
)
FIRST_HILL_STORE_ID = "10482"


@dataclass
class ComponentStock:
    store_id: str
    store_name: str
    store_open: bool
    component_id: str
    component_name: str
    component_type: str
    quantity_on_hand: int
    reserved_quantity: int
    last_updated_at: str

    @property
    def available(self) -> int:
        return self.quantity_on_hand - self.reserved_quantity


@dataclass(frozen=True)
class StoreRecord:
    store_id: str
    store_name: str
    store_open: bool


@dataclass(frozen=True)
class Shortage:
    component_id: str
    component_name: str
    requested: int
    available: int
    reason: str


@dataclass(frozen=True)
class StockDecision:
    ok: bool
    reason: str
    message: str
    store_id: str
    store_name: str | None
    store_open: bool
    shortages: list[Shortage] = field(default_factory=list)


class StockConflict(Exception):
    def __init__(self, decision: StockDecision) -> None:
        self.decision = decision
        super().__init__(decision.message)


class StockBook:
    def __init__(self, rows: list[ComponentStock], snapshot_name: str) -> None:
        self.snapshot_name = snapshot_name
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], ComponentStock] = {}
        self._stores: dict[str, StoreRecord] = {}
        self._by_stripped: dict[str, str] = {}
        for row in rows:
            self._rows[(row.store_id, row.component_id)] = row
            self._stores[row.store_id] = StoreRecord(row.store_id, row.store_name, row.store_open)
            self._by_stripped[row.store_id.lstrip("0") or "0"] = row.store_id

    @classmethod
    def load(cls, path: Path | None = None) -> StockBook:
        snapshot = Path(path) if path else DEFAULT_SNAPSHOT
        rows: list[ComponentStock] = []
        with snapshot.open(newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):
                rows.append(
                    ComponentStock(
                        store_id=raw["store_id"].strip(),
                        store_name=raw["store_name"].strip(),
                        store_open=raw["store_open"].strip().lower() == "true",
                        component_id=raw["component_id"].strip().lower(),
                        component_name=raw["component_name"].strip(),
                        component_type=raw["component_type"].strip(),
                        quantity_on_hand=int(raw["quantity_on_hand"]),
                        reserved_quantity=int(raw["reserved_quantity"]),
                        last_updated_at=raw["last_updated_at"].strip(),
                    )
                )
        if not rows:
            raise ValueError(f"Snapshot {snapshot} has no stock rows.")
        return cls(rows, snapshot.name)

    def canonical_store_id(self, store_id: str) -> str | None:
        key = str(store_id).strip()
        if key in self._stores:
            return key
        return self._by_stripped.get(key.lstrip("0") or "0")

    def get(self, store_id: str, component_id: str) -> ComponentStock | None:
        canonical = self.canonical_store_id(store_id)
        if canonical is None:
            return None
        return self._rows.get((canonical, component_id.strip().lower()))

    def check(self, store_id: str, items: list[tuple[str, int]]) -> StockDecision:
        with self._lock:
            return self._evaluate(store_id, items)

    def reserve(self, store_id: str, items: list[tuple[str, int]]) -> StockDecision:
        with self._lock:
            decision = self._evaluate(store_id, items)
            if not decision.ok:
                raise StockConflict(decision)
            for component_id, quantity in merge_quantities(items):
                row = self._rows[(decision.store_id, component_id)]
                row.reserved_quantity += quantity
            return decision

    def milk_report(self, store_id: str) -> dict | None:
        canonical = self.canonical_store_id(store_id)
        if canonical is None:
            return None
        store = self._stores[canonical]
        milks = []
        for milk_id in MILK_IDS:
            row = self._rows[(canonical, milk_id)]
            milks.append(
                {
                    "component_id": milk_id,
                    "component_name": row.component_name,
                    "quantity_on_hand": row.quantity_on_hand,
                    "reserved_quantity": row.reserved_quantity,
                    "available": row.available,
                    "sellable": store.store_open and row.available > 0,
                }
            )
        return {
            "store_id": canonical,
            "store_name": store.store_name,
            "store_open": store.store_open,
            "snapshot": self.snapshot_name,
            "rule_id": MILK_RULE["id"],
            "milks": milks,
        }

    def component_view(self, store_id: str, component_id: str) -> dict | None:
        row = self.get(store_id, component_id)
        if row is None:
            return None
        return {
            "store_id": row.store_id,
            "store_name": row.store_name,
            "store_open": row.store_open,
            "component_id": row.component_id,
            "component_name": row.component_name,
            "component_type": row.component_type,
            "quantity_on_hand": row.quantity_on_hand,
            "reserved_quantity": row.reserved_quantity,
            "available": row.available,
            "last_updated_at": row.last_updated_at,
        }

    def _evaluate(self, store_id: str, items: list[tuple[str, int]]) -> StockDecision:
        canonical = self.canonical_store_id(store_id)
        if canonical is None:
            return StockDecision(
                ok=False,
                reason="unknown_store",
                message="We couldn't find that store. We did not place this order.",
                store_id=str(store_id).strip(),
                store_name=None,
                store_open=False,
            )

        store = self._stores[canonical]
        merged = merge_quantities(items)
        if not merged or any(quantity < 1 for _, quantity in merged):
            return StockDecision(
                ok=False,
                reason="invalid",
                message="Add at least one item. We did not place this order.",
                store_id=canonical,
                store_name=store.store_name,
                store_open=store.store_open,
            )
        if not store.store_open:
            return StockDecision(
                ok=False,
                reason="closed",
                message=(
                    f"{store.store_name} is closed. "
                    "We did not place this order, so you will not be charged."
                ),
                store_id=canonical,
                store_name=store.store_name,
                store_open=False,
            )

        shortages: list[Shortage] = []
        for component_id, quantity in merged:
            row = self._rows.get((canonical, component_id))
            if row is None:
                shortages.append(
                    Shortage(component_id, component_id, quantity, 0, "unknown")
                )
            elif row.available < quantity:
                shortages.append(
                    Shortage(
                        component_id,
                        row.component_name,
                        quantity,
                        row.available,
                        "insufficient",
                    )
                )
        if shortages:
            return StockDecision(
                ok=False,
                reason="out_of_stock",
                message=_unavailable_message(store.store_name, shortages),
                store_id=canonical,
                store_name=store.store_name,
                store_open=True,
                shortages=shortages,
            )
        return StockDecision(
            ok=True,
            reason="ok",
            message="",
            store_id=canonical,
            store_name=store.store_name,
            store_open=True,
        )


def _unavailable_message(store_name: str, shortages: list[Shortage]) -> str:
    if len(shortages) == 1 and shortages[0].reason == "insufficient":
        shortage = shortages[0]
        left = max(shortage.available, 0)
        return (
            f"{shortage.component_name} is unavailable at {store_name}. "
            f"{left} left after drinks already in the queue, and this order needs {shortage.requested}. "
            "We did not place this order, so you will not be charged."
        )

    parts = []
    for shortage in shortages:
        if shortage.reason == "unknown":
            parts.append(f"{shortage.component_id} is not on this store's menu")
        else:
            left = max(shortage.available, 0)
            parts.append(
                f"{shortage.component_name} ({left} left, this order needs {shortage.requested})"
            )
    return (
        f"We can't make this order at {store_name} because these are unavailable: "
        f"{'; '.join(parts)}. "
        "We did not place this order, so you will not be charged."
    )
