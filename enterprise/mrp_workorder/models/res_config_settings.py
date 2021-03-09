# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_mrp_wo_tablet_timer = fields.Boolean("Timer", implied_group="mrp_workorder.group_mrp_wo_tablet_timer")
