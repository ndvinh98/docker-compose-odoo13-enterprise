# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import api, fields, models, _
from odoo.tools import ormcache
from odoo.exceptions import UserError


class HrSalaryRuleParameterValue(models.Model):
    _name = 'hr.rule.parameter.value'
    _description = 'Salary Rule Parameter Value'
    _order = 'date_from desc'

    rule_parameter_id = fields.Many2one('hr.rule.parameter', required=True, ondelete='cascade')
    code = fields.Char(related="rule_parameter_id.code", index=True, store=True, readonly=True)
    date_from = fields.Date(string="From", index=True, required=True)
    parameter_value = fields.Text(help="Python data structure")
    country_id = fields.Many2one(related="rule_parameter_id.country_id")

    _sql_constraints = [
        ('_unique', 'unique (rule_parameter_id, date_from)', "Two rules with the same code cannot start the same day"),
    ]


class HrSalaryRuleParameter(models.Model):
    _name = 'hr.rule.parameter'
    _description = 'Salary Rule Parameter'

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="This code is used in salary rules to refer to this parameter.")
    description = fields.Text()
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.company.country_id)
    parameter_version_ids = fields.One2many('hr.rule.parameter.value', 'rule_parameter_id', string='Versions')

    _sql_constraints = [
        ('_unique', 'unique (code)', "Two rule parameters cannot have the same code."),
    ]

    @api.model
    @ormcache('code', 'date', 'tuple(self.env.context.get("allowed_company_ids", []))')
    def _get_parameter_from_code(self, code, date=None):
        if not date:
            date = fields.Date.today()
        # This should be quite fast as it uses a limit and fields are indexed
        # moreover the method is cached
        rule_parameter = self.env['hr.rule.parameter.value'].search([
            ('code', '=', code),
            ('date_from', '<=', date)], limit=1)
        if not rule_parameter:
            raise UserError(_("No rule parameter with code '%s' was found for %s ") % (code, date))
        return ast.literal_eval(rule_parameter.parameter_value)
