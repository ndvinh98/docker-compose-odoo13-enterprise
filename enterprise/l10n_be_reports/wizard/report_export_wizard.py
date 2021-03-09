# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class ReportExportWizard(models.TransientModel):
    _inherit = 'account_reports.export.wizard'

    l10n_be_reports_periodic_vat_wizard_id = fields.Many2one(string="Periodic VAT Export Wizard", comodel_name="l10n_be_reports.periodic.vat.xml.export")

    def export_report(self):
        self.ensure_one()
        report = self._get_report_obj()
        if report._name == 'account.generic.tax.report' and any([format.name == 'XML' for format in self.export_format_ids]) and not self.l10n_be_reports_periodic_vat_wizard_id:
            manual_action = report.print_xml(self.env.context.get('account_report_generation_options'))
            manual_wizard = self.env[manual_action['res_model']].browse(manual_action['res_id'])
            manual_wizard.calling_export_wizard_id = self
            return manual_action
        return super(ReportExportWizard, self).export_report()


class ReportExportWizardOption(models.TransientModel):
    _inherit = 'account_reports.export.wizard.format'

    def apply_export(self, report_options):
        self.ensure_one()
        report = self.export_wizard_id._get_report_obj()
        if self.name == 'XML' and report._name == 'account.generic.tax.report' and self.export_wizard_id.l10n_be_reports_periodic_vat_wizard_id:
            return self.export_wizard_id.l10n_be_reports_periodic_vat_wizard_id.print_xml()
        return super(ReportExportWizardOption, self).apply_export(report_options)
