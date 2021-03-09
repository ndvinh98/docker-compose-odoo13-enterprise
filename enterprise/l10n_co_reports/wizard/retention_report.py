# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class RetentionReportWizard(models.TransientModel):
    _name = 'l10n_co_reports.retention_report.wizard'
    _description = "Colombian Retention Report Wizard"

    expedition_date = fields.Date(string=u'Fecha de Expedición', default=fields.Date.context_today, required=True)
    declaration_date = fields.Date(string=u'Fecha de Declaración', default=fields.Date.context_today, required=True)
    article = fields.Char(string=u'Artículo', default='ART. 10 DECRETO 386/91', required=True)

    def generate_report(self):
        data = {
            'wizard_values': self.read()[0],
            'lines': self._context.get('lines'),
            'report_name': self._context.get('report_name'),
        }

        return self.env.ref('l10n_co_reports.action_report_certification').report_action([], data=data)
