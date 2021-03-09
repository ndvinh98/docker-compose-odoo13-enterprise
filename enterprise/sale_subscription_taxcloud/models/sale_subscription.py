# -*- coding: utf-8 -*-

from odoo import api, models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    def _do_payment(self, payment_token, invoice, two_steps_sec=True):
        if invoice.fiscal_position_id.is_taxcloud and invoice.type in ["out_invoice", "out_refund"]:
            # force computation of the taxes so the payment amount is correct, otherwise it
            # would only be done at invoice confirmation, *after* the payment.
            # Note: do not capture the payment yet (`taxcloud_authorize_transaction` context flag),
            # as it may still fail below - that will be done when the invoice is posted.
            invoice.validate_taxes_on_invoice()
        return super(SaleSubscription, self)._do_payment(payment_token, invoice, two_steps_sec=two_steps_sec)
