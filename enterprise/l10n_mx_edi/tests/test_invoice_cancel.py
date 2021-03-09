# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import time
from os import path

from odoo.addons.l10n_mx_edi.tests.common import InvoiceTransactionCase
from odoo.tools import misc


class TestL10nMxEdiCancelTest(InvoiceTransactionCase):

    def setUp(self):
        super(TestL10nMxEdiCancelTest, self).setUp()
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag

    def test_case1(self):
        """Call the method to request cancellation"""
        invoice = self.create_invoice()
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        invoice.sudo().journal_id.update_posted = True
        invoice.l10n_mx_edi_request_cancellation()
        self.assertTrue(invoice.l10n_mx_edi_pac_status in [
            'to_cancel', 'cancelled'], 'The request cancellation do not try to'
            ' cancel in the PAC')

    def test_case2(self):
        """The cron that cancel in Odoo when the PAC status is to_cancel is
        executed"""
        invoice = self.create_invoice()
        invoice.sudo().journal_id.update_posted = True
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        invoice.l10n_mx_edi_pac_status = 'to_cancel'
        cron = self.env.ref(
            'l10n_mx_edi.ir_cron_cancellation_invoices_open_to_cancel')
        cron.method_direct_trigger()
        self.assertEquals(
            invoice.state, 'cancel', 'The invoice cannot be cancelled')

    def test_case3(self):
        """The cron that cancel in Odoo when the SAT status is cancelled is
        executed"""
        invoice = self.create_invoice()
        invoice.sudo().journal_id.update_posted = True
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        invoice.l10n_mx_edi_sat_status = 'cancelled'
        cron = self.env.ref(
            'l10n_mx_edi.ir_cron_cancellation_invoices_open_to_cancel')
        cron.method_direct_trigger()
        self.assertEquals(
            invoice.state, 'cancel', 'The invoice cannot be cancelled')

    def test_case4(self):
        """The cron that return to Open the invoice is executed"""
        invoice = self.create_invoice()
        invoice.sudo().journal_id.update_posted = True
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        attachment = invoice.l10n_mx_edi_retrieve_last_attachment()
        self.company.country_id = False
        invoice.action_invoice_cancel()
        self.company.country_id = self.env.ref('base.mx').id
        xml_valid = misc.file_open(path.join(
            'l10n_mx_edi', 'tests', 'cfdi_vauxoo.xml')).read().encode('UTF-8')
        attachment.datas = base64.encodestring(xml_valid)
        cron = self.env.ref(
            'l10n_mx_edi.ir_cron_cancellation_invoices_cancel_signed_sat')
        cron.method_direct_trigger()
        self.assertEquals(
            invoice.state, 'open', 'The invoice cannot be returned to open')

    def test_case5(self):
        """The cron that return to Open the invoice is executed (When the PAC)
        status is to_cancel"""
        invoice = self.create_invoice()
        invoice.sudo().journal_id.update_posted = True
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        attachment = invoice.l10n_mx_edi_retrieve_last_attachment()
        invoice.button_cancel()
        xml_valid = misc.file_open(path.join(
            'l10n_mx_edi', 'tests', 'cfdi_vauxoo.xml')).read().encode('UTF-8')
        attachment.datas = base64.encodestring(xml_valid)
        invoice.l10n_mx_edi_pac_status = 'to_cancel'
        invoice.l10n_mx_edi_update_sat_status()
        invoice.refresh()
        self.assertEquals(
            invoice.l10n_mx_edi_sat_status, 'valid',
            'The SAT status is not valid')
        cron = self.env.ref(
            'l10n_mx_edi.ir_cron_cancellation_invoices_cancel_signed_sat')
        time.sleep(10)
        cron.method_direct_trigger()
        self.assertEquals(
            invoice.l10n_mx_edi_pac_status, 'signed',
            'The PAC status not was updated: %s' %
            invoice.message_ids.mapped('body'))
