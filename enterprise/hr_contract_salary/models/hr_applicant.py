# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    proposed_contracts = fields.Many2many('hr.contract', string="Proposed Contracts", domain="[('company_id', '=', company_id)]")
    proposed_contracts_count = fields.Integer(compute="_compute_proposed_contracts_count", string="Proposed Contracts Count")
    access_token = fields.Char('Security Token', copy=False)
    access_token_end_date = fields.Date('Access Token Validity Date', copy=False)

    def action_show_proposed_contracts(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["applicant_id", "=", self.id], '|', ["active", "=", False], ["active", "=", True]],
            "name": "Proposed Contracts",
            "context": {'default_employee_id': self.emp_id.id, 'default_applicant_id': self.id},
        }

    def _compute_proposed_contracts_count(self):
        Contracts = self.env['hr.contract'].sudo()
        for applicant in self:
            applicant.proposed_contracts_count = Contracts.with_context(active_test=False).search_count([
                ('applicant_id', '=', applicant.id)])
