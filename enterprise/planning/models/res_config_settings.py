# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    planning_generation_interval = fields.Integer("Rate of shift generation", required=True,
        related="company_id.planning_generation_interval", readonly=False, help="Delay for the rate at which recurring shifts should be generated")

    planning_allow_self_unassign = fields.Boolean("Allow Unassignment", default=False, readonly=False,
        related="company_id.planning_allow_self_unassign", help="Let your employees un-assign themselves from shifts when unavailable")
