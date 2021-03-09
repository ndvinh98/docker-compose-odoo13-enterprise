# -*- coding: utf-8 -*-

from odoo import models, api, _

class account_payment(models.Model):
    _inherit = "account.payment"

    def do_print_checks(self):
        if self:
            check_layout = self[0].company_id.account_check_printing_layout
            # A config parameter is used to give the ability to use this check format even in other countries than US, as not all the localizations have one
            if check_layout != 'disabled' and (self[0].journal_id.company_id.country_id.code == 'US' or bool(self.env['ir.config_parameter'].sudo().get_param('account_check_printing_force_us_format'))):
                self.write({'state': 'sent'})
                return self.env.ref('l10n_us_check_printing.%s' % check_layout).report_action(self)
        return super(account_payment, self).do_print_checks()
