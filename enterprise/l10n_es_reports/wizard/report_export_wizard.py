# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class ReportExportWizard(models.TransientModel):
    _inherit = 'account_reports.export.wizard'

    l10n_es_reports_boe_wizard_id = fields.Integer(help="Technical field storing the id of the related BOE generation wizard when exporting a Spanish report")
    l10n_es_reports_boe_wizard_model = fields.Char(help="Technical field storing the model of the related BOE generation wizard when exporting a Spanish report")

    def export_report(self):
        self.ensure_one()
        if any([format.name == 'BOE' for format in self.export_format_ids]) and not self.l10n_es_reports_boe_wizard_model:
            report = self._get_report_obj()
            boe_action = report.print_boe(self.env.context.get('account_report_generation_options'))

            # BOE generation may require the use of a wizard (hence returning act_window)
            # to prompt for some manual data. If so, we display this wizard, and
            # its validation will then set the l10n_es_reports_boe_wizard_id and l10n_es_reports_boe_wizard_model
            # fields, before recalling export_report, so that the manual values are used in the export.
            if boe_action['type'] == 'ir.actions.act_window':
                boe_wizard = self.env[boe_action['res_model']].browse(boe_action['res_id'])
                boe_wizard.calling_export_wizard_id = self
                return boe_action

        return super(ReportExportWizard, self).export_report()

    def _get_log_options_dict(self, report_options):
        log_dict = super(ReportExportWizard, self)._get_log_options_dict(report_options)

        boe_wizard_id = report_options.get('l10n_es_reports_boe_wizard_id')
        if boe_wizard_id:
            boe_wizard_data = {}
            report = self.env[self.report_model].browse(self.report_id)
            boe_wizard = report._get_boe_wizard_model().browse(boe_wizard_id)

            for field_name in boe_wizard._fields:
                if field_name == 'cash_basis_mod347_data':
                    cash_basis_data = []
                    for partner_data in boe_wizard.cash_basis_mod347_data:
                        cash_basis_data.append({
                            'partner_id': str(partner_data.partner_id),
                            'perceived_amount': partner_data.perceived_amount,
                            'currency_id': str(partner_data.currency_id),
                            'operation_key': partner_data.operation_key,
                            'operation_class': partner_data.operation_class,
                        })
                    boe_wizard_data[field_name] = cash_basis_data

                elif field_name != 'calling_export_wizard_id' and field_name[0] != '_':
                    boe_wizard_data[field_name] = str(getattr(boe_wizard, field_name))

            log_dict['l10n_es_reports_boe_wizard_id'] = boe_wizard_data
        return log_dict


class ReportExportWizardOption(models.TransientModel):
    _inherit = 'account_reports.export.wizard.format'

    def apply_export(self, report_options):
        self.ensure_one()
        if self.name == 'BOE':
            # If we need to export to BOE and the report has a BOE wizard (for manual value),
            # we call that wizard and return the resulting action.
            # The wizard itself will always have been created if needed before arriving in
            # this function by report export wizard's export_report function.
            if self.export_wizard_id.l10n_es_reports_boe_wizard_id and self.export_wizard_id.l10n_es_reports_boe_wizard_model:
                boe_wizard = self.env[self.export_wizard_id.l10n_es_reports_boe_wizard_model].browse(self.export_wizard_id.l10n_es_reports_boe_wizard_id)
                return boe_wizard.download_boe_action()
            # BOE reports without BOE export wizard behave normally

        return super(ReportExportWizardOption, self).apply_export(report_options)
