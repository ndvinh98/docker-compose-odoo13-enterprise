# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HmrcSendWizard(models.TransientModel):
    _name = 'l10n_uk.hmrc.send.wizard'
    _description = "HMRC Send Wizard"

    @api.model
    def default_get(self, fields_list):
        res = super(HmrcSendWizard, self).default_get(fields_list)

        # Check obligations: should be logged in by now
        self.env['l10n_uk.vat.obligation'].import_vat_obligations()

        obligations = self.env['l10n_uk.vat.obligation'].search([('status', '=', 'open')])
        if not obligations:
            raise UserError(_('You have no open obligations anymore'))

        date_from = fields.Date.from_string(self.env.context['options']['date']['date_from'])
        date_to = fields.Date.from_string(self.env.context['options']['date']['date_to'])
        for obl in obligations:
            if obl.date_start == date_from and obl.date_end == date_to:
                res['obligation_id'] = obl.id
                break
        res['message'] = not res.get('obligation_id')
        return res

    obligation_id = fields.Many2one('l10n_uk.vat.obligation', 'Obligation', domain=[('status', '=', 'open')], required=True)
    message = fields.Boolean('Message', readonly=True) # Show message if no obligation corresponds to report options
    accept_legal = fields.Boolean('Accept Legal Statement') # A checkbox to warn the user that what he sends is legally binding
    hmrc_cash_basis = fields.Boolean('Cash Accounting Scheme', readonly=True, store=False, default=lambda self: self.env.context['options'].get('cash_basis', False))

    def send(self):
        # Check correct obligation and send it to the HMRC
        self.obligation_id.action_submit_vat_return()
