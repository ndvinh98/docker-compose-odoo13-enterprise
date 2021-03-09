# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

PAY_LINES_PER_PAGE = 20


class PrintBatchPayment(models.AbstractModel):
    _name = 'report.account_batch_payment.print_batch_payment'
    _template = 'account_batch_payment.print_batch_payment'
    _description = 'Batch Deposit Report'

    def get_pages(self, batch):
        """ Returns the data structure used by the template
        """
        i = 0
        payment_slices = []
        while i < len(batch.payment_ids):
            payment_slices.append(batch.payment_ids[i:i+PAY_LINES_PER_PAGE])
            i += PAY_LINES_PER_PAGE

        return [{
            'date': batch.date,
            'batch_name': batch.name,
            'journal_name': batch.journal_id.name,
            'payments': payments,
            'currency': batch.currency_id,
            'total_amount': batch.amount if idx == len(payment_slices) - 1 else 0,
            'footer': batch.journal_id.company_id.report_footer,
        } for idx, payments in enumerate(payment_slices)]

    @api.model
    def _get_report_values(self, docids, data=None):
        report_name = 'account_batch_payment.print_batch_payment'
        report = self.env['ir.actions.report']._get_report_from_name(report_name)
        return {
            'doc_ids': docids,
            'doc_model': report.model,
            'docs': self.env[report.model].browse(docids),
            'pages': self.get_pages,
        }
