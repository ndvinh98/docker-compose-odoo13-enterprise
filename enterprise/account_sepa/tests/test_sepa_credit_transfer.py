# -*- coding: utf-8 -*-

import base64
from lxml import etree

from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from odoo.modules.module import get_module_resource
from odoo.tests import tagged
from odoo.tests.common import Form


@tagged('post_install','-at_install')
class TestSEPACreditTransfer(AccountingTestCase):

    def setUp(self):
        super(TestSEPACreditTransfer, self).setUp()

        self.env.user.company_id.country_id = self.env.ref('base.be')

        # Get some records
        self.asustek_sup = self.env['res.partner'].search([('name', 'ilike', 'Wood Corner')])
        self.suppliers = self.env['res.partner'].search([('name', 'not ilike', 'Wood Corner')])
        self.sepa_ct = self.env.ref('account_sepa.account_payment_method_sepa_ct')

        # Create an IBAN bank account and its journal
        bank = self.env['res.bank'].create({'name': 'ING', 'bic': 'BBRUBEBB'})
        self.bank_journal = self.env['account.journal'].create({
            'name': 'BE48363523682327',
            'type': 'bank',
            'bank_acc_number': 'BE48363523682327',
            'bank_id': bank.id,
        })
        if self.bank_journal.company_id.currency_id != self.env.ref("base.EUR"):
            self.bank_journal.default_credit_account_id.write({'currency_id': self.env.ref("base.EUR").id})
            self.bank_journal.default_debit_account_id.write({'currency_id': self.env.ref("base.EUR").id})
            self.bank_journal.write({'currency_id': self.env.ref("base.EUR").id})

        # Make sure all suppliers have exactly one bank account
        self.setSingleBankAccountToPartner(self.asustek_sup, {
            'acc_type': 'iban',
            'partner_id': self.asustek_sup[0].id,
            'acc_number': 'BE39103123456719',
            'bank_id': self.env.ref('base.bank_bnp').id,
            'currency_id': self.env.ref('base.USD').id,
        })
        self.setSingleBankAccountToPartner(self.suppliers[0], {
            'acc_type': 'bank',
            'partner_id': self.suppliers[0].id,
            'acc_number': '123456789',
            'bank_name': 'Mock & Co',
        })

        # Create 1 payment per supplier
        self.payment_1 = self.createPayment(self.asustek_sup, 500)
        self.payment_1.post()
        self.payment_2 = self.createPayment(self.asustek_sup, 600)
        self.payment_2.post()
        self.payment_3 = self.createPayment(self.suppliers[0], 700)
        self.payment_3.post()

        # Get a pain.001.001.03 schema validator
        schema_file_path = get_module_resource('account_sepa', 'schemas', 'pain.001.001.03.xsd')
        self.xmlschema = etree.XMLSchema(etree.parse(open(schema_file_path)))

    def setSingleBankAccountToPartner(self, partner_id, bank_account_vals):
        """ Make sure a partner has exactly one bank account """
        partner_id.bank_ids.unlink()
        return self.env['res.partner.bank'].create(bank_account_vals)

    def createPayment(self, partner, amount):
        """ Create a SEPA credit transfer payment """
        return self.env['account.payment'].create({
            'journal_id': self.bank_journal.id,
            'partner_bank_account_id': partner.bank_ids[0].id,
            'payment_method_id': self.sepa_ct.id,
            'payment_type': 'outbound',
            'payment_date': '2015-04-28',
            'amount': amount,
            'currency_id': self.env.ref("base.EUR").id,
            'partner_id': partner.id,
            'partner_type': 'supplier',
        })

    def testStandardSEPA(self):
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [(4, payment.id, None) for payment in (self.payment_1 | self.payment_2)],
            'payment_method_id': self.sepa_ct.id,
            'batch_type': 'outbound',
        })

        batch.validate_batch()
        download_wizard = self.env['account.batch.download.wizard'].browse(batch.export_batch_payment()['res_id'])

        self.assertFalse(batch.sct_generic)
        sct_doc = etree.fromstring(base64.b64decode(download_wizard.export_file))
        self.assertTrue(self.xmlschema.validate(sct_doc), self.xmlschema.error_log.last_error)
        self.assertEqual(self.payment_1.state, 'sent')
        self.assertEqual(self.payment_2.state, 'sent')

    def testGenericSEPA(self):
        batch = self.env['account.batch.payment'].create({
            'journal_id': self.bank_journal.id,
            'payment_ids': [(4, payment.id, None) for payment in (self.payment_1 | self.payment_3)],
            'payment_method_id': self.sepa_ct.id,
            'batch_type': 'outbound',
        })

        batch.validate_batch()
        download_wizard = self.env['account.batch.download.wizard'].browse(batch.export_batch_payment()['res_id'])

        self.assertTrue(batch.sct_generic)
        sct_doc = etree.fromstring(base64.b64decode(download_wizard.export_file))
        self.assertTrue(self.xmlschema.validate(sct_doc), self.xmlschema.error_log.last_error)
        self.assertEqual(self.payment_1.state, 'sent')
        self.assertEqual(self.payment_3.state, 'sent')

    def testQRCode(self):
        """Test thats the QR-Code is displayed iff the mandatory fields are
        written and in the good state"""

        form = Form(self.env['account.payment'])
        form.partner_type = 'customer'
        self.assertEqual(form.display_qr_code, False)
        form.partner_type = 'supplier'
        self.assertEqual(form.display_qr_code, False)
        form.payment_method_code == 'manual'
        self.assertEqual(form.display_qr_code, False)
        form.partner_id = self.suppliers[0]
        self.assertEqual(form.display_qr_code, True)
        self.assertIn('The SEPA QR Code information is not set correctly', form.qr_code_url, 'A warning should be displayed')
        form.partner_id = self.asustek_sup
        self.assertEqual(form.display_qr_code, True)
        self.assertIn('<img ', form.qr_code_url, 'The QR code should be displayed')
        form.partner_bank_account_id = self.env['res.partner.bank']
        self.assertIn('The SEPA QR Code information is not set correctly', form.qr_code_url, 'A warning should be displayed')
        form.payment_method_id = self.sepa_ct
        self.assertEqual(form.display_qr_code, False)
