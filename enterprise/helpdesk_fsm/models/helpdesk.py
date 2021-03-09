# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, api, fields, _


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_fsm = fields.Boolean('Onsite Interventions', help='Convert tickets into Field Service tasks')


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    use_fsm = fields.Boolean(related='team_id.use_fsm')
    fsm_task_ids = fields.One2many('project.task', 'helpdesk_ticket_id', string='Tasks', help='Tasks generated from this ticket', domain=[('is_fsm', '=', True)])
    fsm_task_count = fields.Integer(compute='_compute_fsm_task_count')

    @api.depends('fsm_task_ids')
    def _compute_fsm_task_count(self):
        ticket_groups = self.env['project.task'].read_group([('is_fsm', '=', True), ('helpdesk_ticket_id', '!=', False)], ['id:count_distinct'], ['helpdesk_ticket_id'])
        ticket_count_mapping = dict(map(lambda group: (group['helpdesk_ticket_id'][0], group['helpdesk_ticket_id_count']), ticket_groups))
        for ticket in self:
            ticket.fsm_task_count = ticket_count_mapping.get(ticket.id, 0)

    def action_view_fsm_tasks(self):
        fsm_form_view = self.env.ref('industry_fsm.project_task_view_form')
        fsm_list_view = self.env.ref('industry_fsm.project_task_view_list_fsm')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks from Tickets'),
            'res_model': 'project.task',
            'domain': [('id', 'in', self.fsm_task_ids.ids)],
            'views': [(fsm_list_view.id, 'tree'), (fsm_form_view.id, 'form')],
        }

    def action_generate_fsm_task(self):
        self.ensure_one()
        default_project_id = False
        fsm_projects = self.env['project.project'].search([('is_fsm', '=', True)], limit=2)
        if(len(fsm_projects) == 1):
            default_project_id = fsm_projects.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create a Field Service task'),
            'res_model': 'helpdesk.create.fsm.task',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_helpdesk_ticket_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
                'default_name': self.name,
                'default_project_id': default_project_id,
            }
        }
