# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AccountAccount(models.Model):
    _inherit = 'account.account'

    asset_model = fields.Many2one('account.asset', domain=lambda self: [('state', '=', 'model'), ('asset_type', '=', self.asset_type)], help="If this is selected, an asset will be created automatically when Journal Items on this account are posted.")
    create_asset = fields.Selection([('no', 'No'), ('draft', 'Create in draft'), ('validate', 'Create and validate')], required=True, default='no')
    can_create_asset = fields.Boolean(compute="_compute_can_create_asset", help="""Technical field specifying if the account can generate asset depending on it's type. It is used in the account form view.""")
    form_view_ref = fields.Char(compute='_compute_can_create_asset')
    asset_type = fields.Selection([('sale', 'Deferred Revenue'), ('expense', 'Deferred Expense'), ('purchase', 'Asset')], compute='_compute_can_create_asset')

    @api.depends('user_type_id')
    def _compute_can_create_asset(self):
        for record in self:
            if record.auto_generate_asset():
                record.asset_type = 'purchase'
            elif record.auto_generate_deferred_revenue():
                record.asset_type = 'sale'
            elif record.auto_generate_deferred_expense():
                record.asset_type = 'expense'
            else:
                record.asset_type = False

            record.can_create_asset = record.asset_type != False

            record.form_view_ref = {
                'purchase': 'account_asset.view_account_asset_form',
                'sale': 'account_asset.view_account_asset_revenue_form',
                'expense': 'account_asset.view_account_asset_expense_form',
            }.get(record.asset_type)

    def auto_generate_asset(self):
        return self.user_type_id in self.get_asset_accounts_type()

    def auto_generate_deferred_revenue(self):
        return self.user_type_id in self.get_deferred_revenue_accounts_type()

    def auto_generate_deferred_expense(self):
        return self.user_type_id in self.get_deferred_expense_accounts_type()

    def get_asset_accounts_type(self):
        return self.env.ref('account.data_account_type_fixed_assets') + self.env.ref('account.data_account_type_non_current_assets')

    def get_deferred_revenue_accounts_type(self):
        return self.env.ref('account.data_account_type_current_liabilities') + self.env.ref('account.data_account_type_non_current_liabilities')

    def get_deferred_expense_accounts_type(self):
        return self.env.ref('account.data_account_type_current_assets') + self.env.ref('account.data_account_type_prepayments')
