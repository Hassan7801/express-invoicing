from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    express_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Express Invoice Warehouse',
        check_company=True,
    )

    def _express_set_default_warehouse(self):
        for company in self:
            if company.express_warehouse_id:
                continue
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', company.id)],
                limit=1,
            )
            if warehouse:
                company.express_warehouse_id = warehouse
