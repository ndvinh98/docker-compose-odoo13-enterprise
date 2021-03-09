# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    check_ids = fields.One2many('quality.check', 'production_id', string="Checks")

    def button_plan(self):
        res = super(MrpProduction, self).button_plan()
        for order in self:
            if not order.workorder_ids.mapped('check_ids'):
                order.workorder_ids._create_checks()
        return res
