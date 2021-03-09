# coding: utf-8
import os
import re
from unittest.mock import patch, Mock

from odoo.addons.account.tests.account_test_classes import AccountingTestCase
from odoo.tests import tagged
from odoo.tools import misc, mute_logger


@tagged('post_install', '-at_install')
class InvoiceTransactionCase(AccountingTestCase):
    def setUp(self):
        super(InvoiceTransactionCase, self).setUp()

        self.partner = self.env.ref('base.res_partner_12')
        self.partner.country_id = self.env.ref('base.co')

        self.company = self.env.ref('base.main_company')
        self.company.country_id = self.env.ref('base.co')

        self.salesperson = self.env.ref('base.user_admin')
        self.salesperson.function = 'Sales'

        report_text = 'GRANDES CONTRIBUYENTES SHD Res. DDI-042065 13-10-17'
        self.company.l10n_co_edi_header_gran_contribuyente = report_text
        self.company.l10n_co_edi_header_tipo_de_regimen = report_text
        self.company.l10n_co_edi_header_retenedores_de_iva = report_text
        self.company.l10n_co_edi_header_autorretenedores = report_text
        self.company.l10n_co_edi_header_resolucion_aplicable = report_text
        self.company.l10n_co_edi_header_actividad_economica = report_text
        self.company.l10n_co_edi_header_bank_information = report_text

        self.company.vat = '0123456789'
        self.company.partner_id.l10n_co_document_type = 'rut'
        self.company.partner_id.l10n_co_edi_representation_type_id = self.env.ref('l10n_co_edi.representation_type_0')
        self.company.partner_id.l10n_co_edi_establishment_type_id = self.env.ref('l10n_co_edi.establishment_type_0')
        self.company.partner_id.l10n_co_edi_obligation_type_ids = self.env.ref('l10n_co_edi.obligation_type_0')
        self.company.partner_id.l10n_co_edi_customs_type_ids = self.env.ref('l10n_co_edi.customs_type_0')
        self.company.partner_id.l10n_co_edi_large_taxpayer = True

        self.partner.vat = '9876543210'
        self.partner.l10n_co_document_type = 'rut'
        self.partner.l10n_co_edi_representation_type_id = self.env.ref('l10n_co_edi.representation_type_0')
        self.partner.l10n_co_edi_establishment_type_id = self.env.ref('l10n_co_edi.establishment_type_0')
        self.partner.l10n_co_edi_obligation_type_ids = self.env.ref('l10n_co_edi.obligation_type_0')
        self.partner.l10n_co_edi_customs_type_ids = self.env.ref('l10n_co_edi.customs_type_0')
        self.partner.l10n_co_edi_large_taxpayer = True

        self.tax = self.env['account.tax'].search([('type_tax_use', '=', 'sale')], limit=1)
        self.tax.amount = 15
        self.tax.l10n_co_edi_type = self.env.ref('l10n_co_edi.tax_type_0')
        self.retention_tax = self.tax.copy({
            'l10n_co_edi_type': self.env.ref('l10n_co_edi.tax_type_9').id
        })

        self.account_receivable = self.env['account.account'].search([('user_type_id', '=', self.env.ref('account.data_account_type_receivable').id)], limit=1)
        self.account_revenue = self.env['account.account'].search([('user_type_id', '=', self.env.ref('account.data_account_type_revenue').id)], limit=1)

        self.env.ref('uom.product_uom_unit').l10n_co_edi_ubl = 'S7'

    def test_dont_handle_non_colombian(self):
        self.company.country_id = self.env.ref('base.us')
        product = self.env.ref('product.product_product_4')
        invoice = self.env['account.move'].with_context(default_type='out_invoice').create({
            'partner_id': self.partner.id,
            'account_id': self.account_receivable.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product.id,
                    'quantity': 1,
                    'price_unit': 42,
                    'name': 'something',
                    'account_id': self.account_revenue.id,
                })
            ]
        })

        invoice.post()
        self.assertEqual(invoice.l10n_co_edi_invoice_status, 'not_sent',
                         'Invoices belonging to a non-Colombian company should not be sent.')

    def _validate_and_compare(self, invoice, invoice_number, filename_expected):

        return_value = {
            'message': 'mocked success',
            'transactionId': 'mocked_success',
        }
        with patch('odoo.addons.l10n_co_edi.models.carvajal_request.CarvajalRequest.upload', new=Mock(return_value=return_value)):
            invoice.post()

        invoice.number = invoice_number
        generated_xml = invoice._l10n_co_edi_generate_xml().decode()

        # the ENC_{7,8,16} tags contain information related to the "current" date
        for date_tag in ('ENC_7', 'ENC_8', 'ENC_16'):
            generated_xml = re.sub('<%s>.*</%s>' % (date_tag, date_tag), '', generated_xml)

        # show the full diff
        self.maxDiff = None
        with misc.file_open(os.path.join('l10n_co_edi', 'tests', filename_expected)) as f:
            self.assertEqual(f.read().strip(), generated_xml.strip())

    def test_invoice(self):
        '''Tests if we generate an accepted XML for an invoice and a credit note.'''
        product = self.env.ref('product.product_product_4')
        invoice = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'account_id': self.account_receivable.id,
            'type': 'out_invoice',
            'invoice_user_id': self.salesperson.id,
            'name': 'OC 123',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product.id,
                    'quantity': 150,
                    'price_unit': 250,
                    'discount': 10,
                    'name': 'Line 1',
                    'account_id': self.account_revenue.id,
                    'tax_ids': [(6, 0, (self.tax.id, self.retention_tax.id))],
                }),
                (0, 0, {
                    'quantity': 1,
                    'price_unit': 0.2,
                    'name': 'Line 2',
                    'account_id': self.account_revenue.id,
                    'tax_ids': [(6, 0, (self.tax.id, self.retention_tax.id))],
                    'uom_id': self.env.ref('uom.product_uom_unit').id,
                })
            ]
        })

        self._validate_and_compare(invoice, 'TEST/00001', 'accepted_invoice.xml')

        # To stop a warning about "Tax Base Amount not computable
        # probably due to a change in an underlying tax " which seems
        # to be expected when generating refunds.
        with mute_logger('odoo.addons.account.models.account_invoice'):
            credit_note = invoice.refund()

        self._validate_and_compare(credit_note, 'TEST/00002', 'accepted_credit_note.xml')
