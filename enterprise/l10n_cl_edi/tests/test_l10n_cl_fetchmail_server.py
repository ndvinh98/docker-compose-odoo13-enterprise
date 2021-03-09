# -*- coding: utf-8 -*-
from unittest.mock import patch

import os

from lxml import etree

from odoo import fields
from odoo.tests import Form
from odoo.tools import misc
from .common import TestL10nClEdiCommon


class TestFetchmailServer(TestL10nClEdiCommon):
    def test_get_dte_recipient_company_incoming_supplier_document(self):
        incoming_supplier_dte = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'fetchmail_dtes', 'incoming_supplier_dte.xml')).read()
        xml_content = etree.fromstring(incoming_supplier_dte)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_supplier_document'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_sii_dte_result(self):
        incoming_sii_dte_result = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'fetchmail_dtes', 'incoming_sii_dte_result.xml')).read()
        xml_content = etree.fromstring(incoming_sii_dte_result)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_sii_dte_result'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_acknowledge(self):
        incoming_acknowledge = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'fetchmail_dtes', 'incoming_acknowledge.xml')).read()
        xml_content = etree.fromstring(incoming_acknowledge)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_acknowledge'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_commercial_accept(self):
        incoming_commercial_accept = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'fetchmail_dtes', 'incoming_commercial_accept.xml')).read()
        xml_content = etree.fromstring(incoming_commercial_accept)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_commercial_accept'),
            self.company_data['company']
        )

    def test_get_dte_recipient_company_incoming_commercial_reject(self):
        incoming_commercial_reject = misc.file_open(os.path.join(
            'l10n_cl_edi', 'tests', 'fetchmail_dtes', 'incoming_commercial_reject.xml')).read()
        xml_content = etree.fromstring(incoming_commercial_reject)
        self.assertEqual(
            self.env['fetchmail.server']._get_dte_recipient_company(xml_content, 'incoming_commercial_reject'),
            self.company_data['company']
        )

    @patch('odoo.fields.Date.context_today', return_value=fields.Date.from_string('2019-11-23'))
    def test_create_invoice_33_from_attachment(self, context_today):
        """DTE with unknown partner but known products"""
        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()
        moves = self.env['fetchmail.server']._create_invoice_from_attachment(
            att_content, att_name, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FAC 1')
        self.assertEqual(move.partner_id, self.env['res.partner'])
        self.assertEqual(move.date, fields.Date.from_string('2019-11-23'))
        self.assertEqual(move.invoice_date, fields.Date.from_string('2019-10-23'))
        self.assertEqual(move.invoice_date_due, fields.Date.from_string('2019-10-23'))
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '1')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 351391)
        self.assertEqual(move.amount_tax, 56105)

    def test_create_invoice_34_from_attachment(self):
        """Include Invoice Reference"""
        att_name = 'incoming_invoice_34.xml'
        from_address = 'incoming_dte@test.com'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()
        moves = self.env['fetchmail.server']._create_invoice_from_attachment(
            att_content, att_name, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FNA 100')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '100')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '34')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 295286)
        self.assertEqual(move.amount_tax, 0)
        self.assertEqual(len(move.l10n_cl_reference_ids), 1)
        self.assertEqual(move.l10n_cl_reference_ids.origin_doc_number, '996327')
        self.assertFalse(move.l10n_cl_reference_ids.reference_doc_code)
        self.assertEqual(move.l10n_cl_reference_ids.l10n_cl_reference_doc_type_selection, '52')
        self.assertEqual(move.l10n_cl_reference_ids.reason, 'Test')

    def test_create_invoice_33_with_holding_taxes_from_attachment(self):
        """Include Invoice Reference"""
        att_name = 'incoming_invoice_33_with_holding_taxes.xml'
        from_address = 'incoming_dte@test.com'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()
        moves = self.env['fetchmail.server']._create_invoice_from_attachment(
            att_content, att_name, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FAC 1')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '1')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(len(move.invoice_line_ids), 7)
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 231119)
        self.assertEqual(move.amount_tax, 63670)
        self.assertEqual(len(move.l10n_cl_reference_ids), 0)

    def test_create_invoice_34_unknown_product_from_attachment(self):
        att_name = 'incoming_invoice_34_unknown_product.xml'
        from_address = 'incoming_dte@test.com'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()
        moves = self.env['fetchmail.server']._create_invoice_from_attachment(
            att_content, att_name, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FNA 100')
        self.assertEqual(move.partner_id, self.partner_sii)
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '100')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.invoice_source_email, from_address)
        self.assertEqual(move.l10n_latam_document_type_id.code, '34')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(move.currency_id.name, 'CLP')
        self.assertEqual(move.amount_total, 329800)
        self.assertEqual(move.amount_tax, 0)
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.product_id, self.env['product.product'])
        self.assertEqual(move.invoice_line_ids.name, 'Unknown Product')
        self.assertEqual(move.invoice_line_ids.price_unit, 32980.0)

    @patch('odoo.addons.l10n_cl_edi.models.fetchmail_server.FetchmailServer._get_dte_lines')
    def test_create_invoice_33_from_attachment_get_lines_exception(self, get_dte_lines):
        get_dte_lines.return_value = Exception

        att_name = 'incoming_invoice_33.xml'
        from_address = 'incoming_dte@test.com'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()
        moves = self.env['fetchmail.server']._create_invoice_from_attachment(
            att_content, att_name, from_address, self.company_data['company'].id)

        self.assertEqual(len(moves), 1)

        move = moves[0]
        self.assertEqual(move.name, 'FAC 1')
        self.assertEqual(move.partner_id, self.env['res.partner'])
        self.assertEqual(move.journal_id.type, 'purchase')
        self.assertEqual(move.l10n_latam_document_number, '1')
        self.assertEqual(move.l10n_latam_document_type_id.code, '33')
        self.assertEqual(move.l10n_cl_dte_acceptation_status, 'received')
        self.assertEqual(move.company_id, self.company_data['company'])
        self.assertEqual(move.currency_id.name, 'CLP')

    def test_process_incoming_customer_claim_move_not_found(self):
        att_name = 'incoming_acknowledge.xml'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()

        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([('code', '=', '34')])
        with patch('logging.Logger.error') as logger:
            self.env['fetchmail.server']._process_incoming_customer_claim(
                self.company_data['company'].id, att_content, att_name, origin_type='incoming_acknowledge')
            logger.assert_called_with(
                'Move not found with partner: %s, name: %s, l10n_latam_document_type: %s, company_id: %s' % (
                    self.partner_sii.id, 'FNA 000254', l10n_latam_document_type.id, self.company_data['company'].id))

    def test_process_incoming_customer_claim_acknowledge(self):
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([('code', '=', '34')])
        with Form(self.env['account.move'].with_context(default_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '00254'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 79
                invoice_line_form.tax_ids.clear()

        move = invoice_form.save()
        move.l10n_cl_dte_status = 'accepted'

        att_name = 'incoming_acknowledge.xml'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, att_content, att_name, origin_type='incoming_acknowledge')

        self.assertEquals(move.l10n_cl_dte_acceptation_status, 'received')

    def test_process_incoming_customer_claim_accepted(self):
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([('code', '=', '33')])
        with Form(self.env['account.move'].with_context(default_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '0301'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type
            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 518732.7731

        move = invoice_form.save()
        move.l10n_cl_dte_status = 'accepted'

        att_name = 'incoming_commercial_accept.xml'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, att_content, att_name, origin_type='incoming_commercial_accept')

        self.assertEquals(move.l10n_cl_dte_acceptation_status, 'accepted')

    def test_process_incoming_customer_claim_rejected(self):
        l10n_latam_document_type = self.env['l10n_latam.document.type'].search([('code', '=', '34')])
        with Form(self.env['account.move'].with_context(default_type='out_invoice')) as invoice_form:
            invoice_form.partner_id = self.partner_sii
            invoice_form.l10n_latam_document_number = '254'
            invoice_form.l10n_latam_document_type_id = l10n_latam_document_type

            with invoice_form.invoice_line_ids.new() as invoice_line_form:
                invoice_line_form.product_id = self.product_a
                invoice_line_form.quantity = 1
                invoice_line_form.price_unit = 2398053.78

        move = invoice_form.save()
        move.l10n_cl_dte_status = 'accepted'

        att_name = 'incoming_commercial_reject.xml'
        att_content = misc.file_open(os.path.join('l10n_cl_edi', 'tests', 'fetchmail_dtes', att_name)).read()

        self.env['fetchmail.server']._process_incoming_customer_claim(
            self.company_data['company'].id, att_content, att_name, origin_type='incoming_commercial_reject')

        self.assertEquals(move.l10n_cl_dte_acceptation_status, 'claimed')
