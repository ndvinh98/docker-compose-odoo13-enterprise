# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import fields

from odoo.addons.account_invoice_extract.models.account_invoice import SUCCESS, NOT_READY, ERROR_INTERNAL, WARNING_DUPLICATE_VENDOR_REFERENCE
from odoo.addons.account_invoice_extract.tests import common as account_invoice_extract_common
from odoo.tests import tagged
from odoo.tests.common import Form, TransactionCase


@tagged('post_install', '-at_install')
class TestInvoiceExtract(TransactionCase, account_invoice_extract_common.MockIAP):
    def init_invoice(self, default_type="in_invoice", extract_state='waiting_extraction'):
        move_form = Form(self.env['account.move'].with_context(default_type=default_type))
        move_form.extract_state = extract_state
        return move_form.save()

    def get_default_extract_response(self):
        return {
            'results': [{
                'supplier': {'selected_value': {'content': "Test"}, 'words': []},
                'total': {'selected_value': {'content': 330}, 'words': []},
                'subtotal': {'selected_value': {'content': 300}, 'words': []},
                'invoice_id': {'selected_value': {'content': 'INV0001'}, 'words': []},
                'currency': {'selected_value': {'content': 'EUR'}, 'words': []},
                'VAT_Number': {'selected_value': {'content': 'BE0477472701'}, 'words': []},
                'date': {'selected_value': {'content': '2019-04-12 00:00:00'}, 'words': []},
                'due_date': {'selected_value': {'content': '2019-04-19 00:00:00'}, 'words': []},
                'global_taxes_amount': {'selected_value': {'content': 30.0}, 'words': []},
                'global_taxes': [{'selected_value': {'content': 15.0, 'amount_type': 'percent'}, 'words': []}],
                'email': {'selected_value': {'content': 'test@email.com'}, 'words': []},
                'website': {'selected_value': {'content': 'www.test.com'}, 'words': []},
                'payment_ref': {'selected_value': {'content': '+++123/1234/12345+++'}, 'words': []},
                'iban': {'selected_value': {'content': 'BE01234567890123'}, 'words': []},
                'invoice_lines': [
                    {
                        'description': {'selected_value': {'content': 'Test 1'}},
                        'unit_price': {'selected_value': {'content': 100}},
                        'quantity': {'selected_value': {'content': 1}},
                        'taxes': {'selected_values': [{'content': 15, 'amount_type': 'percent'}]},
                        'subtotal': {'selected_value': {'content': 100}},
                        'total': {'selected_value': {'content': 115}},
                    },
                    {
                        'description': {'selected_value': {'content': 'Test 2'}},
                        'unit_price': {'selected_value': {'content': 50}},
                        'quantity': {'selected_value': {'content': 2}},
                        'taxes': {'selected_values': [{'content': 0, 'amount_type': 'percent'}]},
                        'subtotal': {'selected_value': {'content': 100}},
                        'total': {'selected_value': {'content': 100}},
                    },
                    {
                        'description': {'selected_value': {'content': 'Test 3'}},
                        'unit_price': {'selected_value': {'content': 20}},
                        'quantity': {'selected_value': {'content': 5}},
                        'taxes': {'selected_values': [{'content': 15, 'amount_type': 'percent'}]},
                        'subtotal': {'selected_value': {'content': 100}},
                        'total': {'selected_value': {'content': 115}},
                    },
                ],
            }],
            'status_code': SUCCESS,
        }

    def test_no_merge_check_status(self):
        # test check_status without lines merging
        invoice = self.init_invoice()
        self.env.company.extract_single_line_per_tax = False
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(invoice.extract_state, 'waiting_validation')
        self.assertEqual(invoice.extract_status_code, SUCCESS)
        self.assertEqual(invoice.amount_total, 330)
        self.assertEqual(invoice.amount_untaxed, 300)
        self.assertEqual(invoice.amount_tax, 30)
        self.assertEqual(invoice.ref, 'INV0001')
        self.assertEqual(invoice.invoice_date, fields.Date.from_string('2019-04-12'))
        self.assertEqual(invoice.invoice_date_due, fields.Date.from_string('2019-04-19'))
        self.assertEqual(invoice.invoice_payment_ref, "+++123/1234/12345+++")

        self.assertEqual(len(invoice.invoice_line_ids), 3)
        for i, invoice_line in enumerate(invoice.invoice_line_ids):
            self.assertEqual(invoice_line.name, extract_response['results'][0]['invoice_lines'][i]['description']['selected_value']['content'])
            self.assertEqual(invoice_line.price_unit, extract_response['results'][0]['invoice_lines'][i]['unit_price']['selected_value']['content'])
            self.assertEqual(invoice_line.quantity, extract_response['results'][0]['invoice_lines'][i]['quantity']['selected_value']['content'])
            tax = extract_response['results'][0]['invoice_lines'][i]['taxes']['selected_values'][0]
            if tax['content'] == 0:
                self.assertEqual(len(invoice_line.tax_ids), 0)
            elif tax['content'] == 21:
                self.assertEqual(len(invoice_line.tax_ids), 1)
                self.assertEqual(invoice_line.tax_ids[0].amount, 15)
                self.assertEqual(invoice_line.tax_ids[0].amount_type, 'percent')
            self.assertEqual(invoice_line.price_subtotal, extract_response['results'][0]['invoice_lines'][i]['subtotal']['selected_value']['content'])
            self.assertEqual(invoice_line.price_total, extract_response['results'][0]['invoice_lines'][i]['total']['selected_value']['content'])

    def test_merge_check_status(self):
        # test check_status with lines merging
        invoice = self.init_invoice()
        self.env.company.extract_single_line_per_tax = True
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(len(invoice.invoice_line_ids), 2)

        # line 1 and 3 should be merged as they both have a 21% tax
        self.assertEqual(invoice.invoice_line_ids[0].name, "Test 1\nTest 3")
        self.assertEqual(invoice.invoice_line_ids[0].price_unit, 200)
        self.assertEqual(invoice.invoice_line_ids[0].quantity, 1)
        self.assertEqual(len(invoice.invoice_line_ids[0].tax_ids), 1)
        self.assertEqual(invoice.invoice_line_ids[0].tax_ids[0].amount, 15)
        self.assertEqual(invoice.invoice_line_ids[0].tax_ids[0].amount_type, 'percent')
        self.assertEqual(invoice.invoice_line_ids[0].price_subtotal, 200)
        self.assertEqual(invoice.invoice_line_ids[0].price_total, 230)

        # line 2 has no tax
        self.assertEqual(invoice.invoice_line_ids[1].name, "Test 2")
        self.assertEqual(invoice.invoice_line_ids[1].price_unit, 100)
        self.assertEqual(invoice.invoice_line_ids[1].quantity, 1)
        self.assertEqual(len(invoice.invoice_line_ids[1].tax_ids), 0)
        self.assertEqual(invoice.invoice_line_ids[1].price_subtotal, 100)
        self.assertEqual(invoice.invoice_line_ids[1].price_total, 100)

    def test_partner_creation_from_vat(self):
        # test that the partner isn't created if the VAT number isn't valid
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertFalse(invoice.partner_id)

        # test that the partner is created if the VAT number is valid
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {'company_data': {'name': 'Partner', 'country_code': 'BE', 'vat': 'BE0477472701',
            'partner_gid': False, 'city': 'Namur', 'bank_ids': [], 'zip': '2110', 'street': 'OCR street'}}):
            invoice._check_status()

        self.assertEqual(invoice.partner_id.name, 'Partner')
        self.assertEqual(invoice.partner_id.vat, 'BE0477472701')

    def test_partner_selection_from_vat(self):
        # test that if a partner with the VAT found already exists in database it is selected
        invoice = self.init_invoice()
        existing_partner = self.env['res.partner'].create({'name': 'Existing partner', 'vat': 'BE0477472701'})
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {'name': 'A new partner', 'vat': 'BE0123456789'}):
            invoice._check_status()

        self.assertEqual(invoice.partner_id, existing_partner)

    def test_partner_selection_from_name(self):
        # test that if a partner with a similar name already exists in database it is selected
        invoice = self.init_invoice()
        existing_partner = self.env['res.partner'].create({'name': 'Test S.A.'})
        self.env['res.partner'].create({'name': 'Partner'})
        self.env['res.partner'].create({'name': 'Another supplier'})
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {'name': 'A new partner', 'vat': 'BE0123456789'}):
            invoice._check_status()

        self.assertEqual(invoice.partner_id, existing_partner)

        # test that if no partner with a similar name exists, the partner isn't set
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()
        extract_response['results'][0]['supplier']['selected_value']['content'] = 'Blablablablabla'

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertFalse(invoice.partner_id)

    def test_multi_currency(self):
        # test that if the multi currency isn't disabled, the currency isn't changed
        invoice = self.init_invoice()
        test_user = self.env['res.users'].create({
            'login': "test_user",
            'name': "Test User",
        })
        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')])
        eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')])
        invoice.currency_id = usd_currency.id
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice.with_user(test_user)._check_status()

        self.assertEqual(invoice.currency_id, usd_currency)

        # test that if multi currency is enabled, the currency is changed
        group_multi_currency = self.env.ref('base.group_multi_currency')
        test_user.write({
            'groups_id': [(4, group_multi_currency.id)],
        })

        # test with the name of the currency
        invoice = self.init_invoice()
        invoice.currency_id = usd_currency.id
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice.with_user(test_user)._check_status()

        self.assertEqual(invoice.currency_id, eur_currency)

        # test with the symbol of the currency
        invoice = self.init_invoice()
        invoice.currency_id = usd_currency.id
        extract_response = self.get_default_extract_response()
        extract_response['results'][0]['currency']['selected_value']['content'] = '€'

        with self.mock_iap_extract(extract_response, {}):
            invoice.with_user(test_user)._check_status()

        self.assertEqual(invoice.currency_id, eur_currency)

    def test_tax_adjustments(self):
        # test that if the total computed by Odoo doesn't exactly match the total found by the OCR, the tax are adjusted accordingly
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()
        extract_response['results'][0]['total']['selected_value']['content'] += 0.01

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(invoice.amount_tax, 30.01)
        self.assertEqual(invoice.amount_untaxed, 300)
        self.assertEqual(invoice.amount_total, 330.01)

    def test_non_existing_tax(self):
        # test that if there is an invoice line with a tax which doesn't exist in database it is ignored
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()
        extract_response['results'][0]['total']['selected_value']['content'] = 123.4
        extract_response['results'][0]['subtotal']['selected_value']['content'] = 100
        extract_response['results'][0]['invoice_lines'] = [
            {
                'description': {'selected_value': {'content': 'Test 1'}},
                'unit_price': {'selected_value': {'content': 100}},
                'quantity': {'selected_value': {'content': 1}},
                'taxes': {'selected_values': [{'content': 12.34, 'amount_type': 'percent'}]},
                'subtotal': {'selected_value': {'content': 100}},
                'total': {'selected_value': {'content': 123.4}},
            },
        ]

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.invoice_line_ids[0].name, "Test 1")
        self.assertEqual(invoice.invoice_line_ids[0].price_unit, 100)
        self.assertEqual(invoice.invoice_line_ids[0].quantity, 1)
        self.assertEqual(len(invoice.invoice_line_ids[0].tax_ids), 0)
        self.assertEqual(invoice.invoice_line_ids[0].price_subtotal, 100)
        self.assertEqual(invoice.invoice_line_ids[0].price_total, 100)

    def test_duplicated_reference(self):
        # test that if an invoice with the same invoice reference already exists, the invoice is still created and the user is warned
        invoice = self.init_invoice(extract_state='no_extract_requested')
        invoice.ref = "INV0001"
        invoice.invoice_date = fields.Date.from_string('2019-04-12')
        partner = self.env['res.partner'].create({'name': 'Test', 'vat': 'BE0000000000'})
        invoice.partner_id = partner

        invoice2 = self.init_invoice()
        invoice2.partner_id = partner
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice2._check_status()

        self.assertFalse(invoice2.ref)
        self.assertEqual(invoice2.extract_status_code, WARNING_DUPLICATE_VENDOR_REFERENCE)

    def test_server_error(self):
        # test that the extract state is set to 'error' if the OCR returned an error
        invoice = self.init_invoice()
        extract_response = {'status_code': ERROR_INTERNAL}

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(invoice.extract_state, 'error_status')
        self.assertEqual(invoice.extract_status_code, ERROR_INTERNAL)

    def test_server_not_ready(self):
        # test that the extract state is set to 'not_ready' if the OCR didn't finish to process the invoice
        invoice = self.init_invoice()
        extract_response = {'status_code': NOT_READY}

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(invoice.extract_state, 'extract_not_ready')
        self.assertEqual(invoice.extract_status_code, NOT_READY)

    def test_posted_invoice_not_edited(self):
        # test that we don't edit an invoice that has already been posted
        invoice = self.init_invoice()
        invoice.state = 'posted'
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(len(invoice.invoice_line_ids), 0)

    def test_preupdate_other_waiting_invoices(self):
        # test that when we update an invoice, other invoices waiting for extraction are updated as well
        invoice = self.init_invoice()
        invoice2 = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice.check_status()

        self.assertEqual(invoice.extract_state, 'waiting_validation')
        self.assertEqual(invoice2.extract_state, 'waiting_validation')

    def test_no_overwrite_client_values(self):
        # test that we are not overwriting the values entered by the client
        invoice = self.init_invoice()
        partner = self.env['res.partner'].create({'name': 'Blabla', 'vat': 'BE0123456789'})
        self.env['res.partner'].create({'name': 'Test', 'vat': 'BE0000000000'})     # this match the partner found in the server response
        with Form(invoice) as move_form:
            move_form.invoice_date = fields.Date.from_string('2019-04-01')
            move_form.invoice_date_due = fields.Date.from_string('2019-05-01')
            move_form.ref = 'INV1234'
            move_form.partner_id = partner
            with move_form.invoice_line_ids.new() as line:
                line.name = "Blabla"
                line.price_unit = 13
                line.quantity = 2
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice.check_status()

        self.assertEqual(invoice.extract_state, 'waiting_validation')
        self.assertEqual(invoice.ref, 'INV1234')
        self.assertEqual(invoice.invoice_date, fields.Date.from_string('2019-04-01'))
        self.assertEqual(invoice.invoice_date_due, fields.Date.from_string('2019-05-01'))
        self.assertEqual(invoice.partner_id, partner)

        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.invoice_line_ids[0].name, "Blabla")
        self.assertEqual(invoice.invoice_line_ids[0].price_unit, 13)
        self.assertEqual(invoice.invoice_line_ids[0].quantity, 2)

    def test_invoice_validation(self):
        # test that when we post the invoice, the validation is sent to the server
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {'company_data': {'name': 'Partner', 'country_code': 'BE', 'vat': 'BE0477472701',
            'partner_gid': False, 'city': 'Namur', 'bank_ids': [], 'zip': '2110', 'street': 'OCR street'}}):
            invoice._check_status()

        with self.mock_iap_extract({'status_code': SUCCESS}, {}):
            invoice.post()

        self.assertEqual(invoice.extract_state, 'done')
        self.assertEqual(invoice.get_validation('total')['content'], invoice.amount_total)
        self.assertEqual(invoice.get_validation('subtotal')['content'], invoice.amount_untaxed)
        self.assertEqual(invoice.get_validation('global_taxes_amount')['content'], invoice.amount_tax)
        validation_global_taxes = invoice.get_validation('global_taxes')['content']
        for i, line in enumerate(invoice.line_ids.filtered('tax_repartition_line_id')):
            self.assertDictEqual(validation_global_taxes[i], {
                'amount': line.debit,
                'tax_amount': line.tax_line_id.amount,
                'tax_amount_type': line.tax_line_id.amount_type,
                'tax_price_include': line.tax_line_id.price_include,
            })
        self.assertEqual(invoice.get_validation('date')['content'], str(invoice.invoice_date))
        self.assertEqual(invoice.get_validation('due_date')['content'], str(invoice.invoice_date_due))
        self.assertEqual(invoice.get_validation('invoice_id')['content'], invoice.ref)
        self.assertEqual(invoice.get_validation('supplier')['content'], invoice.partner_id.name)
        self.assertEqual(invoice.get_validation('VAT_Number')['content'], invoice.partner_id.vat)
        self.assertEqual(invoice.get_validation('currency')['content'], invoice.currency_id.name)
        self.assertEqual(invoice.get_validation('payment_ref')['content'], invoice.invoice_payment_ref)
        validation_invoice_lines = invoice.get_validation('invoice_lines')['lines']
        for i, il in enumerate(invoice.invoice_line_ids):
            self.assertDictEqual(validation_invoice_lines[i], {
                'description': il.name,
                'quantity': il.quantity,
                'unit_price': il.price_unit,
                'product': il.product_id.id,
                'taxes_amount': round(il.price_total - il.price_subtotal, 2),
                'taxes': [{
                    'amount': tax.amount,
                    'type': tax.amount_type,
                    'price_include': tax.price_include} for tax in il.tax_ids],
                'subtotal': il.price_subtotal,
                'total': il.price_total,
            })

    def test_automatic_sending(self):
        # test that the invoice is automatically sent to the OCR server when the option is enabled

        # test with message_post()
        self.env.company.extract_show_ocr_option_selection = 'auto_send'
        invoice = self.init_invoice(extract_state='no_extract_requested')
        test_attachment = self.env['ir.attachment'].create({
            'name': "an attachment",
            'datas': base64.b64encode(b'My attachment'),
        })

        with self.mock_iap_extract({'status_code': SUCCESS, 'document_id': 1}, {}):
            invoice.message_post(attachment_ids=[test_attachment.id])

        self.assertEqual(invoice.extract_state, 'waiting_extraction')

        # test with register_as_main_attachment()
        invoice = self.init_invoice(extract_state='no_extract_requested')
        test_attachment = self.env['ir.attachment'].create({
            'name': "an attachment",
            'datas': base64.b64encode(b'My attachment'),
            'res_model': 'account.move',
            'res_id': invoice.id,
        })

        with self.mock_iap_extract({'status_code': SUCCESS, 'document_id': 1}, {}):
            test_attachment.register_as_main_attachment()

        self.assertEqual(invoice.extract_state, 'waiting_extraction')

        # test that the invoice is not automatically sent to the OCR server when the option is disabled

        # test with message_post()
        self.env.company.extract_show_ocr_option_selection = 'manual_send'
        invoice = self.init_invoice(extract_state='no_extract_requested')
        test_attachment = self.env['ir.attachment'].create({
            'name': "an attachment",
            'datas': base64.b64encode(b'My attachment'),
        })

        with self.mock_iap_extract({'status_code': SUCCESS, 'document_id': 1}, {}):
            invoice.message_post(attachment_ids=[test_attachment.id])

        self.assertEqual(invoice.extract_state, 'no_extract_requested')

        # test with register_as_main_attachment()
        invoice = self.init_invoice(extract_state='no_extract_requested')
        test_attachment = self.env['ir.attachment'].create({
            'name': "another attachment",
            'datas': base64.b64encode(b'My other attachment'),
            'res_model': 'account.move',
            'res_id': invoice.id,
        })

        with self.mock_iap_extract({'status_code': SUCCESS, 'document_id': 1}, {}):
            test_attachment.register_as_main_attachment()

        self.assertEqual(invoice.extract_state, 'no_extract_requested')

    def test_bank_account(self):
        # test that the bank account is set when an iban is found

        # test that an account is created if no existing matches the account number
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {'company_data': {'name': 'Partner', 'country_code': 'BE', 'vat': 'BE0477472701', 'partner_gid': False, 'city': 'Namur', 'bank_ids': [], 'zip': '2110', 'street': 'OCR street'}}):
            invoice._check_status()

        self.assertEqual(invoice.invoice_partner_bank_id.acc_number, 'BE01234567890123')

        # test that it uses the existing bank account if it exists
        created_bank_account = invoice.invoice_partner_bank_id
        invoice = self.init_invoice()
        extract_response = self.get_default_extract_response()

        with self.mock_iap_extract(extract_response, {}):
            invoice._check_status()

        self.assertEqual(invoice.invoice_partner_bank_id, created_bank_account)
