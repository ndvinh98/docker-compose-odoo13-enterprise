# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def action_dashboard_redirect(self):
        if self.env.user.has_group('sales_team.group_sale_salesman'):
            return self.env.ref('website_sale_dashboard.sale_dashboard').read()[0]
        return super(Website, self).action_dashboard_redirect()


