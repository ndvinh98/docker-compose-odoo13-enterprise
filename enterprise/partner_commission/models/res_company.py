# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    commission_automatic_po_frequency = fields.Selection([
        ('manually', 'Manually'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')],
        required=True,
        default='monthly')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    commission_automatic_po_frequency = fields.Selection([
        ('manually', 'Manually'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')],
        required=True,
        default='monthly')
