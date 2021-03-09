# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from lxml import etree

from odoo import models, fields, api, _
from odoo.addons.web_grid.models.models import END_OF, STEP_BY, START_OF
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression


class AnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    def _domain_employee_id(self):
        if not self.user_has_groups('hr_timesheet.group_timesheet_manager'):
            return ['|', ('timesheet_manager_id', '=', self.env.user.id), ('user_id', '=', self.env.user.id)]
        return []

    employee_id = fields.Many2one('hr.employee', "Employee", domain=_domain_employee_id)

    # reset amount on copy
    amount = fields.Monetary(copy=False)
    validated = fields.Boolean("Validated line", group_operator="bool_and", compute='_compute_timesheet_validated', store=True, compute_sudo=True)
    is_timesheet = fields.Boolean(
        string="Timesheet Line", compute_sudo=True,
        compute='_compute_is_timesheet', search='_search_is_timesheet',
        help="Set if this analytic line represents a line of timesheet.")

    @api.depends('date', 'employee_id.timesheet_validated')
    def _compute_timesheet_validated(self):
        for line in self:
            if line.is_timesheet:
                # get most recent validation date on any of the line user's employees
                validated_to = line.sudo().employee_id.timesheet_validated
                line.validated = line.date <= validated_to if validated_to else False
            else:
                line.validated = True

    @api.depends('project_id')
    def _compute_is_timesheet(self):
        for line in self:
            line.is_timesheet = bool(line.project_id)

    def _search_is_timesheet(self, operator, value):
        if (operator, value) in [('=', True), ('!=', False)]:
            return [('project_id', '!=', False)]
        return [('project_id', '=', False)]

    def action_validate_timesheet(self):
        if self.env.context.get('grid_anchor'):
            anchor = fields.Date.from_string(self.env.context['grid_anchor'])
        else:
            anchor = date.today() + relativedelta(weeks=-1, days=1, weekday=0)
        span = self.env.context.get('grid_range', 'week')
        validate_to = anchor + END_OF[span]

        if not self:
            raise UserError(_("There aren't any timesheet to validate"))

        domain = self.env['ir.rule']._compute_domain(self._name, 'write')  # can write on the timesheet of team employee or all

        employees = self.filtered_domain(domain or []).mapped('employee_id')
        employees = employees.sudo().filtered(lambda e: not e.timesheet_validated or e.timesheet_validated < validate_to)
        if not employees:
            raise UserError(_('All selected timesheets for which you are indicated as responsible are already validated.'))
        validation = self.env['timesheet.validation'].create({
            'validation_date': validate_to,
            'validation_line_ids': [
                (0, 0, {'employee_id': employee.id}) for employee in employees
            ]
        })

        return {
            'name': _('Validate the timesheets'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'timesheet.validation',
            'res_id': validation.id,
            'views': [(False, 'form')],
        }

    @api.model
    def create(self, vals):
        # when the name is not provide by the 'Add a line' form from grid view, we set a default one
        if vals.get('project_id') and not vals.get('name'):
            vals['name'] = _('/')
        line = super(AnalyticLine, self).create(vals)
        # A line created before validation limit will be automatically validated
        if not self.user_has_groups('hr_timesheet.group_hr_timesheet_approver') and line.is_timesheet and line.validated:
            raise AccessError(_('Only a Timesheets Approver or Manager is allowed to create an entry older than the validation limit.'))
        return line

    def write(self, vals):
        res = super(AnalyticLine, self).write(vals)
        # Write then check: otherwise, the use can create the timesheet in the future, then change
        # its date.
        if not self.user_has_groups('hr_timesheet.group_hr_timesheet_approver') and self.filtered(lambda r: r.is_timesheet and r.validated):
            raise AccessError(_('Only a Timesheets Approver or Manager is allowed to modify a validated entry.'))
        return res

    def unlink(self):
        if not self.user_has_groups('hr_timesheet.group_hr_timesheet_approver') and self.filtered(lambda r: r.is_timesheet and r.validated):
            raise AccessError(_('Only a Timesheets Approver or Manager is allowed to delete a validated entry.'))
        return super(AnalyticLine, self).unlink()

    @api.model
    def _fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """ Set the correct label for `unit_amount`, depending on company UoM """
        result = super(AnalyticLine, self)._fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'grid':
            doc = etree.XML(result['arch'])
            encoding_uom = self.env.company.timesheet_encode_uom_id
            # Here, we override the string put on unit_amount field to display only the UoM name in
            # the total label on the grid view.
            # Here, we select only the unit_amount field having no string set to give priority to
            # custom inheretied view stored in database.
            for node in doc.xpath("//field[@name='unit_amount'][@widget='timesheet_uom'][not(@string)]"):
                node.set('string', encoding_uom.name)
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result

    def adjust_grid(self, row_domain, column_field, column_value, cell_field, change):
        if column_field != 'date' or cell_field != 'unit_amount':
            raise ValueError(
                "{} can only adjust unit_amount (got {}) by date (got {})".format(
                    self._name,
                    cell_field,
                    column_field,
                ))

        additionnal_domain = self._get_adjust_grid_domain(column_value)
        domain = expression.AND([row_domain, additionnal_domain])
        line = self.search(domain)

        day = column_value.split('/')[0]
        if len(line) > 1:  # copy the last line as adjustment
            line[0].copy({
                'name': _('Timesheet Adjustment'),
                column_field: day,
                cell_field: change
            })
        elif len(line) == 1:  # update existing line
            line.write({
                cell_field: line[cell_field] + change
            })
        else:  # create new one
            self.search(row_domain, limit=1).copy({
                'name': _('Timesheet Adjustment'),
                column_field: day,
                cell_field: change
            })
        return False

    def _get_adjust_grid_domain(self, column_value):
        # span is always daily and value is an iso range
        day = column_value.split('/')[0]
        return [('date', '=', day)]
