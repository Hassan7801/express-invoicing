from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Serial',
        domain="[('product_id', '=', product_id)]",
        check_company=True,
        copy=False,
    )
    tracking = fields.Selection(related='product_id.tracking')

    @api.onchange('product_id')
    def _onchange_product_id_lot(self):
        if self.lot_id and self.lot_id.product_id != self.product_id:
            self.lot_id = False
