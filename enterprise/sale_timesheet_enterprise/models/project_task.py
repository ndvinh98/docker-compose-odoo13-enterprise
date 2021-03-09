from odoo import api, fields, models, _
from datetime import datetime
from math import ceil


class Project(models.Model):
    _inherit = 'project.project'

    allow_timesheet_timer = fields.Boolean('Timesheet Timer', default=False, help="Use a timer to record timesheets on tasks")
    allow_billable = fields.Boolean("Bill from Tasks")

    _sql_constraints = [
        ('timer_only_when_timesheet', "CHECK((allow_timesheets IS NOT TRUE AND allow_timesheet_timer IS NOT TRUE) OR (allow_timesheets = 't'))", 'The timesheet timer can only be activated on project allowing timesheet.'),
    ]

    @api.onchange('allow_timesheets')
    def _onchange_allow_timesheets(self):
        if not self.allow_timesheets:
            self.allow_timesheet_timer = False

    @api.onchange('allow_billable')
    def _onchange_allow_billable(self):
        """ In order to keep task billable type as 'task_rate' using sale_timesheet usual flow.
            (see _compute_billable_type method in sale_timesheet)
        """
        if self.allow_billable:
            self.sale_order_id = False
            self.sale_line_employee_ids = False

    def write(self, values):
        result = super(Project, self).write(values)
        if 'allow_timesheet_timer' in values and not values.get('allow_timesheet_timer'):
            self.env['project.task'].with_context(ative_test=False).search([('project_id', 'in', self.ids)]).write({
                'timesheet_timer_start': False,
                'timesheet_timer_pause': False,
            })
        return result


class ProjectTask(models.Model):
    _inherit = 'project.task'

    timesheet_timer_start = fields.Datetime("Timesheet Timer Start", default=None)
    timesheet_timer_pause = fields.Datetime("Timesheet Timer Last Pause")
    timesheet_timer_first_start = fields.Datetime("Timesheet Timer First Use", readonly=True)
    timesheet_timer_last_stop = fields.Datetime("Timesheet Timer Last Use", readonly=True)
    display_timesheet_timer = fields.Boolean("Display Timesheet Time", compute='_compute_display_timesheet_timer')
    allow_billable = fields.Boolean(related="project_id.allow_billable")

    @api.depends('allow_timesheets', 'project_id.allow_timesheet_timer', 'analytic_account_active')
    def _compute_display_timesheet_timer(self):
        for task in self:
            task.display_timesheet_timer = task.allow_timesheets and task.project_id.allow_timesheet_timer and task.analytic_account_active

    # ---------------------------------------------------------
    # Timer Methods
    # ---------------------------------------------------------

    def action_timer_start(self):
        self.ensure_one()
        if not self.timesheet_timer_first_start:
            self.write({'timesheet_timer_first_start': fields.Datetime.now()})
        return self.write({'timesheet_timer_start': fields.Datetime.now()})

    def action_timer_pause(self):
        self.write({'timesheet_timer_pause': fields.Datetime.now()})

    def action_timer_resume(self):
        new_start = self.timesheet_timer_start + (fields.Datetime.now() - self.timesheet_timer_pause)
        self.write({
            'timesheet_timer_start': new_start,
            'timesheet_timer_pause': False
        })

    def action_timer_stop(self):
        self.ensure_one()
        start_time = self.timesheet_timer_start
        if start_time:  # timer was either running or paused
            pause_time = self.timesheet_timer_pause
            if pause_time:
                start_time = start_time + (fields.Datetime.now() - pause_time)
            minutes_spent = (fields.Datetime.now() - start_time).total_seconds() / 60
            minutes_spent = self._timer_rounding(minutes_spent)
            return self._action_create_timesheet(minutes_spent * 60 / 3600)
        return False

    def _timer_rounding(self, minutes_spent):
        minimum_duration = int(self.env['ir.config_parameter'].sudo().get_param('sale_timesheet_enterprise.timesheet_min_duration', 0))
        rounding = int(self.env['ir.config_parameter'].sudo().get_param('sale_timesheet_enterprise.timesheet_rounding', 0))
        minutes_spent = max(minimum_duration, minutes_spent)
        if rounding and ceil(minutes_spent % rounding) != 0:
            minutes_spent = ceil(minutes_spent / rounding) * rounding
        return minutes_spent

    # ---------------------------------------------------------
    # Business Methods
    # ---------------------------------------------------------

    def action_make_billable(self):
        return {
            "name": _("Create Sales Order"),
            "type": 'ir.actions.act_window',
            "res_model": 'project.task.create.sale.order',
            "views": [[False, "form"]],
            "target": 'new',
            "context": {
                'active_id': self.id,
                'active_model': 'project.task',
                'form_view_initial_mode': 'edit',
            },
        }

    def _action_create_timesheet(self, time_spent):
        return {
            "name": _("Confirm Time Spent"),
            "type": 'ir.actions.act_window',
            "res_model": 'project.task.create.timesheet',
            "views": [[False, "form"]],
            "target": 'new',
            "context": {
                **self.env.context,
                'active_id': self.id,
                'active_model': 'project.task',
                'default_time_spent': time_spent,
            },
        }
