# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_industry_fsm_report = fields.Boolean("Worksheet Templates")
    group_industry_fsm_quotations = fields.Boolean(string="Extra Quotations", implied_group="industry_fsm.group_fsm_quotation_from_task")
