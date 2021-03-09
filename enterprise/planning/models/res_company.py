# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    planning_generation_interval = fields.Integer("Rate of shift generation", required=True, readonly=False, default=3, help="Delay for the rate at which recurring shift should be generated in month")

    planning_allow_self_unassign = fields.Boolean("Can employee un-assign themselves?", default=False,
        help="Let your employees un-assign themselves from shifts when unavailable")
