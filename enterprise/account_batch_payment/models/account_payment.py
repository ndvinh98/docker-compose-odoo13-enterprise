# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    batch_payment_id = fields.Many2one('account.batch.payment', ondelete='set null', copy=False)

    def unreconcile(self):
        for payment in self:
            if payment.batch_payment_id and payment.batch_payment_id.state == 'reconciled':
                # removing the link between a payment and a statement line means that the batch
                # payment the payment was in, is not reconciled anymore.
                payment.batch_payment_id.write({'state': 'sent'})
        return super(AccountPayment, self).unreconcile()

    def write(self, vals):
        result = super(AccountPayment, self).write(vals)
        # Mark a batch payment as reconciled if all its payments are reconciled
        for rec in self:
            if rec.batch_payment_id:
                if all(payment.state == 'reconciled' for payment in rec.batch_payment_id.payment_ids):
                    rec.batch_payment_id.state = 'reconciled'
        return result

    @api.model
    def create_batch_payment(self):
        # We use self[0] to create the batch; the constrains on the model ensure
        # the consistency of the generated data (same journal, same payment method, ...)
        if any([p.payment_type == 'transfer' for p in self]):
            raise UserError(
                _('You cannot make a batch payment with internal transfers. Internal transfers ids: %s')
                % ([p.id for p in self if p.payment_type == 'transfer'])
            )

        batch = self.env['account.batch.payment'].create({
            'journal_id': self[0].journal_id.id,
            'payment_ids': [(4, payment.id, None) for payment in self],
            'payment_method_id': self[0].payment_method_id.id,
            'batch_type': self[0].payment_type,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.batch.payment",
            "views": [[False, "form"]],
            "res_id": batch.id,
        }
