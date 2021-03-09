# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields
from odoo.tools.date_utils import end_of


class HrAttachmentSalary(models.Model):
    _name = 'l10n_be.attachment.salary'
    _description = 'Garnished amount from payslip wages'

    name = fields.Char(string="Description")
    amount = fields.Float(required=True)
    garnished_type = fields.Selection([
        ('attachment_salary', 'Attachment of Salary'),
        ('assignment_salary', 'Assignment of Salary'),
        ('child_support', 'Child Support'),
    ], default='attachment_salary', required=True)
    contract_id = fields.Many2one('hr.contract')
    date_from = fields.Date(string="From", default=lambda self: fields.Date.today())
    date_to = fields.Date(string="To", default=lambda self: end_of(fields.Date.today(), 'month'))
