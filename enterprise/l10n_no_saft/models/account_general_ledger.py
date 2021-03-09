# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, _


class AccountGeneralLedger(models.AbstractModel):
    _inherit = 'account.general.ledger'

    def _get_reports_buttons(self):
        buttons = super()._get_reports_buttons()
        if self.env.company.country_id.code == 'NO':
            buttons.append({'name': _('Export SAF-T (Norway)'), 'sequence': 5, 'action': 'print_xml', 'file_export_type': _('XML')})
        return buttons

    def _prepare_header_data(self, options):
        res = super()._prepare_header_data(options)
        if self.env.company.country_id.code == 'NO':
            res.update({
                'file_version': '1.10',
                'accounting_basis': 'A',
           })
        return res

    def _prepare_saft_report_data(self, options):
        res = super()._prepare_saft_report_data(options)
        if res['country_code'] == 'NO':
            res['xmlns'] = 'urn:StandardAuditFile-Taxation-Financial:NO'
        return res

    def _get_xsd_file(self):
        if self.env.company.country_id.code == 'NO':
            return 'Norwegian_SAF-T_Financial_Schema_v_1.10.xsd'
        return super()._get_xsd_file()
