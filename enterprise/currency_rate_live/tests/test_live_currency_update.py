from odoo.tests.common import TransactionCase, tagged


@tagged('-standard', 'external')
class CurrencyTestCase(TransactionCase):

    def setUp(self):
        super(CurrencyTestCase, self).setUp()
        # Each test will check the number of rates for USD
        self.currency_usd = self.env.ref('base.USD')
        self.test_company = self.env['res.company'].create({
            'name': 'Test Company',
            'currency_id': self.currency_usd.id,
        })

    def test_live_currency_update_ecb(self):
        self.test_company.currency_provider = 'ecb'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_fta(self):
        self.test_company.currency_provider = 'fta'
        # testing Swiss Federal Tax Administration requires that Franc Suisse can be found
        # which is not the case in runbot/demo data as l10n_ch is not always installed
        self.env.ref('base.CHF').write({'active': True})
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_banxico(self):
        self.test_company.currency_provider = 'banxico'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        if res:
            self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_boc(self):
        self.test_company.currency_provider = 'boc'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_xe_com(self):
        self.test_company.currency_provider = 'xe_com'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)
