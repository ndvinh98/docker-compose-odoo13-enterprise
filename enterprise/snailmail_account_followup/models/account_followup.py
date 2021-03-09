# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class FollowupLine(models.Model):
    _inherit = 'account_followup.followup.line'

    send_letter = fields.Boolean('Send a Letter', help="When processing, it will send a letter by Post", default=True)
