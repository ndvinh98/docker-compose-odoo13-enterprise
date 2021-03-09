# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ReportL10nBeHrPayroll28145(models.AbstractModel):
    _name = 'report.l10n_be_hr_payroll.report_281_45'
    _description = 'Get 281.45 report as PDF.'
    # addons.base.tests.test_reports automatically tests generic reports
    # i.e reports without explicit model.
    # This model is defined to avoid this automatic testing
    # which does not retrieve the required data to render the template

    @api.model
    def _get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': self.env['hr.employee'],
            'data': data,
            'docs': self.env['hr.employee'].browse(docids),
        }
