from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import float_compare
from odoo.tools.date_utils import start_of, end_of


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_express = fields.Boolean(copy=False)
    express_sale_id = fields.Many2one(
        'sale.order',
        string='Express Sale Order',
        copy=False,
        readonly=True,
    )
    express_picking_count = fields.Integer(compute='_compute_express_picking_count')

    @api.depends('express_sale_id', 'express_sale_id.picking_ids', 'invoice_line_ids.sale_line_ids')
    def _compute_express_picking_count(self):
        for move in self:
            move.express_picking_count = len(move._express_pickings())

    def _express_pickings(self):
        self.ensure_one()
        return (
            self.express_sale_id.picking_ids
            | self.invoice_line_ids.sale_line_ids.order_id.picking_ids
        )

    def action_view_express_pickings(self):
        self.ensure_one()
        pickings = self._express_pickings()
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_picking_tree_all')
        if len(pickings) == 1:
            action.update({
                'views': [(False, 'form')],
                'res_id': pickings.id,
                'domain': [],
            })
        else:
            action['domain'] = [('id', 'in', pickings.ids)]
        return action

    def _post(self, soft=True):
        if soft:
            future_moves = self.filtered(lambda move: move.date > fields.Date.context_today(self))
            to_process = self - future_moves
        else:
            to_process = self
        express_moves = to_process.filtered(lambda move: move._express_should_run())
        errors = []
        for move in express_moves:
            errors.extend(move._express_collect_errors())
        if errors:
            raise UserError('\n'.join(errors))
        for move in express_moves:
            move._express_run()
        return super()._post(soft=soft)

    def _express_should_run(self):
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state != 'draft':
            return False
        if self.express_sale_id:
            return False
        if self.invoice_line_ids.sale_line_ids:
            return False
        return bool(self._express_product_lines())

    def _express_product_lines(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product' and line.product_id and line.quantity
        )

    def _express_warehouse(self):
        self.ensure_one()
        warehouse = self.company_id.express_warehouse_id
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.company_id.id)],
                limit=1,
            )
        if not warehouse:
            raise UserError(_('Set a warehouse for express invoicing in Invoicing settings.'))
        return warehouse

    def _express_collect_errors(self):
        self.ensure_one()
        errors = []
        if not self.partner_id:
            errors.append(_('A customer is required before confirming the invoice.'))
        warehouse = self.company_id.express_warehouse_id or self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)],
            limit=1,
        )
        if not warehouse:
            errors.append(_('Set a warehouse for express invoicing in Invoicing settings.'))
            return errors
        location = warehouse.lot_stock_id
        demand = defaultdict(float)
        line_names = defaultdict(str)
        today = fields.Datetime.now()
        for line in self._express_product_lines():
            product = line.product_id
            if product.tracking in ('lot', 'serial') and not line.lot_id:
                errors.append(_(
                    '%(product)s: lot/serial number is missing.',
                    product=product.display_name,
                ))
            if line.lot_id and line.lot_id.product_id != product:
                errors.append(_(
                    '%(product)s: lot %(lot)s belongs to a different product.',
                    product=product.display_name,
                    lot=line.lot_id.display_name,
                ))
            if line.lot_id and line.lot_id.expiration_date and line.lot_id.expiration_date <= today:
                errors.append(_(
                    '%(product)s: lot %(lot)s expired on %(date)s.',
                    product=product.display_name,
                    lot=line.lot_id.display_name,
                    date=fields.Datetime.to_string(line.lot_id.expiration_date),
                ))
            if not product.is_storable:
                continue
            qty = line.product_uom_id._compute_quantity(line.quantity, product.uom_id) if line.product_uom_id else line.quantity
            key = (product, line.lot_id)
            demand[key] += qty
            line_names[key] = product.display_name
        Quant = self.env['stock.quant']
        for (product, lot), qty in demand.items():
            available = Quant._get_available_quantity(
                product,
                location,
                lot_id=lot,
                strict=bool(lot),
            )
            if float_compare(available, qty, precision_rounding=product.uom_id.rounding) < 0:
                lot_label = _(' (lot %s)') % lot.display_name if lot else ''
                errors.append(_(
                    '%(product)s%(lot)s: not enough stock (need %(need)s, available %(available)s).',
                    product=line_names[(product, lot)],
                    lot=lot_label,
                    need=qty,
                    available=available,
                ))
        return errors

    def _express_run(self):
        self.ensure_one()
        warehouse = self._express_warehouse()
        product_lines = self._express_product_lines()
        SaleOrder = self.env['sale.order'].sudo().with_company(self.company_id).with_context(
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_auto_subscribe_no_notify=True,
        )
        order = SaleOrder.create({
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_id.id,
            'partner_shipping_id': (self.partner_shipping_id or self.partner_id).id,
            'warehouse_id': warehouse.id,
            'company_id': self.company_id.id,
            'origin': self.name if self.name != '/' else _('Express Invoice'),
            'client_order_ref': self.ref or self.payment_reference or False,
            'is_express': True,
            'order_line': [
                Command.create({
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_uom_qty': line.quantity,
                    'product_uom_id': line.product_uom_id.id,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'tax_ids': [Command.set(line.tax_ids.ids)],
                    'sequence': line.sequence,
                })
                for line in product_lines
            ],
        })
        remaining = order.order_line.filtered(lambda line: not line.display_type)
        lot_by_sol = {}
        for invoice_line in product_lines:
            so_line = remaining.filtered(lambda line: line.product_id == invoice_line.product_id)[:1]
            if not so_line:
                continue
            invoice_line.sale_line_ids = [Command.set(so_line.ids)]
            if invoice_line.lot_id:
                lot_by_sol[so_line.id] = invoice_line.lot_id
            remaining -= so_line
        order.action_confirm()
        pickings = order.picking_ids.filtered(lambda picking: picking.state not in ('done', 'cancel'))
        for picking in pickings.sorted('id'):
            extra_moves = picking.move_ids.filtered(lambda move: not move.product_id.is_storable)
            if extra_moves:
                extra_moves._action_cancel()
                extra_moves.unlink()
            if not picking.move_ids.filtered(lambda move: move.state != 'cancel'):
                picking.action_cancel()
                continue
            self._express_validate_picking(picking, lot_by_sol)
        self.write({
            'is_express': True,
            'express_sale_id': order.id,
            'invoice_origin': order.name,
        })

    def _express_validate_picking(self, picking, lot_by_sol):
        picking = picking.sudo()
        picking.action_assign()
        MoveLine = self.env['stock.move.line'].sudo()
        for move in picking.move_ids.filtered(lambda move: move.state != 'cancel'):
            lot = lot_by_sol.get(move.sale_line_id.id)
            qty = move.product_uom_qty
            if lot:
                extra = move.move_line_ids[1:]
                if extra:
                    extra.unlink()
                if move.move_line_ids:
                    move.move_line_ids[0].write({
                        'lot_id': lot.id,
                        'quantity': qty,
                        'picked': True,
                    })
                else:
                    MoveLine.create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'quantity': qty,
                        'lot_id': lot.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'picking_id': picking.id,
                        'picked': True,
                    })
            else:
                if move.move_line_ids:
                    move.move_line_ids[0].quantity = qty
                    move.move_line_ids[0].picked = True
            move.quantity = qty
            move.picked = True
        result = picking.with_context(
            skip_backorder=True,
            skip_sms=True,
            skip_expired=True,
            cancel_backorder=True,
        ).button_validate()
        if picking.state != 'done' and isinstance(result, dict):
            raise UserError(_(
                'The delivery %(picking)s could not be validated automatically.',
                picking=picking.display_name,
            ))

    @api.model
    def get_express_dashboard_data(self, period='today'):
        date_from, date_to = self._express_period_bounds(period)
        company = self.env.company
        invoice_domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('company_id', '=', company.id),
        ]
        invoices = self.search(invoice_domain)
        express_invoices = invoices.filtered('is_express')
        normal_invoices = invoices - express_invoices
        picking_domain = [
            ('sale_id.is_express', '=', True),
            ('company_id', '=', company.id),
        ]
        pickings = self.env['stock.picking']
        if self.env['stock.picking'].has_access('read'):
            pickings = self.env['stock.picking'].search(picking_domain)
        open_pickings = pickings.filtered(lambda picking: picking.state not in ('done', 'cancel'))
        stock_value = 0.0
        out_of_stock_ids = []
        below_reorder_ids = []
        expiring_lot_ids = []
        if self.env['stock.quant'].has_access('read'):
            quants = self.env['stock.quant'].search([
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0),
                ('company_id', '=', company.id),
            ])
            stock_value = sum(
                quant.quantity * quant.product_id.standard_price
                for quant in quants
            )
        if self.env['product.product'].has_access('read'):
            out_of_stock_ids = self.env['product.product'].search([
                ('is_storable', '=', True),
                ('sale_ok', '=', True),
                ('qty_available', '<=', 0),
            ]).ids
        if self.env['stock.warehouse.orderpoint'].has_access('read'):
            orderpoints = self.env['stock.warehouse.orderpoint'].search([
                ('company_id', '=', company.id),
            ])
            below_reorder_ids = orderpoints.filtered(
                lambda orderpoint: orderpoint.qty_on_hand < orderpoint.product_min_qty
            ).ids
        if self.env['stock.lot'].has_access('read') and 'expiration_date' in self.env['stock.lot']._fields:
            now = fields.Datetime.now()
            lots = self.env['stock.lot'].search([
                ('expiration_date', '>=', now),
                ('expiration_date', '<=', now + timedelta(days=30)),
                ('product_qty', '>', 0),
            ])
            expiring_lot_ids = lots.ids
        lines = self.env['account.move.line'].search([
            ('move_id', 'in', invoices.ids),
            ('display_type', '=', 'product'),
            ('product_id', '!=', False),
        ])
        qty_by_product = defaultdict(float)
        value_by_product = defaultdict(float)
        for line in lines:
            qty_by_product[line.product_id] += line.quantity
            value_by_product[line.product_id] += line.price_subtotal
        top_qty = sorted(qty_by_product.items(), key=lambda item: item[1], reverse=True)[:5]
        top_value = sorted(value_by_product.items(), key=lambda item: item[1], reverse=True)[:5]
        return {
            'period': period,
            'date_from': fields.Date.to_string(date_from),
            'date_to': fields.Date.to_string(date_to),
            'currency_id': company.currency_id.id,
            'has_invoices': bool(invoices),
            'invoice_count': len(invoices),
            'invoice_total': sum(invoices.mapped('amount_total')),
            'express_count': len(express_invoices),
            'normal_count': len(normal_invoices),
            'delivery_count': len(pickings),
            'open_delivery_count': len(open_pickings),
            'stock_value': stock_value,
            'out_of_stock_count': len(out_of_stock_ids),
            'below_reorder_count': len(below_reorder_ids),
            'expiring_lot_count': len(expiring_lot_ids),
            'top_qty': [
                {'id': product.id, 'name': product.display_name, 'qty': qty}
                for product, qty in top_qty
            ],
            'top_value': [
                {'id': product.id, 'name': product.display_name, 'value': value}
                for product, value in top_value
            ],
            'actions': {
                'invoices': self._express_action('account.move', invoice_domain, _('Customer Invoices')),
                'express': self._express_action(
                    'account.move',
                    invoice_domain + [('is_express', '=', True)],
                    _('Express Invoices'),
                ),
                'normal': self._express_action(
                    'account.move',
                    invoice_domain + [('is_express', '=', False)],
                    _('Standard Invoices'),
                ),
                'deliveries': self._express_action('stock.picking', picking_domain, _('Express Deliveries')),
                'open_deliveries': self._express_action(
                    'stock.picking',
                    picking_domain + [('state', 'not in', ('done', 'cancel'))],
                    _('Open Express Deliveries'),
                ),
                'out_of_stock': self._express_action(
                    'product.product',
                    [('id', 'in', out_of_stock_ids)],
                    _('Out of Stock'),
                ),
                'below_reorder': self._express_action(
                    'stock.warehouse.orderpoint',
                    [('id', 'in', below_reorder_ids)],
                    _('Below Reorder Point'),
                ),
                'expiring_lots': self._express_action(
                    'stock.lot',
                    [('id', 'in', expiring_lot_ids)],
                    _('Lots Expiring Soon'),
                ),
            },
        }

    @api.model
    def _express_period_bounds(self, period):
        today = fields.Date.context_today(self)
        if period == 'week':
            return start_of(today, 'week'), end_of(today, 'week')
        if period == 'month':
            return start_of(today, 'month'), end_of(today, 'month')
        return today, today

    @api.model
    def _express_action(self, res_model, domain, name):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': res_model,
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }
