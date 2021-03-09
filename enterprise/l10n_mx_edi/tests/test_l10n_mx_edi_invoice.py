# coding: utf-8

import base64
from datetime import timedelta
import os
import time

from lxml import objectify

from odoo.exceptions import ValidationError
from odoo.tools import misc
from odoo.tests.common import Form

from . import common


class TestL10nMxEdiInvoice(common.InvoiceTransactionCase):
    def setUp(self):
        super(TestL10nMxEdiInvoice, self).setUp()
        self.cert = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer'), 'rb').read()
        self.cert_key = misc.file_open(os.path.join(
            'l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key'), 'rb').read()
        self.cert_password = '12345678a'
        self.l10n_mx_edi_basic_configuration()
        self.company_partner = self.env.ref('base.main_partner')
        self.config_parameter = self.env.ref(
            'l10n_mx_edi.l10n_mx_edi_version_cfdi')
        self.xml_expected_str = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests', 'expected_cfdi33.xml')).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag
        self.payment_method_manual_out = self.env.ref(
            "account.account_payment_method_manual_out")

    def l10n_mx_edi_basic_configuration(self):
        self.company.write({
            'currency_id': self.mxn.id,
            'name': 'YourCompany',
            'l10n_mx_edi_fiscal_regime': '601',
        })
        self.company.partner_id.write({
            'vat': 'EKU9003173C9',
            'country_id': self.env.ref('base.mx').id,
            'zip': '37200',
        })
        certificate = self.env['l10n_mx_edi.certificate'].create({
            'content': base64.encodestring(self.cert),
            'key': base64.encodestring(self.cert_key),
            'password': self.cert_password,
        })
        self.account_settings.create({
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_certificate_ids': [(6, 0, [certificate.id])],
        }).execute()
        self.set_currency_rates(mxn_rate=21, usd_rate=1)

    def test_l10n_mx_edi_invoice_basic(self):
        # -----------------------
        # Testing sign process
        # -----------------------
        invoice = self.create_invoice()
        invoice.sudo().journal_id.l10n_mx_address_issued_id = self.company_partner.id
        invoice.move_name = 'INV/2017/999'
        invoice.post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))

        # -------------------------------------------------------
        # Testing deletion of attachments (XML & PDF) once signed
        # -------------------------------------------------------
        xml_attachment = self.env['ir.attachment'].search([
            ('res_id', '=', invoice.id),
            ('res_model', '=', 'account.move'),
            ('name', '=', invoice.l10n_mx_edi_cfdi_name)])
        error_msg = 'You cannot delete a set of documents which has a legal'
        with self.assertRaisesRegexp(ValidationError, error_msg):
            xml_attachment.unlink()
        # Creates a dummy PDF to attach it and then try to delete it
        pdf_filename = '%s.pdf' % os.path.splitext(xml_attachment.name)[0]
        pdf_attachment = self.env['ir.attachment'].with_context({}).create({
            'name': pdf_filename,
            'res_id': invoice.id,
            'res_model': 'account.move',
            'datas': base64.encodestring(b'%PDF-1.3'),
        })
        pdf_attachment.unlink()

        # ----------------
        # Testing discount
        # ----------------
        invoice_disc = invoice.copy()
        for line in invoice_disc.invoice_line_ids:
            line.discount = 10
            line.price_unit = 500
        invoice_disc.compute_taxes()
        invoice_disc.post()
        self.assertEqual(invoice_disc.state, "posted")
        self.assertEqual(invoice_disc.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = invoice_disc.l10n_mx_edi_get_xml_etree()
        xml_expected_disc = objectify.fromstring(self.xml_expected_str)
        version = xml.get('version', xml.get('Version', ''))
        xml_expected_disc.attrib['SubTotal'] = '500.00'
        xml_expected_disc.attrib['Descuento'] = '50.00'
        # 500 - 10% + taxes(16%, -10%)
        xml_expected_disc.attrib['Total'] = '477.00'
        self.xml_merge_dynamic_items(xml, xml_expected_disc)
        xml_expected_disc.attrib['Folio'] = xml.attrib['Folio']
        xml_expected_disc.attrib['Serie'] = xml.attrib['Serie']
        for concepto in xml_expected_disc.Conceptos:
            concepto.Concepto.attrib['ValorUnitario'] = '500.00'
            concepto.Concepto.attrib['Importe'] = '500.00'
            concepto.Concepto.attrib['Descuento'] = '50.00'
        self.assertEqualXML(xml, xml_expected_disc)

        # -----------------------
        # Testing re-sign process (recovery a previous signed xml)
        # -----------------------
        invoice.l10n_mx_edi_pac_status = "retry"
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "retry")
        invoice.l10n_mx_edi_update_pac_status()
        for _x in range(10):
            if invoice.l10n_mx_edi_pac_status == 'signed':
                break
            time.sleep(2)
            invoice.l10n_mx_edi_retrieve_last_attachment().unlink()
            invoice.l10n_mx_edi_update_pac_status()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml_attachs = invoice.l10n_mx_edi_retrieve_attachments()
        self.assertEqual(len(xml_attachs), 2)
        xml_1 = objectify.fromstring(base64.decodestring(xml_attachs[0].datas))
        xml_2 = objectify.fromstring(base64.decodestring(xml_attachs[1].datas))
        if hasattr(xml_2, 'Addenda'):
            xml_2.remove(xml_2.Addenda)
        self.assertEqualXML(xml_1, xml_2)

        # -----------------------
        # Testing cancel PAC process
        # -----------------------
        invoice.with_context(called_from_cron=True).action_invoice_cancel()
        self.assertEqual(invoice.state, "cancel")
        self.assertTrue(
            invoice.l10n_mx_edi_pac_status in ['cancelled', 'to_cancel'],
            invoice.message_ids.mapped('body'))
        invoice.l10n_mx_edi_pac_status = "signed"

        # -----------------------
        # Testing cancel SAT process
        # -----------------------
        invoice.l10n_mx_edi_update_sat_status()
        self.assertNotEqual(invoice.l10n_mx_edi_sat_status, "cancelled")

    def test_multi_currency(self):
        invoice = self.create_invoice()
        usd_rate = 20.0

        # -----------------------
        # Testing company.mxn.rate=1 and invoice.usd.rate=1/value
        # -----------------------
        self.set_currency_rates(mxn_rate=1, usd_rate=1/usd_rate)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(float(values['rate']), usd_rate)

        # -----------------------
        # Testing company.mxn.rate=value and invoice.usd.rate=1
        # -----------------------
        self.set_currency_rates(mxn_rate=usd_rate, usd_rate=1)
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertEqual(float(values['rate']), usd_rate)

        # -----------------------
        # Testing using MXN currency for invoice and company
        # -----------------------
        invoice.currency_id = self.mxn.id
        values = invoice._l10n_mx_edi_create_cfdi_values()
        self.assertFalse(values['rate'])

    def test_addenda(self):
        invoice = self.create_invoice()
        addenda_autozone = self.ref('l10n_mx_edi.l10n_mx_edi_addenda_autozone')
        invoice.sudo().partner_id.l10n_mx_edi_addenda = addenda_autozone
        invoice.sudo().invoice_user_id.partner_id.ref = '8765'
        invoice.message_ids.unlink()
        invoice.post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml_str = base64.decodestring(invoice.message_ids[-2].attachment_ids.datas)
        xml = objectify.fromstring(xml_str)
        xml_expected = objectify.fromstring(
            '<ADDENDA10 xmlns:cfdi="http://www.sat.gob.mx/cfd/3" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="https://azfes.autozone.com/xsd/Addenda_Merch_32.xsd" '
            'VERSION="1.0" BUYER="%s" VENDOR_ID="8765" '
            'EMAIL="%s"/>' % (invoice.partner_id.name,
                              invoice.company_id.partner_id.email))
        xml_addenda = xml.Addenda.xpath('//ADDENDA10')[0]
        self.assertEqualXML(xml_addenda, xml_expected)

    def test_l10n_mx_edi_invoice_basic_33(self):
        self.xml_expected_str = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests', 'expected_cfdi33.xml')).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)
        self.test_l10n_mx_edi_invoice_basic()

        # -----------------------
        # Testing invoice refund to verify CFDI related section
        # -----------------------
        invoice = self.create_invoice()
        invoice.post()
        refund = self.env['account.move.reversal'].with_context(
            active_ids=invoice.ids).create({
                'refund_method': 'refund',
                'reason': 'Refund Test',
                'date': invoice.invoice_date,
            })
        result = refund.reverse_moves()
        refund_id = result.get('domain')[1][2]
        refund = self.invoice_model.browse(refund_id)
        refund.refresh()
        refund.post()
        xml = refund.l10n_mx_edi_get_xml_etree()
        self.assertEquals(xml.CfdiRelacionados.CfdiRelacionado.get('UUID'),
                          invoice.l10n_mx_edi_cfdi_uuid,
                          'Invoice UUID is different to CFDI related')

        # -----------------------
        # Testing invoice without product to verify no traceback
        # -----------------------
        invoice = self.create_invoice()
        invoice.invoice_line_ids[0].product_id = False
        invoice.compute_taxes()
        invoice.post()
        self.assertEqual(invoice.state, "posted")

        # -----------------------
        # Testing case with include base amount
        # -----------------------
        invoice = self.create_invoice()
        tax_ieps = self.tax_positive.copy({
            'name': 'IEPS 9%',
            'amount': 9.0,
            'include_base_amount': True,
        })
        self.tax_positive.sequence = 3
        for line in invoice.invoice_line_ids:
            line.invoice_line_tax_id = [self.tax_positive.id, tax_ieps.id]
        invoice.compute_taxes()
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml_total = invoice.l10n_mx_edi_get_xml_etree().get('Total')
        self.assertEqual(invoice.amount_total, float(xml_total),
                         'The amount with include base amount is incorrect')

        # -----------------------
        # Testing send payment by email
        # -----------------------
        invoice = self.create_invoice()
        invoice.post()
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank')], limit=1)
        payment_register = Form(self.env['account.payment'].with_context(active_model='account.move', active_ids=invoice.ids))
        payment_register.payment_date = invoice.date
        payment_register.l10n_mx_edi_payment_method_id = self.env.ref(
                'l10n_mx_edi.payment_method_efectivo')
        payment_register.payment_method_id = self.env.ref(
                "account.account_payment_method_manual_in")
        payment_register.journal_id = bank_journal
        payment_register.communication = invoice.name
        payment_register.amount = invoice.amount_total
        payment = payment_register.save()
        payment.post()
        self.assertEqual(payment.l10n_mx_edi_pac_status, "signed",
                         payment.message_ids.mapped('body'))
        default_template = self.env.ref(
            'account.mail_template_data_payment_receipt')
        wizard_mail = self.env['mail.compose.message'].with_context({
            'default_template_id': default_template.id,
            'default_model': 'account.payment',
            'default_res_id': payment.id}).create({})
        res = wizard_mail.onchange_template_id(
            default_template.id, wizard_mail.composition_mode,
            'account_payment', payment.id)
        wizard_mail.write({'attachment_ids': res.get('value', {}).get(
            'attachment_ids', [])})
        wizard_mail.send_mail()
        attachment = payment.l10n_mx_edi_retrieve_attachments()
        self.assertEqual(len(attachment), 2,
                         'Documents not attached correctly')

    def test_l10n_mx_edi_payment(self):
        journal = self.env['account.journal'].search(
            [('type', '=', 'bank')], limit=1)
        self.company.l10n_mx_edi_fiscal_regime = '601'
        invoice = self.create_invoice()
        invoice.move_name = 'INV/2017/999'
        today = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped("body"))
        payment_register = Form(self.env['account.payment'].with_context(active_model='account.move', active_ids=invoice.ids))
        payment_register.payment_date = today.date() - timedelta(days=5)
        payment_register.l10n_mx_edi_payment_method_id = self.payment_method_cash
        payment_register.payment_method_id = self.payment_method_manual_out
        payment_register.journal_id = journal
        payment_register.communication = invoice.name
        payment_register.amount = invoice.amount_total
        payment_register.save().post()

        payment = invoice._get_reconciled_payments()
        self.assertEqual(
            payment.l10n_mx_edi_pac_status, 'signed',
            payment.message_ids.mapped('body'))

    def test_l10n_mx_edi_invoice_custom(self):
        """Test Invoice for information custom  with three cases:
        - Information custom wrong for sat
        - Information custom correct for sat
        - Invoice with more the one information custom correct"""

        invoice = self.create_invoice()
        invoice.move_name = 'INV/2017/997'
        customs_num = '15  48  30  001234'
        invoice.invoice_line_ids.l10n_mx_edi_customs_number = customs_num
        msg = ("Error in the products:.*%s.* The format of the customs "
               "number is incorrect.*For example: 15  48  3009  0001234") % (
                   invoice.invoice_line_ids.product_id.name)
        with self.assertRaisesRegexp(ValidationError, msg):
            invoice.post()

        node_expected = '''
        <cfdi:InformacionAduanera xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        NumeroPedimento="15  48  3009  0001234"/>
        '''
        invoice = self.create_invoice()
        invoice.move_name = 'INV/2017/998'
        customs_number = '15  48  3009  0001234'
        invoice.invoice_line_ids.l10n_mx_edi_customs_number = customs_number
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = invoice.l10n_mx_edi_get_xml_etree()
        xml_expected = objectify.fromstring(node_expected)
        self.assertEqualXML(xml.Conceptos.Concepto.InformacionAduanera,
                            xml_expected)

        node_expected_2 = '''
        <cfdi:InformacionAduanera xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        NumeroPedimento="15  48  3009  0001235"/>
        '''
        invoice = self.create_invoice()
        invoice.move_name = 'INV/2017/999'
        customs_number = '15  48  3009  0001234,15  48  3009  0001235'
        invoice.invoice_line_ids.l10n_mx_edi_customs_number = customs_number
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = invoice.l10n_mx_edi_get_xml_etree()
        xml_expected = objectify.fromstring(node_expected)
        xml_expected_2 = objectify.fromstring(node_expected_2)
        self.assertEqualXML(xml.Conceptos.Concepto.InformacionAduanera[0],
                            xml_expected)
        self.assertEqualXML(xml.Conceptos.Concepto.InformacionAduanera[1],
                            xml_expected_2)
