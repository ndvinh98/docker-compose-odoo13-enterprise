# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

import time

from odoo import fields

from odoo.addons.account.tests.account_test_classes import AccountingTestCase

from odoo.modules.module import get_module_resource
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class SDDTest(AccountingTestCase):

    def create_user(self):
        return self.env['res.users'].create({
            'company_id': self.env.ref("base.main_company").id,
            'name': "Ruben Rybnik",
            'login': "ruben",
            'email': "ruben.rybnik@sorcerersfortress.com",
            'groups_id': [(6, 0, [self.ref('account.group_account_invoice')])]
        })

    def create_account(self, number, partner, bank):
        return self.env['res.partner.bank'].create({
            'acc_number': number,
            'partner_id': partner.id,
            'bank_id': bank.id
        })

    def create_mandate(self,partner, partner_bank, one_off, company, current_uid, payment_journal):
        return self.env['sdd.mandate'].with_context({'uid': current_uid}).create({
            'name': 'mandate ' + (partner.name or ''),
            'original_doc': '42',
            'partner_bank_id': partner_bank.id,
            'one_off': one_off,
            'start_date': fields.Date.today(),
            'partner_id': partner.id,
            'company_id': company.id,
            'payment_journal_id': payment_journal.id
        })

    def create_invoice(self, partner, current_uid, currency):
        invoice = self.env['account.move'].with_context(default_type='out_invoice', uid=current_uid).create({
            'partner_id': partner.id,
            'currency_id': currency.id,
            'invoice_payment_ref': 'invoice to client',
            'type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.env.ref("product.product_product_4").id,
                'quantity': 1,
                'price_unit': 42,
                'name': 'something',
            })],
        })
        invoice.post()
        return invoice

    def test_sdd(self):
        # We generate the user whose the test will simulate the actions.
        user = self.create_user()

        # We setup our test company
        company = user.company_id
        company.sdd_creditor_identifier = 'BE30ZZZ300D000000042'
        company_bank_journal = self.env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'bank')], limit=1)
        company_bank_journal.bank_acc_number = 'CH9300762011623852957'
        company_bank_journal.bank_account_id.bank_id = self.env.ref('base.bank_ing')

        # Then we setup the banking data and mandates of two customers (one with a one-off mandate, the other with a recurrent one)
        partner_agrolait = self.env.ref("base.res_partner_2")
        partner_bank_agrolait = self.create_account('DE44500105175407324931', partner_agrolait, self.env.ref('base.bank_ing'))
        mandate_agrolait = self.create_mandate(partner_agrolait, partner_bank_agrolait, False, company, user.id, company_bank_journal)
        mandate_agrolait.action_validate_mandate()

        partner_china_export = self.env.ref("base.res_partner_3")
        partner_bank_china_export = self.create_account('SA0380000000608010167519', partner_china_export, self.env.ref('base.bank_bnp'))
        mandate_china_export = self.create_mandate(partner_china_export, partner_bank_china_export, True, company, user.id, company_bank_journal)
        mandate_china_export.action_validate_mandate()

        # We create one invoice for each of our test customers ...
        invoice_agrolait = self.create_invoice(partner_agrolait, user.id, company.currency_id)
        invoice_china_export = self.create_invoice(partner_china_export, user.id, company.currency_id)

        # Pay the invoices with mandates
        invoice_agrolait._sdd_pay_with_mandate(mandate_agrolait)
        invoice_china_export._sdd_pay_with_mandate(mandate_china_export)

        # These invoice should have been paid thanks to the mandate
        self.assertEqual(invoice_agrolait.invoice_payment_state, 'paid', 'This invoice should have been paid thanks to the mandate')
        self.assertEqual(invoice_agrolait.sdd_paying_mandate_id, mandate_agrolait)
        self.assertEqual(invoice_china_export.invoice_payment_state, 'paid', 'This invoice should have been paid thanks to the mandate')
        self.assertEqual(invoice_china_export.sdd_paying_mandate_id, mandate_china_export)

        #The 'one-off' mandate should now be closed
        self.assertEqual(mandate_agrolait.state, 'active', 'A recurrent mandate should stay confirmed after accepting a payment')
        self.assertEqual(mandate_china_export.state, 'closed', 'A one-off mandate should be closed after accepting a payment')

        #Let us check the conformity of XML generation :
        payment = invoice_agrolait.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')
        xml_file = etree.fromstring(payment.generate_xml(company, fields.Date.today(), True))

        schema_file_path = get_module_resource('account_sepa_direct_debit', 'schemas', 'pain.008.001.02.xsd')
        xml_schema = etree.XMLSchema(etree.parse(open(schema_file_path)))

        self.assertTrue(xml_schema.validate(xml_file), xml_schema.error_log.last_error)
