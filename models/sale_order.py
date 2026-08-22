from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_express = fields.Boolean(copy=False)
