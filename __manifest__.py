{
    'name': 'Express Invoicing',
    'version': '1.0.0',
    'category': 'Accounting/Accounting',
    'author': 'Express Invoicing',
    'summary': 'Confirm a customer invoice and create the sale order and delivery',
    'depends': [
        'account',
        'sale_stock',
        'product_expiry',
        'stock_account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_views.xml',
        'data/express_invoicing_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'express_invoicing/static/src/dashboard/express_dashboard.js',
            'express_invoicing/static/src/dashboard/express_dashboard.xml',
            'express_invoicing/static/src/dashboard/express_dashboard.scss',
        ],
    },
    'post_init_hook': '_set_default_warehouse',
    'installable': True,
    'license': 'LGPL-3',
}
