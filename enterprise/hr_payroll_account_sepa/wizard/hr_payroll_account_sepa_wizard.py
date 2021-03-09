# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayslipSepaWizard(models.TransientModel):
    _name = 'hr.payslip.sepa.wizard'
    _description = 'HR Payslip SEPA Wizard'

    journal_id = fields.Many2one(
        string='Bank Journal', comodel_name='account.journal', required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'bank')], limit=1))

    def generate_sepa_xml_file(self):
        payslip_ids = self.env['hr.payslip'].browse(self.env.context['active_ids'])
        payslip_ids._create_xml_file(self.journal_id)


class HrPayslipRunSepaWizard(models.TransientModel):
    _name = 'hr.payslip.run.sepa.wizard'
    _description = 'HR Payslip Run SEPA Wizard'

    def _get_filename(self):
        payslip_run_id = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))
        return payslip_run_id.sepa_export_filename or payslip_run_id.name

    journal_id = fields.Many2one(
        string='Bank Journal', comodel_name='account.journal', required=True,
        default=lambda self: self.env['account.journal'].search([('type', '=', 'bank')], limit=1))
    file_name = fields.Char(String='File name', required=True, default=_get_filename)

    def generate_sepa_xml_file(self):
        payslip_run_id = self.env['hr.payslip.run'].browse(self.env.context['active_id'])
        payslip_run_id.mapped('slip_ids')._create_xml_file(self.journal_id, self.file_name)
