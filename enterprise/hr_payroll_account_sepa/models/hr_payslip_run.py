# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    state = fields.Selection(selection_add=[('paid', 'Paid')])
    sepa_export = fields.Binary(string='SEPA File', readonly=True, help="Exported SEPA .xml file")
    sepa_export_date = fields.Date(string='Generation Date', readonly=True, help="Creation date of the related export file.")
    sepa_export_filename = fields.Char(string='File Name', help="Exported SEPA .xml file name")

    def action_open_sepa_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name' : 'Select a bank journal.',
            'res_model': 'hr.payslip.run.sepa.wizard',
            'view_mode': 'form',
            'view_id' : 'hr_payslip_run_sepa_xml_form',
            'views': [(False, 'form')],
            'target': 'new',
        }
