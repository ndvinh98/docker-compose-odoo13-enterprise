# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = "hr.employee"

    def _default_employee_token(self):
        return str(uuid.uuid4())

    planning_role_id = fields.Many2one('planning.role', string="Default Planning Role", groups='hr.group_hr_user')
    employee_token = fields.Char('Security Token', default=_default_employee_token, copy=False, groups='hr.group_hr_user', readonly=True)

    _sql_constraints = [
        ('employee_token_unique', 'unique(employee_token)', 'Error: each employee token must be unique')
    ]

    def _init_column(self, column_name):
        # to avoid generating a single default employee_token when installing the module,
        # we need to set the default row by row for this column
        if column_name == "employee_token":
            _logger.debug("Table '%s': setting default value of new column %s to unique values for each row", self._table, column_name)
            self.env.cr.execute("SELECT id FROM %s WHERE employee_token IS NULL" % self._table)
            acc_ids = self.env.cr.dictfetchall()
            query_list = [{'id': acc_id['id'], 'employee_token': self._default_employee_token()} for acc_id in acc_ids]
            query = 'UPDATE ' + self._table + ' SET employee_token = %(employee_token)s WHERE id = %(id)s;'
            self.env.cr._obj.executemany(query, query_list)
        else:
            super(Employee, self)._init_column(column_name)

    def _planning_get_url(self, planning):
        result = {}
        for employee in self:
            if employee.user_id and employee.user_id.has_group('planning.group_planning_user'):
                result[employee.id] = '/web?#action=planning.planning_action_open_shift'
            else:
                result[employee.id] = '/planning/%s/%s' % (planning.access_token, employee.employee_token)
        return result
