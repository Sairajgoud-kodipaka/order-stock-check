# Order stock check

Mobile orders ask what the store has left before they are accepted. The customer sees one of two outcomes: the barista queue, or a message that names what is unavailable. An order is never placed until that check has run.

The stock book is the snapshot `data/starbucks_store_stock_snapshot_2025-03-07.csv`.

## Milk rule

Rule id: `on_hand_minus_reserved`

Available quantity is `quantity_on_hand - reserved_quantity`. Espresso and matcha drinks use **2% Milk** when the customer does not choose a milk. The order is checked against that one milk, and the milk quantity covers every espresso and matcha drink on the order. Add-ins use the same available-quantity check.

## First Hill, 7 March 2025

Store `10482`, First Hill - Madison & Boylston, is open.

| Milk | On hand | Reserved | Available | Sellable |
| --- | ---: | ---: | ---: | --- |
| Oatmilk | 0 | 0 | 0 | no |
| Almondmilk | 38 | 1 | 37 | yes |
| 2% Milk | 96 | 3 | 93 | yes |

An oat latte here is unavailable, and nothing is reserved. A latte with no milk chosen uses 2% Milk and goes to the barista queue. An order that names two milks is refused, because there is no single milk to check.

## Run

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python -m uvicorn app.main:app --reload
```

`GET /stores/10482/milk` is the First Hill milk check. `POST /orders` places an order.

```bash
curl http://127.0.0.1:8000/stores/10482/milk

curl -X POST http://127.0.0.1:8000/orders ^
  -H "Content-Type: application/json" ^
  -d "{\"store_id\":\"10482\",\"items\":[{\"component_id\":\"espresso_signature\",\"quantity\":1},{\"component_id\":\"oat_milk\",\"quantity\":1}]}"
```
