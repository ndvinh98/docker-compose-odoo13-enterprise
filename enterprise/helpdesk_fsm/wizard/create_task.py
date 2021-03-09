# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, fields, _


class CreateTask(models.TransientModel):
    _name = 'helpdesk.create.fsm.task'
    _description = 'Create a Field Service task'

    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string='Related ticket', required=True)
    company_id = fields.Many2one(related='helpdesk_ticket_id.company_id')
    name = fields.Char('Title', required=True)
    project_id = fields.Many2one('project.project', string='Project', help='Project in which to create the task', required=True, domain="[('company_id', '=', company_id), ('is_fsm', '=', True)]")
    partner_id = fields.Many2one('res.partner', string='Customer', help="Ticket's customer, will be linked to the task", required=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    def action_generate_task(self):
        self.ensure_one()
        values = self._prepare_values()
        new_task = self.env['project.task'].create(self._convert_to_write(values))
        return new_task

    def action_generate_and_view_task(self):
        self.ensure_one()
        new_task = self.action_generate_task()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks from Tickets'),
            'res_model': 'project.task',
            'res_id': new_task.id,
            'view_mode': 'form',
            'view_id': self.env.ref('industry_fsm.project_task_view_form').id,
            'context': {
                'fsm_mode': True,
            }
        }

    def _prepare_values(self, values={}):
        prepared_values = dict(values)
        for fname in ['helpdesk_ticket_id', 'name', 'project_id', 'partner_id']:
            prepared_values[fname] = self[fname]
        return prepared_values
