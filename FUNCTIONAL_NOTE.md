# Express invoicing — functional note

## Assumptions

The owner wants one screen. I treated a customer invoice with no sales-order link as the start of the flow, and left invoices that already come from a quotation alone.

Warehouse is company-wide. The outgoing operation type is the one already configured on that warehouse. If the warehouse is still on one-step delivery, one transfer is created and validated. Multi-step routes were not built.

Availability is free quantity in the warehouse stock location, including children. Reserved stock is not sold again. For a tracked product the check is on the chosen lot, not on the product as a whole.

Expiry is the lot's expiration date against now. A lot with no date is allowed. Lots due in the next 30 days still sell; they only appear on the board.

Service and non-storable goods still get a sales order line so the invoice has an origin. They do not create a transfer.

Prices, taxes, and discounts on the invoice are copied onto the order. The sales order is a stock and traceability document, not a commercial rewrite of the invoice.

A limited invoicing user often cannot create sales orders. The hidden order and picking are created with `sudo`. The dashboard is not.

## Questions I would have asked first

1. Is this counter sales, van sales, or office invoicing after a call? That decides whether a sales order should exist at all, and whether the customer expects a delivery note.
2. When stock is short, should we refuse the invoice, sell what we have, or take a backorder? Blocking is what was asked. It is not always what operations want at 7:30 a.m.
3. Who is allowed to ship an expired batch if the customer and a manager both sign? Food and medicine usually need an override with a name on it, not a hard wall with no door.
4. How do serials actually leave the warehouse? One scan per unit, or a list pasted from a scanner? The current field cannot hold five serials on one line.
5. After a credit note, should stock come back, stay out, or wait for a physical return? Until that is answered I would not touch reversals.

## Would I have built this?

I would have pushed back.

Odoo already has shorter paths: invoice from the order in one click, invoicing policy "ordered quantities", and in some databases a payment that confirms and delivers. For a true counter, POS is the product that was designed for "type lines, take money, stock leaves".

What I would have said: the pain is real. Four screens for a box of flour is too much for this team. The risk of teaching fifteen people to start from Invoicing is that Sales and Inventory become write-only systems. Returns, commissions, and "what did we promise" all live on the sales order. If we skip it on screen, we still have to create it, which is what this module does.

I would have offered a middle step first: a "Quick sale" on the quotation that confirms, delivers, and invoices with one button, and a simplified list view. If they still want the invoice as the only document they touch, then this design is the honest way to do it — a real delivery, not a stock scratch.

I built it because that is the brief. I would not have opened with it at a client.

## What I did not build

Credit notes. A refund for goods that physically come back should return the same lot onto a return picking, then the credit note. A refund for damaged goods that stay out should not. A refund typed as a price correction should not touch stock. I would not guess.

Five serials on one line. The stock engine wants one serial per move line. I would add a small list on the invoice line, or split the line on confirm. Until then, one serial per line.

COGS. Delivery is validated before the invoice is posted. In a perpetual setup that is the safer order: the outgoing move values first, then the invoice. If we had posted the invoice first, Anglo-Saxon COGS on the invoice can miss the real lot cost. I did not add extra accounting entries.

Blocking the invoice when stock is short. It protects the warehouse and the ministry file. It also loses a sale that a shop would have taken as "come back at two". A warning with a manager override would be more like how they already work. I kept the hard block because that was the non-negotiable.

## With three weeks

I cut credit-note returns, serial lists, two-step routes, and tests against a 500-invoice day.

At 500 invoices a day the confirm path must stop walking every quant in Python and use a single availability read per product/lot. The dashboard must not search every storable product for "qty = 0"; that list will include items they never sell. I would first time the confirm of a 40-line invoice with lots, then the board as an invoicing user with no inventory rights, then reset-to-draft-and-repost on a busy warehouse.

That is also what I would test first: lots on the picking, no double delivery, all three errors at once, and the board opening the same records a limited user is allowed to see.
