from odoo import api, models, _
import requests


class TaxFinancialReport(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    filter_cash_basis = False

    def _get_reports_buttons(self):
        """
            Add Buttons to Tax Report
        """
        rslt = super(TaxFinancialReport, self)._get_reports_buttons()
        if self.env.company.country_id.id == self.env.ref('base.uk').id:
            # If token, but no refresh_token, check if you got the refresh_token on the server first
            # That way, you can see immediately if your login was successful after logging in
            # and the label of the button will be correct
            if self.env.user.l10n_uk_user_token and not self.env.user.l10n_uk_hmrc_vat_token:
                self.env['hmrc.service']._login()

            if self.env.user.l10n_uk_hmrc_vat_token:
                rslt.insert(0, {'name': _('Send to HMRC'), 'action': 'send_hmrc'})
            else:
                rslt.insert(0, {'name': _('Connect to HMRC'), 'action': 'send_hmrc'})
        return rslt

    def send_hmrc(self, options):
        #login if not token
        if not self.env.user.l10n_uk_hmrc_vat_token: # If button is connect
            return self.env['hmrc.service']._login()

        # Show wizard when sending to HMRC
        context = self.env.context.copy()
        context.update({'options': options})
        view_id = self.env.ref('l10n_uk_reports.hmrc_send_wizard_form').id
        return {'type': 'ir.actions.act_window',
                'name': _('Send to HMRC'),
                'res_model': 'l10n_uk.hmrc.send.wizard',
                'target': 'new',
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'context': context,
        }