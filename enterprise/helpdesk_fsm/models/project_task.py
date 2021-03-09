# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, fields, _


class Task(models.Model):
    _inherit = 'project.task'

    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', help='Ticket this task was generated from', readonly=True)

    def action_view_ticket(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'res_id': self.helpdesk_ticket_id.id,
        }