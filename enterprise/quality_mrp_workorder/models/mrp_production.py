# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _get_quality_point_domain(self):
        domain = super(MrpProduction, self)._get_quality_point_domain()
        domain.append(('operation_id', '=', False))
        return domain

    def _get_quality_check_values(self, quality_point):
        values = super(MrpProduction, self)._get_quality_check_values(quality_point)
        values['workorder_id'] = False
        return values
