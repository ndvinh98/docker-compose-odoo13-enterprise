# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    def send_success_mail(self, tx, invoice):
        """Override to avoid sending the success mail before the payment is
        reconciled. It will be sent by the transaction's callback_method, which
        is called after the reconciliation.
        """
        if tx.acquirer_id.provider == 'sepa_direct_debit' and tx.state != 'done':
            pass
        else:
            return super(SaleSubscription, self).send_success_mail(tx, invoice)

    def reconcile_pending_transaction(self, tx, invoice=False):
        """Override the transaction's callback_method to send the success mail
        now that the payment is reconciled.
        """
        res = super(SaleSubscription, self).reconcile_pending_transaction(tx, invoice=invoice)
        if tx.acquirer_id.provider == 'sepa_direct_debit' and tx.state == 'done':
            if not invoice:
                invoice = tx.invoice_ids and tx.invoice_ids[0]
            self.send_success_mail(tx, invoice)
        return res


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _compute_renewal_allowed(self):
        sepa_tx = self.filtered(lambda tx: tx.acquirer_id.provider == 'sepa_direct_debit')
        for tx in sepa_tx:
            tx.renewal_allowed = tx.state == 'pending'
        return super(PaymentTransaction, (self - sepa_tx))._compute_renewal_allowed()
