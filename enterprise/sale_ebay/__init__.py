# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import tools
from . import wizard

from odoo import api, SUPERUSER_ID

def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env['ir.config_parameter']
    # remove config parameter to ebay.site record
    icp.set_param('ebay_site', False)
    # remove config parameter to sale_ebay.ebay_sales_team
    team_id = int(icp.get_param('ebay_sales_team'))
    if team_id and team_id == env.ref('sale_ebay.ebay_sales_team', False).id:
        icp.set_param('ebay_sales_team', False)
