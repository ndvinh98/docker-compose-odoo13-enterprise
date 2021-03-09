# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.tools.misc import formatLang, format_date

class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    ####################################################
    # Public
    ####################################################

    @api.model
    def get_move_lines_by_batch_payment(self, st_line_id, batch_payment_id):
        """ As get_move_lines_for_bank_statement_line, but returns lines from a batch deposit """
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)
        move_lines = self.env['account.move.line']
        # batch deposits from any journal can be selected in bank statement reconciliation widget,
        # so we need to filter not only on lines of type 'liquidity' but also on any bank/cash
        # account set as 'Allow Reconciliation'.
        move_lines = self.env['account.move.line']
        for payment in self.env['account.batch.payment'].browse(batch_payment_id).payment_ids:
            journal_accounts = [payment.journal_id.default_debit_account_id.id, payment.journal_id.default_credit_account_id.id]
            move_lines |= payment.move_line_ids.filtered(lambda r: r.account_id.id in journal_accounts)

        target_currency = st_line.currency_id or st_line.journal_id.currency_id or st_line.journal_id.company_id.currency_id
        return self._prepare_move_lines(move_lines, target_currency=target_currency, target_date=st_line.date)

    @api.model
    def get_batch_payments_data(self, bank_statement_ids):
        """ Return a list of dicts containing informations about unreconciled batch deposits """

        Batch_payment = self.env['account.batch.payment']

        batch_payments = []
        batch_payments_domain = [('state', '!=', 'reconciled')]
        for batch_payment in Batch_payment.search(batch_payments_domain, order='id asc'):
            payments = batch_payment.payment_ids
            journal = batch_payment.journal_id
            company_currency = journal.company_id.currency_id
            journal_currency = journal.currency_id or company_currency

            amount_journal_currency = formatLang(self.env, batch_payment.amount, currency_obj=journal_currency)
            amount_payment_currency = False
            # If all the payments of the deposit are in another currency than the journal currency, we'll display amount in both currencies
            if payments and all(p.currency_id != journal_currency and p.currency_id == payments[0].currency_id for p in payments):
                amount_payment_currency = sum(p.amount for p in payments)
                amount_payment_currency = formatLang(self.env, amount_payment_currency, currency_obj=payments[0].currency_id or company_currency)

            batch_payments.append({
                'id': batch_payment.id,
                'name': batch_payment.name,
                'date': format_date(self.env, batch_payment.date),
                'journal_id': journal.id,
                'amount_str': amount_journal_currency,
                'amount_currency_str': amount_payment_currency,
            })
        return batch_payments

    @api.model
    def get_bank_statement_data(self, bank_statement_line_ids, srch_domain=[]):
        """ Add batch payments data to the dict returned """
        res = super(AccountReconciliation, self).get_bank_statement_data(bank_statement_line_ids, srch_domain)
        res.update({'batch_payments': self.get_batch_payments_data(bank_statement_line_ids)})
        return res
