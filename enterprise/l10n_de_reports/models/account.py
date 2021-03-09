# -*- coding: utf-8 -*-

from odoo import api, models

class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _prepare_liquidity_account(self, name, company, currency_id, type):
        res = super(AccountJournal, self)._prepare_liquidity_account(name, company, currency_id, type)

        if company.country_id.code == 'DE':
            tag_ids = res.get('tag_ids', [])
            tag_ids.append((4, self.env.ref('l10n_de.tag_de_asset_bs_B_IV').id))
            res['tag_ids'] = tag_ids

        return res

class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    def _load(self, sale_tax_rate, purchase_tax_rate, company):
        if company.country_id.code == 'DE':
            self = self.with_context(no_create_move=True)
        return super(AccountChartTemplate, self)._load(sale_tax_rate, purchase_tax_rate, company)
