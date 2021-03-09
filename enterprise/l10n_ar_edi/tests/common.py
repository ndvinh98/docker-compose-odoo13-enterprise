# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import Form
from odoo.tests.common import SingleTransactionCase
from odoo.modules.module import get_module_resource
import base64
import random
import logging

_logger = logging.getLogger(__name__)


class TestEdi(SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestEdi, cls).setUpClass()

        cls.company_ri = cls.env.ref('l10n_ar.company_ri')

        # Set context to do not make cr.commit() for unit tests
        cls.env = cls.env(context={'l10n_ar_invoice_skip_commit': True})

        # partners
        cls.partner_ri = cls.env.ref('l10n_ar.res_partner_adhoc')
        cls.partner_cf = cls.env.ref('l10n_ar.par_cfa')
        cls.partner_fz = cls.env.ref('l10n_ar.res_partner_cerrocastor')
        cls.partner_ex = cls.env.ref('l10n_ar.res_partner_expresso')
        cls.partner_mipyme = cls.env.ref('l10n_ar.res_partner_mipyme')
        cls.partner_mipyme_ex = cls.env.ref('l10n_ar.res_partner_mipyme').copy({'name': 'MiPyme Exento', 'l10n_ar_afip_responsibility_type_id': cls.env.ref('l10n_ar.res_IVAE').id})

        # Products
        cls.product_iva_21 = cls.env.ref('product.product_product_6')
        cls.service_iva_27 = cls.env.ref('l10n_ar.product_product_telefonia')

        # Document Types
        cls.document_type = {'invoice_a': cls.env.ref('l10n_ar.dc_a_f'),
                             'credit_note_a': cls.env.ref('l10n_ar.dc_a_nc'),
                             'invoice_b': cls.env.ref('l10n_ar.dc_b_f'),
                             'credit_note_b': cls.env.ref('l10n_ar.dc_b_nc'),
                             'invoice_e': cls.env.ref('l10n_ar.dc_e_f'),
                             'invoice_mipyme_a': cls.env.ref('l10n_ar.dc_fce_a_f'),
                             'invoice_mipyme_b': cls.env.ref('l10n_ar.dc_fce_b_f')}

        # taxes
        cls.tax_21 = cls._search_tax(cls, 'iva_21')
        cls.tax_27 = cls._search_tax(cls, 'iva_27')

    # Initialition

    def _set_today_rate(self, currency, value):
        rate_obj = self.env['res.currency.rate']
        rate = rate_obj.search([('currency_id', '=', currency.id), ('name', '=', fields.Date.to_string(fields.Date.today())),
                                ('company_id', '=', self.env.company.id)])
        if rate:
            rate.rate = value
        else:
            rate_obj.create({'company_id': self.env.company.id, 'currency_id': currency.id, 'rate': value})
        _logger.log(25, 'Using %s rate %s' % (currency.name, currency.rate))

    def _prepare_multicurrency_values(self):
        # Enable multi currency
        self.env.user.write({'groups_id': [(4, self.env.ref('base.group_multi_currency').id)]})
        # Set ARS as main currency
        self._set_today_rate(self.env.ref('base.ARS'), 1.0)
        # Set Rates for USD currency takint into account the value from AFIP
        USD = self.env.ref('base.USD')
        _date, value = USD._l10n_ar_get_afip_ws_currency_rate()
        # value = 1.0 / 62.013
        self._set_today_rate(USD, 1.0 / value)

    # Re used unit tests methods

    def _test_connection(self):
        """ Review that the connection is made and all the documents are syncronized"""
        with self.assertRaisesRegex(UserError, '"Check Available AFIP PoS" is not implemented in testing mode for webservice'):
            self.journal.l10n_ar_check_afip_pos_number()
        self.assertFalse(self.journal.l10n_ar_sync_next_number_with_afip(), 'Sync Next Numbers with AFIP fails')

    def _test_consult_invoice(self, expected_result=None):
        invoice = self._create_invoice_product()
        self._edi_validate_and_review(invoice, expected_result=expected_result)

        # Consult the info about the last invoice
        last = invoice.journal_id._l10n_ar_get_afip_last_invoice_number(invoice.l10n_latam_document_type_id)
        document_parts = invoice._l10n_ar_get_document_number_parts(invoice.l10n_latam_document_number, invoice.l10n_latam_document_type_id.code)
        self.assertEqual(last, document_parts['invoice_number'])

        # Consult the info about specific invoice
        with self.assertRaisesRegex(UserError, '(CodAutorizacion|Cae).*%s' % invoice.l10n_ar_afip_auth_code):
            self.env['l10n_ar_afip.ws.consult'].create({'number': last,
                                                        'journal_id': invoice.journal_id.id,
                                                        'document_type_id': invoice.l10n_latam_document_type_id.id}).button_confirm()
        return invoice

    def _test_case(self, document_type, concept, forced_values=None, expected_document=None, expected_result=None):
        values = {}
        forced_values = forced_values or {}
        create_invoice = {'product': self._create_invoice_product,
                          'service': self._create_invoice_service,
                          'product_service': self._create_invoice_product_service}
        create_invoice = create_invoice.get(concept)
        expected_document = self.document_type[document_type]

        if 'mipyme' in document_type:
            values.update({'document_type': expected_document, 'lines': [{'price_unit': 100000}]})
            if '_a' in document_type or '_c' in document_type:
                values.update({'partner': self.partner_mipyme})
            elif '_b' in document_type:
                values.update({'partner': self.partner_mipyme_ex})
        elif '_b' in document_type:
            values.update({'partner': self.partner_cf})

        values.update(forced_values)
        invoice = create_invoice(values)
        self.assertEqual(invoice.l10n_latam_document_type_id.display_name, expected_document.display_name, 'The document should be %s' % expected_document.display_name)
        self._edi_validate_and_review(invoice, expected_result=expected_result)
        return invoice

    def _test_case_credit_note(self, document_type, invoice, data=None, expected_result=None):
        refund = self._create_credit_note(invoice, data=data)
        expected_document = self.document_type[document_type]
        self.assertEqual(refund.l10n_latam_document_type_id.display_name, expected_document.display_name, 'The document should be %s' % expected_document.display_name)
        self._edi_validate_and_review(refund, expected_result=expected_result)
        return refund

    def _test_demo_cases(self, cases):
        for xml_id, test_case in cases.items():
            _logger.info('  * running test %s: %s' % (xml_id, test_case))
            invoice = self._duplicate_demo_invoice(xml_id)
            self._edi_validate_and_review(invoice, error_msg=test_case)

    # Helpers

    def _create_journal(self, afip_ws, data=None):
        """ Create a journal of a given AFIP ws type.
        If there is a problem because we are using a AFIP certificate that is already been in use then change the certificate and try again """
        data = data or {}
        mapping = {'WSFE': 'RAW_MAW', 'WSFEX': 'FEEWS', 'WSBFE': 'BFEWS', 'PREPRINTED': 'II_IM'}
        afip_ws = afip_ws.upper()
        pos_number = str(random.randint(0, 99999))
        if 'l10n_ar_afip_pos_number' in data:
            pos_number = data.pop('l10n_ar_afip_pos_number')
        values = {'name': '%s %s' % (afip_ws.replace('WS', ''), pos_number),
                  'type': 'sale',
                  'code': afip_ws,
                  'l10n_ar_afip_pos_system': mapping.get(afip_ws),
                  'l10n_ar_afip_pos_number': pos_number,
                  'l10n_latam_use_documents': True,
                  'company_id': self.env.company.id,
                  'l10n_ar_afip_pos_partner_id': self.partner_ri.id}
        values.update(data)

        # When we create the journal we are syncronizing document types sequeces with the ones we have in AFIP. In order to connection AFIP we need to
        # to create a token which depend on the configured AFIP certificate . If the certificate is been used by another testing instance will raise an error
        # telling us that the token can not be used and need to wait 10 minutos or change with another certificate. To avoid this and always run the unit
        # tests we randonly change the certificate and try to create the journal (connect to AFIP) until there is not token error.
        journal = False
        while not journal:
            try:
                journal = self.env['account.journal'].create(values)
                journal.l10n_ar_sync_next_number_with_afip()
                _logger.info('Using certificate %s for %s company' % (self.env.company.l10n_ar_afip_ws_crt_fname, self.env.company.name))
                _logger.info('Created journal %s for company %s' % (journal.name, self.env.company.name))
            except Exception:
                old = self.env.company.l10n_ar_afip_ws_crt_fname or 'NOT DEFINED'
                self.env.company.l10n_ar_afip_ws_crt = base64.b64encode(open(get_module_resource('l10n_ar_edi', 'tests', 'test_cert%d.crt' % random.randint(1, 3)), 'rb').read())
                _logger.log(25, 'Certificate %s already in use. Change to certificate %s for %s company' % (old, self.env.company.l10n_ar_afip_ws_crt_fname, self.env.company.name))
        return journal

    def _create_invoice(self, data=None, invoice_type='out_invoice'):
        data = data or {}
        with Form(self.env['account.move'].with_context(default_type=invoice_type)) as invoice_form:
            invoice_form.partner_id = data.pop('partner', self.partner)
            if 'in_' not in invoice_type:
                invoice_form.journal_id = data.pop('journal', self.journal)

            if data.get('document_type'):
                invoice_form.l10n_latam_document_type_id = data.pop('document_type')
            if data.get('document_number'):
                invoice_form.l10n_latam_document_number = data.pop('document_number')
            if data.get('incoterm'):
                invoice_form.invoice_incoterm_id = data.pop('incoterm')
            if data.get('currency'):
                invoice_form.currency_id = data.pop('currency')
            for line in data.get('lines', [{}]):
                with invoice_form.invoice_line_ids.new() as invoice_line_form:
                    if line.get('display_type'):
                        invoice_line_form.display_type = line.get('display_type')
                        invoice_line_form.name = line.get('name', 'not invoice line')
                    else:
                        invoice_line_form.product_id = line.get('product', self.product_iva_21)
                        invoice_line_form.quantity = line.get('quantity', 1)
                        invoice_line_form.price_unit = line.get('price_unit', 100)
        invoice = invoice_form.save()
        return invoice

    def _create_invoice_product(self, data=None):
        data = data or {}
        return self._create_invoice(data)

    def _create_invoice_service(self, data=None):
        data = data or {}
        newlines = []
        for line in data.get('lines', [{}]):
            line.update({'product': self.service_iva_27})
            newlines.append(line)
        data.update({'lines': newlines})
        return self._create_invoice(data)

    def _create_invoice_product_service(self, data=None):
        data = data or {}
        newlines = []
        for line in data.get('lines', [{}]):
            line.update({'product': self.product_iva_21})
            newlines.append(line)
        data.update({'lines': newlines + [{'product': self.service_iva_27}]})
        return self._create_invoice(data)

    def _create_credit_note(self, invoice, data=None):
        data = data or {}
        refund_wizard = self.env['account.move.reversal'].with_context(active_ids=[invoice.id], active_model='account.move').create({
            'reason': data.get('reason', 'Mercadería defectuosa'),
            'refund_method': data.get('refund_method', 'refund'),
            'move_id': invoice.id})
        refund_wizard._onchange_move_id()

        forced_document_type = data.get('document_type')
        if forced_document_type:
            refund_wizard.l10n_latam_document_type_id = forced_document_type.id

        res = refund_wizard.reverse_moves()
        refund = self.env['account.move'].browse(res['res_id'])
        return refund

    def _create_debit_note(self, document_type, invoice, expected_result='A'):
        expected_document = self.document_type[document_type]
        debit_note = self._test_case(document_type, 'product_service', {'document_type': expected_document})
        debit_note.invoice_origin = invoice.l10n_latam_document_number
        self.assertEqual(debit_note.l10n_latam_document_type_id.display_name, expected_document.display_name, 'The document should be %s' % expected_document.display_name)
        self._edi_validate_and_review(debit_note, expected_result=expected_result)
        return debit_note

    def _search_tax(self, tax_type):
        res = self.env['account.tax'].with_context(active_test=False).search([('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id), ('tax_group_id', '=', self.env.ref('l10n_ar.tax_group_' + tax_type).id)], limit=1)
        self.assertTrue(res, '%s Tax was not found' % (tax_type))
        return res

    def _search_fp(self, name):
        return self.env['account.fiscal.position'].search([('company_id', '=', self.env.company.id), ('name', '=', name)])

    def _duplicate_demo_invoice(self, xml_id):
        demo_invoice = self.env.ref('l10n_ar.' + xml_id)
        invoice = demo_invoice.copy({'journal_id': self.journal.id})
        invoice._onchange_partner_journal()
        invoice._onchange_partner_id()
        return invoice

    def _edi_validate_and_review(self, invoice, expected_result=None, error_msg=None):
        """ Validate electronic invoice and review that the invoice has been proper validated. """
        expected_result = expected_result or 'A'
        error_msg = error_msg or 'This test return a result different from the expteced (%s)' % expected_result
        invoice.post()

        self.assertEqual(invoice.state, 'posted', error_msg)
        self.assertEqual(invoice.l10n_ar_afip_auth_mode, 'CAE', error_msg)

        detail_info = error_msg + '\nReponse\n' + invoice.l10n_ar_afip_xml_response + '\nMsg\n' + invoice.message_ids[0].body
        self.assertEqual(invoice.l10n_ar_afip_result, expected_result, detail_info)

        self.assertTrue(invoice.l10n_ar_afip_auth_code, error_msg)
        self.assertTrue(invoice.l10n_ar_afip_auth_code_due, error_msg)
        self.assertTrue(invoice.l10n_ar_afip_xml_request, error_msg)
        self.assertTrue(invoice.l10n_ar_afip_xml_response, error_msg)


class TestFex(TestEdi):

    @classmethod
    def setUpClass(cls):
        super(TestFex, cls).setUpClass()

        context = dict(cls.env.context, allowed_company_ids=[cls.company_ri.id])
        cls.env = cls.env(context=context)

        cls.partner = cls.partner_ex
        cls.incoterm = cls.env.ref('account.incoterm_EXW')
        cls.journal = cls._create_journal(cls, 'wsfex')

        # Document Types
        cls.document_type.update({
            'invoice_e': cls.env.ref('l10n_ar.dc_e_f'),
            'credit_note_e': cls.env.ref('l10n_ar.dc_e_nc')})

    def _create_invoice_product(self, data=None):
        data = data or {}
        data.update({'incoterm': self.incoterm})
        return super()._create_invoice_product(data=data)

    def _create_invoice_product_service(self, data=None):
        data = data or {}
        data.update({'incoterm': self.incoterm})
        return super()._create_invoice_product_service(data=data)
