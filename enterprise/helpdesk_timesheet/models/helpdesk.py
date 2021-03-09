# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    project_id = fields.Many2one("project.project", string="Project", ondelete="restrict", domain="[('allow_timesheets', '=', True), ('company_id', '=', company_id)]",
        help="Project to which the tickets (and the timesheets) will be linked by default.")

    @api.model
    def create(self, vals):
        if vals.get('use_helpdesk_timesheet') and not vals.get('project_id'):
            vals['project_id'] = self.env['project.project'].create({
                'name': vals['name'],
                'type_ids': [
                    (0, 0, {'name': _('In Progress')}),
                    (0, 0, {'name': _('Closed'), 'is_closed': True})
                ]
            }).id
        return super(HelpdeskTeam, self).create(vals)

    def write(self, vals):
        if 'use_helpdesk_timesheet' in vals and not vals['use_helpdesk_timesheet']:
            vals['project_id'] = False
        result = super(HelpdeskTeam, self).write(vals)
        self.filtered(lambda team: team.use_helpdesk_timesheet and not team.project_id)._create_project()
        return result

    @api.model
    def _init_data_create_project(self):
        self.search([('use_helpdesk_timesheet', '=', True), ('project_id', '=', False)])._create_project()

    def _create_project(self):
        for team in self:
            team.project_id = self.env['project.project'].create({
                'name': team.name,
                'type_ids': [
                    (0, 0, {'name': _('In Progress')}),
                    (0, 0, {'name': _('Closed'), 'is_closed': True})
                ],
                'allow_timesheets': True,
            })
            self.env['helpdesk.ticket'].search([('team_id', '=', team.id), ('project_id', '=', False)]).write({'project_id': team.project_id.id})


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    @api.model
    def default_get(self, fields_list):
        result = super(HelpdeskTicket, self).default_get(fields_list)
        if result.get('team_id') and not result.get('project_id'):
            result['project_id'] = self.env['helpdesk.team'].browse(result['team_id']).project_id.id
        return result

    project_id = fields.Many2one("project.project", string="Project", domain="[('allow_timesheets', '=', True), ('company_id', '=', company_id)]")
    task_id = fields.Many2one("project.task", string="Task", domain="[('project_id', '=', project_id), ('company_id', '=', company_id)]", tracking=True, help="The task must have the same customer as this ticket.")
    timesheet_ids = fields.One2many('account.analytic.line', 'helpdesk_ticket_id', 'Timesheets')
    is_closed = fields.Boolean(related="task_id.stage_id.is_closed", string="Is Closed", readonly=True)
    is_task_active = fields.Boolean(related="task_id.active", string='Is Task Active', readonly=True)
    use_helpdesk_timesheet = fields.Boolean('Timesheet activated on Team', related='team_id.use_helpdesk_timesheet', readonly=True)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        # force domain on task when project is set
        if self.project_id:
            if self.project_id != self.task_id.project_id:
                # reset task when changing project
                self.task_id = False
            return {'domain': {
                'task_id': [('project_id', '=', self.project_id.id)]
            }}
        return {'domain': {
            'task_id': [('project_id.allow_timesheets', '=', True), ('company_id', '=', self.company_id.id)]
        }}

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.timesheet_ids:
            if self.task_id:
                msg = _("All timesheet hours will be assigned to the selected task on save. Discard to avoid the change.")
            else:
                msg = _("Timesheet hours will not be assigned to a customer task. Set a task to charge a customer.")
            return {'warning':
                {
                    'title': _("Warning"),
                    'message': msg
                }
            }

    @api.constrains('project_id', 'team_id')
    def _check_project_id(self):
        for ticket in self:
            if ticket.use_helpdesk_timesheet and not ticket.project_id:
                raise ValidationError(_("The project is required to track time on ticket."))

    @api.constrains('project_id', 'task_id')
    def _check_task_in_project(self):
        for ticket in self:
            if ticket.task_id:
                if ticket.task_id.project_id != ticket.project_id:
                    raise ValidationError(_("The task must be in ticket's project."))

    @api.model_create_multi
    def create(self, value_list):
        team_ids = set([value['team_id'] for value in value_list if value.get('team_id')])
        teams = self.env['helpdesk.team'].browse(team_ids)

        team_project_map = {}  # map with the team that require a project
        for team in teams:
            if team.use_helpdesk_timesheet:
                team_project_map[team.id] = team.project_id.id

        for value in value_list:
            if value.get('team_id') and not value.get('project_id') and team_project_map.get(value['team_id']):
                value['project_id'] = team_project_map[value['team_id']]

        return super(HelpdeskTicket, self).create(value_list)

    def write(self, values):
        result = super(HelpdeskTicket, self).write(values)
        # force timesheet values: changing ticket's task or project will reset timesheet ones
        timesheet_vals = {}
        for fname in self._timesheet_forced_fields():
            if fname in values:
                timesheet_vals[fname] = values[fname]
        if timesheet_vals:
            for timesheet in self.sudo().mapped('timesheet_ids'):
                timesheet.write(timesheet_vals)  # sudo since helpdesk user can change task
        return result

    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """ Set the correct label for `unit_amount`, depending on company UoM """
        result = super(HelpdeskTicket, self)._fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        result['arch'] = self.env['account.analytic.line']._apply_timesheet_label(result['arch'])
        return result

    def action_view_ticket_task(self):
        self.ensure_one()
        return {
            'view_mode': 'form',
            'res_model': 'project.task',
            'type': 'ir.actions.act_window',
            'res_id': self.task_id.id,
        }

    def _timesheet_forced_fields(self):
        """ return the list of field that should also be written on related timesheets """
        return ['task_id', 'project_id']
