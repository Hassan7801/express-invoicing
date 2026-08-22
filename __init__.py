from . import models
from . import hooks


def _set_default_warehouse(env):
    env['res.company'].search([])._express_set_default_warehouse()
