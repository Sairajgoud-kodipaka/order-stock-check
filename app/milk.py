"""Milk rule for mobile drink orders.

Rule id: on_hand_minus_reserved

A component can go on an order only when quantity_on_hand minus
reserved_quantity covers the quantity requested. Espresso and matcha
drinks use 2% Milk when the customer does not choose a milk. The order
is checked against that single milk, and the milk quantity is raised to
the number of espresso and matcha drinks on the order.
"""

from __future__ import annotations

from dataclasses import dataclass

MILK_IDS = ("oat_milk", "almond_milk", "two_pct_milk")
DEFAULT_MILK_ID = "two_pct_milk"
NEEDS_MILK = frozenset({"espresso_signature", "matcha_powder"})

MILK_RULE = {
    "id": "on_hand_minus_reserved",
    "default_milk_id": DEFAULT_MILK_ID,
    "default_milk_name": "2% Milk",
    "milk_ids": list(MILK_IDS),
    "needs_milk": sorted(NEEDS_MILK),
    "statement": (
        "Count a component as available only when quantity on hand minus "
        "quantity already reserved covers the order. Espresso and matcha "
        "drinks use 2% Milk when the customer does not choose a milk. "
        "The order is checked against that one milk, and the milk quantity "
        "covers every espresso and matcha drink on the order."
    ),
}


@dataclass(frozen=True)
class ResolvedItems:
    items: list[tuple[str, int]]
    milk_id: str | None
    milk_defaulted: bool


@dataclass(frozen=True)
class MilkProblem:
    message: str


def normalize_component_id(component_id: str) -> str:
    return component_id.strip().lower()


def merge_quantities(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    order: list[str] = []
    for component_id, quantity in items:
        key = normalize_component_id(component_id)
        if key not in totals:
            order.append(key)
        totals[key] = totals.get(key, 0) + quantity
    return [(component_id, totals[component_id]) for component_id in order]


def apply_milk_rule(items: list[tuple[str, int]]) -> ResolvedItems | MilkProblem:
    merged = merge_quantities(items)
    chosen = [component_id for component_id, _ in merged if component_id in MILK_IDS]
    if len(chosen) > 1:
        return MilkProblem(
            "Choose one milk for this drink. We did not place this order, so you will not be charged."
        )

    drink_quantity = sum(quantity for component_id, quantity in merged if component_id in NEEDS_MILK)
    if len(chosen) == 1:
        milk_id = chosen[0]
        if drink_quantity:
            merged = [
                (component_id, max(quantity, drink_quantity) if component_id == milk_id else quantity)
                for component_id, quantity in merged
            ]
        return ResolvedItems(merged, milk_id, False)

    if drink_quantity:
        merged.append((DEFAULT_MILK_ID, drink_quantity))
        return ResolvedItems(merged, DEFAULT_MILK_ID, True)

    return ResolvedItems(merged, None, False)
