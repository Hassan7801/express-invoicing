# Express Invoicing

Odoo **19.0 Community**.

Confirm a customer invoice and the module creates the sales order, assigns lots, validates the delivery, then posts the invoice.

## Install

1. Add `custom` to `addons_path`.
2. Install **Invoicing**, **Sales**, and **Inventory** (a chart of accounts is required).
3. Apps → Express Invoicing.

Inventory → Configuration → Settings → Express Invoicing holds the warehouse. If it is empty, the company's first warehouse is used.

## What is finished

- Confirm on a customer invoice creates a sales order and validates the outgoing transfer through `stock.picking`.
- Lot/serial on the invoice line is copied onto the stock move line.
- Service and consumable lines do not move stock.
- Invoices created from a sales order are not processed again.
- Reset to draft and confirm again does not create a second delivery.
- Stock, missing lot, and expiry are checked together and all messages are shown at once.
- Morning Board (OWL) with today / this week / this month, clickable tiles, loading and empty states, no `sudo`.

## Idempotency

The invoice stores `express_sale_id`. If that field is set, confirm only posts the invoice. The sales order and pickings already created are reused. Stock is not moved twice.

## Demo records

Created on install:

- White Flour 1kg (lot, expiry)
- Paracetamol 500mg (serial, expiry)
- Sunflower Oil 1L (storable, no tracking)
- Paper Bag (consumable)
- Same-day Drop-off (service)
- Lots `FLOUR-OK-2026`, `FLOUR-SOON-2026` (expires in 12 days), `FLOUR-EXPIRED-2024`
- Serials `PARA-SN-001`, `PARA-SN-002`
- Reorder rules that put flour and oil below minimum

Customer: **Corner Shop**.

Walkthrough:

1. Customer invoice for Corner Shop, flour 5 with `FLOUR-OK-2026`, confirm. Stock drops, delivery is done, lots are on the transfer.
2. Same product with `FLOUR-EXPIRED-2024` → blocked.
3. Flour without a lot → blocked.
4. Oil qty 40 → blocked for stock.
5. Combine the last three on one invoice → three messages.
6. Accounting → Reporting → Morning Board, change the period, click a tile.

## Known issues

- Credit notes do not reverse stock.
- One serial field per invoice line. Five serials need five lines.
- One warehouse, one-step delivery is assumed.
- After reset to draft, changing lines does not rebuild the delivery.

## Time

About five hours.
