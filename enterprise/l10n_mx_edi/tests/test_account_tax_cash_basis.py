# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo.fields import Date
from odoo.tools import float_round
from odoo import api, registry
from . import common


class TestL10nMxTaxCashBasis(common.InvoiceTransactionCase):

    def setUp(self):
        super(TestL10nMxTaxCashBasis, self).setUp()
        with registry().cursor() as cr:
            env = api.Environment(cr, 1, {})
            dp = env.ref('product.decimal_price')
            dp.digits = 3

        self.today = Date.today()
        self.yesterday = self.today - timedelta(days=1)
        self.two_days_ago = self.today - timedelta(days=2)
        self.a_week_ago = self.today - timedelta(days=7)

        # In order to avoid using this method we at l10n_mx_edi need to use a
        # company of our own. Having MXN as currency. And Loading our Chart of
        # account and base our tests on it.
        # /!\ FIXME: @luistorresm or @hbto
        self.delete_journal_data()

        self.env.company.write({'currency_id': self.mxn.id})
        self.create_rates()

        self.tax_cash_basis_journal_id = self.company.tax_cash_basis_journal_id
        self.user_type_id = self.env.ref(
            'account.data_account_type_current_liabilities')
        self.account_model = self.env['account.account']
        self.account_move_line_model = self.env['account.move.line']
        self.journal_model = self.env['account.journal']
        self.payment_model = self.env['account.payment']
        self.precision = self.env.company.currency_id.decimal_places
        self.payment_method_manual_out = self.env.ref(
            'account.account_payment_method_manual_out')
        self.payment_method_manual_in = self.env.ref(
            'account.account_payment_method_manual_in')
        self.bank_journal_mxn = self.env['account.journal'].create(
            {'name': 'Bank MXN',
             'type': 'bank',
             'code': 'BNK37'})
        self.bank_journal_usd = self.env['account.journal'].create(
            {'name': 'Bank USD',
             'type': 'bank',
             'code': 'BNK52',
             'currency_id': self.usd.id})
        self.tax_model = self.env['account.tax']
        self.tax_account = self.create_account(
            '11111101', 'Tax Account')
        self.cash_tax_account = self.create_account(
            '77777777', 'Cash Tax Account')
        self.account_tax_cash_basis = self.create_account(
            '99999999', 'Tax Base Account')
        self.tax_positive.write({
            'l10n_mx_cfdi_tax_type': 'Tasa',
            'tax_exigibility': 'on_payment',
            'cash_basis_transition_account_id': self.cash_tax_account.id,
            'cash_basis_base_account_id': self.account_tax_cash_basis.id,
            'invoice_repartition_line_ids': [
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'base',
                }),

                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'account_id': self.tax_account.id,
                }),
            ],
            'refund_repartition_line_ids': [
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'base',
                }),

                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'account_id': self.tax_account.id,
                }),
            ],
        })

    def delete_journal_data(self):
        """Delete journal data
        delete all journal-related data, so a new currency can be set.
        """

        # 1. Reset to draft invoices, so some records may be deleted
        company = self.company
        invoices = self.env['account.move'].search(
            [('company_id', '=', company.id)])
        invoices.write({'state': 'draft'})

        # 2. Delete related records
        models_to_clear = [
            'account.move.line', 'account.payment', 'account.bank.statement']
        for model in models_to_clear:
            records = self.env[model].search([('company_id', '=', company.id)])
            records.unlink()

    def create_rates(self):
        # Let's delete rates that could be messy to have
        self.rate_model.search([]).unlink()
        dates = (self.today, self.yesterday, self.a_week_ago)
        rates = (1.25, 1.00, 1/1.25)
        for date, rate in zip(dates, rates):
            self.rate_model.create({
                'currency_id': self.usd.id,
                'company_id': self.company.id,
                'name': date,
                'rate': rate})

    def create_payment(self, invoice, date, amount, journal, currency_id):
        payment_method_id = self.payment_method_manual_out.id
        if invoice.type == 'in_invoice':
            payment_method_id = self.payment_method_manual_in.id

        default_dict = self.payment_model.with_context(active_model='account.move', active_ids=invoice.id).default_get(self.payment_model.fields_get_keys())
        payments = self.payment_model.new({**default_dict, **{
            'payment_date': date,
            'l10n_mx_edi_payment_method_id': self.payment_method_cash.id,
            'payment_method_id': payment_method_id,
            'journal_id': journal.id,
            'currency_id': currency_id.id,
            'communication': invoice.name,
            'amount': amount,
        }})

        return payments.create_payments()

    def create_account(self, code, name, user_type_id=False):
        """This account is created to use like cash basis account and only
        it will be filled when there is payment
        """
        account_ter = self.account_model.create({
            'name': name,
            'code': code,
            'user_type_id': user_type_id or self.user_type_id.id,
        })
        return account_ter

    def create_invoice(
            self, amount, invoice_date, inv_type='out_invoice',
            currency_id=None):
        if currency_id is None:
            currency_id = self.usd.id
        invoice = self.env['account.move'].with_env(
            self.env(user=self.user_billing)).create({
                'partner_id': self.partner_agrolait.id,
                'type': inv_type,
                'currency_id': currency_id,
                'l10n_mx_edi_payment_method_id': self.payment_method_cash.id,
                'l10n_mx_edi_partner_bank_id': self.account_payment.id,
                'date_invoice': invoice_date,
            })

        self.create_invoice_line(invoice, 1000)
        invoice.invoice_line_ids.write(
            {'invoice_line_tax_ids': [(6, None, [self.tax_positive.id])]})

        invoice.refresh()

        # validate invoice
        invoice.compute_taxes()
        invoice.post()

        return invoice

    def create_invoice_line(self, invoice_id, price_unit):
        self.product.sudo().write({
            'default_code': 'PR01',
            'l10n_mx_edi_code_sat_id': self.ref(
                'l10n_mx_edi.prod_code_sat_01010101'),
        })
        invoice_line = self.invoice_line_model.new({
            'product_id': self.product.id,
            'invoice_id': invoice_id,
            'quantity': 1,
            # 'invoice_line_tax_ids': [self.tax_positive.id],
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write({
            name: invoice_line[name] for name in invoice_line._cache})
        invoice_line_dict['price_unit'] = price_unit
        self.invoice_line_model.create(invoice_line_dict)

    def test_00_xrates(self):
        """Test if the company is Mexican. Let's assert the currency conversion
        prior to begin and not waste time with further debug."""

        self.assertEquals(
            self.env.company.country_id,
            self.env.ref('base.mx'), "The company's country is not Mexico")

        xrate = self.mxn._convert(1, self.usd, self.company, self.two_days_ago)
        self.assertEquals(
            xrate, 0.80, 'two days ago in USD at a rate => 1MXN = 0.80 USD')

        xrate = self.mxn._convert(1, self.usd, self.company, self.yesterday)
        self.assertEquals(
            xrate, 1.00, 'yesterday in USD at a rate => 1MXN = 1.00 USD')

        xrate = self.mxn._convert(1, self.usd, self.company, self.today)
        self.assertEquals(
            xrate, 1.25, 'today in USD at a rate => 1MXN = 1.25 USD')

    def test_01_cash_basis_multicurrency_payment_before_invoice(self):
        """Test to validate tax effectively receivable
        My company currency is MXN.

        Invoice issued yesterday in USD at a rate => 1MXN = 1 USD.
        Booked like:

            Receivable          1160                1160    USD
                Revenue                 1000       -1000    USD
                Taxes to Collect         160        -160    USD

        Payment issued two days ago in USD at a rate => 1MXN = 0.80 USD.
        Booked like:

            Bank                1450                1160    USD
                Receivable              1450       -1160    USD

        This Generates a Exchange Rate Difference.
        Booked like:

            Receivable           290                   0    USD
                Gain Exchange rate       290           0    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1250                1000    USD
                Tax Base Account        1250       -1000    USD
            Taxes to Collect     200                 160    USD
                Taxes to Paid            200        -160    USD

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 1250.00
            - Paid to SAT MXN 200.00
            - Have a difference of MXN 40.00 for Taxes to Collect that I would
            later have to issue as a Loss in Exchange Rate Difference

            Loss Exchange rate    40                   0    USD
                Taxes to Collect          40           0    USD
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.usd.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.two_days_ago, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -1250)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 40)

    def test_02_cash_basis_multicurrency_payment_after_invoice(self):
        """Test to validate tax effectively receivable
        My company currency is MXN.

        Invoice issued two days ago in USD at a rate => 1MXN = 0.80 USD.
        Booked like:

            Receivable          1450                1160    USD
                Revenue                 1250       -1000    USD
                Taxes to Collect         200        -160    USD

        Payment issued today in USD at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Bank                 928                1160    USD
                Receivable               928       -1160    USD

        This Generates a Exchange Rate Difference.
        Booked like:

            Loss Exchange rate   522                   0    USD
                Receivable               522           0    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account     800                1000    USD
                Tax Base Account         800       -1000    USD
            Taxes to Collect     128                 160    USD
                Taxes to Paid            128        -160    USD

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 800.00
            - Paid to SAT MXN 128.00
            - Have a difference of MXN -72.00 for Taxes to Collect that I would
            later have to issue as a Gain in Exchange Rate Difference

            Taxes to Collect      72                   0    USD
                Gain Exchange rate        72           0    USD
        """

        invoice_date = self.two_days_ago
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.usd.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.today, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -800)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), -72)

    def test_03_cash_basis_multicurrency_payment_same_day_than_invoice(self):
        """Test to validate tax effectively receivable
        My company currency is MXN.

        Invoice issued two days ago in USD at a rate => 1MXN = 0.8 USD.
        Booked like:

            Receivable          1450                1160    USD
                Revenue                 1250       -1000    USD
                Taxes to Collect         200        -160    USD

        Payment issued two days ago in USD at a rate => 1 MXN = 0.8 USD.
        Booked like:

            Bank                1450                1160    USD
                Receivable              1450       -1160    USD

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1250                1000    USD
                Tax Base Account        1250       -1000    USD
            Taxes to Collect     200                 160    USD
                Taxes to Paid            200        -160    USD

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 1250.00
            - Paid to SAT MXN 200.00
            - Have no difference for Taxes to Collect
        """

        invoice_date = self.two_days_ago
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.usd.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.two_days_ago, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -1250)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_04_invoice_company_currency_payment_not_company_currency(self):
        """Test to validate tax effectively receivable

        My company currency is MXN.

        Invoice issued yesterday in MXN at a rate => 1MXN = 1 USD.
        Booked like:

            Receivable          1160                   -      -
                Revenue                 1000           -      -
                Taxes to Collect         160           -      -

        Payment issued two days ago in USD at a rate => 1 MXN = 0.80 USD.
        Booked like:

            Bank                1160                 928    USD
                Receivable              1160        -928    USD

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1000                   0      -
                Tax Base Account        1000           0      -
            Taxes to Collect     160                   0      -
                Taxes to Paid            160           0      -

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 1000.00
            - Paid to SAT MXN 160.00
            - Have no difference for Taxes to Collect
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.company.currency_id.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.two_days_ago, 928, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -1000)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_05_invoice_not_company_currency_payment_in_company_currency(self):
        """Test to validate tax effectively receivable

        My company currency is MXN.

        Invoice issued yesterday in USD at a rate => 1MXN = 1 USD.
        Booked like:

            Receivable          1160                1160    USD
                Revenue                 1000       -1000    USD
                Taxes to Collect         160        -160    USD

        Payment issued today in MXN at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Bank                 928                   -      -
                Receivable               928           -      -

        This Generates a Exchange Rate Difference.
        Booked like:

            Loss Exchange rate   232                 232    USD
                Receivable               232        -232    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account     800                   0    USD
                Tax Base Account         800           0    USD
            Taxes to Collect     128                   0    USD  # (I'd expect the same value as in the invoice for amount_currency in tax: 160 USD)  # noqa
                Taxes to Paid            128           0    USD

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 800.00
            - Paid to SAT MXN 128.00
            - Have a difference of MXN -32.00 for Taxes to Collect that I would
            later have to issue as a Gain in Exchange Rate Difference

            Taxes to Collect      32                   0    USD
                Gain Exchange rate        32           0    USD
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.usd.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.today, 928, self.bank_journal_mxn, self.mxn)  # noqa

        # Testing that I am fetching the right Tax Base
        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -800)

        # Testing that I am fetching the right difference in Exchange rate
        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), -32)

    def test_06_invoice_company_currency_payment_not_company_currency(self):
        """Test to validate tax effectively receivable

        My company currency is MXN.

        Invoice issued yesterday in MXN at a rate => 1MXN = 1 USD.
        Booked like:

            Receivable          1160                   -      -
                Revenue                 1000           -      -
                Taxes to Collect         160           -      -

        Payment issued today in MXN at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Bank                1160                   -      -
                Receivable              1160           -      -

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1000                   -      -
                Tax Base Account        1000           -      -
            Taxes to Collect     160                   -      -
                Taxes to Paid            160           -      -

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 1000.00
            - Paid to SAT MXN 160.00
            - Have no difference for Taxes to Collect
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.company.currency_id.id)

        self.assertEqual(invoice_id.state, "open")
        self.assertEqual(
            invoice_id.invoice_line_ids.invoice_line_tax_ids.
            l10n_mx_cfdi_tax_type, "Tasa")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        xml = invoice_id.l10n_mx_edi_get_xml_etree()
        self.assertEqual(invoice_id.amount_total, float(xml.get('Total')),
                         "Total amount is not right")
        self.assertEqual(invoice_id.l10n_mx_edi_pac_status, "signed",
                         invoice_id.message_ids.mapped('body'))

        self.create_payment(
            invoice_id, self.today, 1160, self.bank_journal_mxn, self.mxn)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            -1000)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_07_cash_basis_multicurrency_payment_before_invoice(self):
        """Test to validate tax effectively Payable
        My company currency is MXN.

        Invoice issued yesterday in USD at a rate => 1MXN = 1 USD.
        Booked like:

            Expenses            1000                1000    USD
            Unpaid Taxes         160                 160    USD
                Payable                 1160       -1160    USD

        Payment issued two days ago in USD at a rate => 1MXN = 0.80 USD.
        Booked like:

            Payable             1450                1160    USD
                Bank                    1450       -1160    USD

        This Generates a Exchange Rate Difference.
        Booked like:

            Loss Exchange rate   290                   0    USD
                Payable                  290           0    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1250                1000    USD
                Tax Base Account        1250       -1000    USD
            Creditable Tax       200                 160    USD
                Unpaid Taxes             200        -160    USD

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 1250.00
            - Creditable Tax MXN 200.00
            - Have a difference of MXN -40.00 for Unpaid Taxes that I would
            later have to issue as a Loss in Exchange Rate Difference

            Unpaid Taxes          40                   0    USD
                Gain Exchange rate        40           0    USD
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.usd.id)

        self.create_payment(
            invoice_id, self.two_days_ago, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            1250)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), -40)

    def test_08_cash_basis_multicurrency_payment_after_invoice(self):
        """Test to validate tax effectively Payable
        My company currency is MXN.

        Invoice issued two days ago in USD at a rate => 1MXN = 0.80 USD.
        Booked like:

            Expenses            1250                1000    USD
            Unpaid Taxes         200                 160    USD
                Payable                 1450       -1160    USD

        Payment issued today in USD at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Payable              928                1160    USD
                Bank                     928       -1160    USD

        This Generates a Exchange Rate Difference.
        Booked like:

            Payable              522                   0    USD
                Gain Exchange rate       522           0    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account     800                1000    USD
                Tax Base Account         800       -1000    USD
            Creditable Tax       128                 160    USD
                Unpaid Taxes             128        -160    USD

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 800.00
            - Creditable Tax MXN 128.00
            - Have a difference of MXN 72.00 for Unpaid Taxes that I would
            later have to issue as a Loss in Exchange Rate Difference

            Loss Exchange rate    72                   0    USD
                Unpaid Taxes              72           0    USD
        """

        invoice_date = self.two_days_ago
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.usd.id)

        self.create_payment(
            invoice_id, self.today, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            800)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 72)

    def test_09_cash_basis_multicurrency_payment_same_day_than_invoice(self):
        """Test to validate tax effectively Payable
        My company currency is MXN.

        Invoice issued two days ago in USD at a rate => 1MXN = 0.8 USD.
        Booked like:

            Expenses            1250                1000    USD
            Unpaid Taxes         200                 160    USD
                Payable                 1450       -1160    USD

        Payment issued two days ago in USD at a rate => 1 MXN = 0.8 USD.
        Booked like:

            Payable             1450                1160    USD
                Bank                    1450       -1160    USD

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1250                1000    USD
                Tax Base Account        1250       -1000    USD
            Creditable Tax       200                 160    USD
                Unpaid Taxes             200        -160    USD

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 1250.00
            - Creditable Tax MXN 200.00
            - Have no difference for Unpaid Taxes
        """

        invoice_date = self.two_days_ago
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.usd.id)
        self.create_payment(
            invoice_id, self.two_days_ago, 1160, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            1250)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_10_invoice_company_currency_payment_not_company_currency(self):
        """Test to validate tax effectively Payable

        My company currency is MXN.

        Invoice issued yesterday in MXN at a rate => 1MXN = 1 USD.
        Booked like:

            Expenses            1000                   -      -
            Unpaid Taxes         160                   -      -
                Payable                 1160           -      -

        Payment issued two days ago in USD at a rate => 1 MXN = 0.80 USD.
        Booked like:

            Payable             1160                 928    USD
                Bank                    1160        -928    USD

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1000                   0      -
                Tax Base Account        1000           0      -
            Creditable Tax       160                   0      -
                Unpaid Taxes             160           0      -

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 1000.00
            - Creditable Tax MXN 160.00
            - Have no difference for Unpaid Taxes
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.company.currency_id.id)

        self.create_payment(
            invoice_id, self.two_days_ago, 928, self.bank_journal_usd, self.usd)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            1000)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_11_invoice_not_company_currency_payment_in_company_currency(self):
        """Test to validate tax effectively Payable

        My company currency is MXN.

        Invoice issued yesterday in USD at a rate => 1MXN = 1 USD.
        Booked like:

            Expenses            1000                1000    USD
            Unpaid Taxes         160                 160    USD
                Payable                 1160       -1160    USD

        Payment issued today in MXN at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Payable              928                   -      -
                Bank                     928           -      -

        This Generates a Exchange Rate Difference.
        Booked like:

            Payable              232                 232    USD
                Gain Exchange rate       522        -232    USD

        And a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account     800                   0    USD
                Tax Base Account         800           0    USD
            Creditable Tax       128                   0    USD  # (I'd expect the same value as in the invoice for amount_currency in tax: 160 USD)  # noqa
                Unpaid Taxes             128           0    USD

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 800.00
            - Creditable Tax MXN 128.00
            - Have a difference of MXN 32.00 for Unpaid Taxes that I would
            later have to issue as a Loss in Exchange Rate Difference

            Loss Exchange rate    32                   0    USD
                Unpaid Taxes              32           0    USD
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.usd.id)

        self.create_payment(
            invoice_id, self.today, 928, self.bank_journal_mxn, self.mxn)  # noqa

        # Testing that I am fetching the right Tax Base
        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            800)

        # Testing that I am fetching the right difference in Exchange rate
        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 32)

    def test_12_invoice_company_currency_payment_not_company_currency(self):
        """Test to validate tax effectively Payable

        My company currency is MXN.

        Invoice issued yesterday in MXN at a rate => 1MXN = 1 USD.
        Booked like:

            Expenses            1000                   -      -
            Unpaid Taxes         160                   -      -
                Payable                 1160           -      -

        Payment issued today in MXN at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Payable             1160                   -      -
                Bank                    1160           -      -

        This does not generates any Exchange Rate Difference.

        But a Tax Cash Basis Entry is generated.
        Booked like:

            Tax Base Account    1000                   -      -
                Tax Base Account        1000           -      -
            Creditable Tax       160                   -      -
                Unpaid Taxes             160           -      -

        What I expect from here:
            - Base to report to DIOT: Tax Base Account MXN 1000.00
            - Creditable Tax MXN 160.00
            - Have no difference for Unpaid Taxes
        """

        invoice_date = self.yesterday
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            inv_type='in_invoice',
            currency_id=self.company.currency_id.id)

        self.create_payment(
            invoice_id, self.today, 1160, self.bank_journal_mxn, self.mxn)  # noqa

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision),
            1000)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), 0)

    def test_14_cash_basis_multicurrency_creditnote_after_invoice(self):
        """Test to validate tax effectively receivable
        My company currency is MXN.

        Invoice issued two days ago in USD at a rate => 1MXN = 0.80 USD.
        Booked like:

            Receivable          1450                1160    USD
                Revenue                 1250       -1000    USD
                Taxes to Collect         200        -160    USD

        Credit Note issued today in USD at a rate => 1 MXN = 1.25 USD.
        Booked like:

            Revenue              800                1000    USD
            Taxes to Collect     128                 160    USD
                Receivable               928       -1160    USD

        This Generates a Exchange Rate Difference.
        Booked like:

            Loss Exchange rate   522                   0    USD
                Receivable               522           0    USD

        And two Tax Cash Basis Entry are generated.
        Booked like:

            Tax Base Account     800                1000    USD
                Tax Base Account         800       -1000    USD
            Taxes to Collect     128                 160    USD
                Taxes to Paid            128        -160    USD

            Tax Base Account     800                1000    USD
                Tax Base Account         800       -1000    USD
            Taxes to Paid        128                 160    USD
                Taxes to Collect         128        -160    USD

        What I expect from here:
            - Base to report to DIOT if it would be the case (not in this
            case): * Tax Base Account MXN 800.00 and MXN -800.00
            - Paid to SAT MXN 0.00
            - Have a difference of MXN -72.00 for Taxes to Collect that I would
            later have to issue as a Gain in Exchange Rate Difference

            Taxes to Collect      72                   0    USD
                Gain Exchange rate        72           0    USD
        """

        invoice_date = self.two_days_ago
        self.company.partner_id.write({
            'property_account_position_id': self.fiscal_position.id,
        })
        invoice_id = self.create_invoice(
            1000,
            invoice_date,
            currency_id=self.usd.id)

        self.assertEqual(invoice_id.state, "posted")

        refund = self.env['account.move.reversal'].with_context(active_ids=invoice_id.ids).create({
                'refund_method': 'refund',
                'reason': 'Refund Test',
                'date': self.today,
            })
        result = refund.reverse_moves()
        refund_id = result.get('domain')[1][2]
        refund = self.env['account.move'].browse(refund_id)
        refund.refresh()
        refund.post()
        self.assertEqual(refund.state, "open")

        ((invoice_id | refund)
         .mapped('move_id.line_ids')
         .filtered(lambda l: l.account_id.user_type_id.type == 'receivable')
         .reconcile())

        base_amls = self.account_move_line_model.search(
            [('account_id', '=', self.account_tax_cash_basis.id)])
        base_at_payment = sum(base_amls.filtered('tax_ids').mapped('balance'))
        self.assertEquals(
            float_round(base_at_payment, precision_digits=self.precision), 0)

        tax_amls = self.account_move_line_model.search(
            [('account_id', '=', self.tax_account.id)])
        tax_diff = sum(tax_amls.mapped('balance'))
        self.assertEquals(
            float_round(tax_diff, precision_digits=self.precision), -72)
