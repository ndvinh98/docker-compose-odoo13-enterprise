# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Repair(models.Model):
    _inherit = 'repair.order'

    ticket_id = fields.Many2one('helpdesk.ticket', string="Ticket", help="Related Helpdesk Ticket")
