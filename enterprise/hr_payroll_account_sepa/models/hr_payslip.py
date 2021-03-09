# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import models, fields, _
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    state = fields.Selection(selection_add=[('paid', 'Paid')])
    sepa_export_date = fields.Date(string='Generation Date', readonly=True, help="Creation date of the related export file.")
    sepa_export = fields.Binary(string='SEPA File', readonly=True, help="Export file related to this payslip")
    sepa_export_filename = fields.Char(string='File Name', help="Name of the export file generated for this payslip", store=True)

    def action_open_sepa_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name' : 'Select a bank journal!',
            'res_model': 'hr.payslip.sepa.wizard',
            'view_mode': 'form',
            'view_id' : 'hr_payslip_sepa_xml_form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def _create_xml_file(self, journal_id, file_name=None):
        employees = self.mapped('employee_id').filtered(lambda e: not e.address_home_id)
        if employees:
            raise UserError(_("Some employees (%s) don't have a private address.") % (','.join(employees.mapped('name'))))
        employees = self.mapped('employee_id').filtered(lambda e: not e.bank_account_id)
        if employees:
            raise UserError(_("Some employees (%s) don't have a bank account.") % (','.join(employees.mapped('name'))))

        # Map the necessary data
        payments_data = []
        sct_generic = (journal_id.currency_id or journal_id.company_id.currency_id).name != 'EUR'
        for slip in self:
            payments_data.append({
                'id' : slip.id,
                'name': slip.number,
                'payment_date' : slip.date_to,
                'amount' : slip.net_wage,
                'journal_id' : journal_id.id,
                'currency_id' : journal_id.currency_id.id,
                'payment_type' : 'outbound',
                'communication' : slip.number,
                'partner_id' : slip.employee_id.address_home_id.id,
                'partner_bank_id': slip.employee_id.bank_account_id.id,
            })
            if not sct_generic and (not slip.employee_id.bank_account_id.bank_bic or not slip.employee_id.bank_account_id.acc_type == 'iban'):
                sct_generic = True

        # Generate XML File
        xml_doc = journal_id.create_iso20022_credit_transfer(payments_data, True, sct_generic)
        xml_binary = base64.encodebytes(xml_doc)

        # Save XML file on the payslip
        self.write({
            'sepa_export_date': fields.Date.today(),
            'sepa_export': xml_binary,
            'sepa_export_filename': (file_name or 'SEPA_export') + '.xml',
        })

        # Change open payslips state to 'Paid'
        self.filtered(lambda slip: slip.state == 'done').write({'state': 'paid'})

        # Set payslip runs to paid state, if needed
        payslip_runs = self.mapped('payslip_run_id').filtered(
            lambda run: run.state == 'close' and all(slip.state in ['paid', 'cancel'] for slip in run.slip_ids))
        payslip_runs.write({
            'sepa_export_date': fields.Date.today(),
            'sepa_export': xml_binary,
            'sepa_export_filename': (file_name or 'SEPA_export') + '.xml',
            'state': 'paid',
        })
