# coding: utf-8
import base64
import os

from lxml import objectify

from odoo.tools import misc
from odoo.addons.l10n_mx_edi.tests.common import InvoiceTransactionCase


class TestL10nMxEdiExternalTrade(InvoiceTransactionCase):
    def setUp(self):
        super(TestL10nMxEdiExternalTrade, self).setUp()
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag
        unit = self.env.ref('uom.product_uom_unit')
        self.tariff = self.ref(
            'l10n_mx_edi_external_trade.tariff_fraction_84289099')
        self.product.write({
            'l10n_mx_edi_umt_aduana_id': unit.id,
            'l10n_mx_edi_tariff_fraction_id': self.tariff,
        })
        self.namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'cce11': 'http://www.sat.gob.mx/ComercioExterior11',
        }
        self.set_currency_rates(mxn_rate=1, usd_rate=1)
        self.incoterm = self.ref('account.incoterm_FCA')

    def test_l10n_mx_edi_invoice_external_trade(self):
        self.xml_expected_str = misc.file_open(os.path.join(
            'l10n_mx_edi', 'tests',
            'expected_cfdi_external_trade_33.xml')).read().encode('UTF-8')
        self.xml_expected = objectify.fromstring(self.xml_expected_str)

        self.company.partner_id.write({
            'l10n_mx_edi_locality_id': self.env.ref(
                'l10n_mx_edi.res_locality_mx_son_04').id,
            'city_id': self.env.ref('l10n_mx_edi.res_city_mx_son_018').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_colony_code': '2883',
            'zip': 85136,
        })
        self.partner_agrolait.commercial_partner_id.write({
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_23').id,
            'zip': 39301,
        })
        self.partner_agrolait.write({
            'country_id': self.env.ref('base.us').id,
            'state_id': self.env.ref('base.state_us_23').id,
            'l10n_mx_edi_external_trade': True,
            'zip': 39301,
            'vat': '123456789',
        })

        self.company._load_xsd_attachments()

        # -----------------------
        # Testing sign process with External Trade
        # -----------------------

        invoice = self.create_invoice()
        invoice.incoterm_id = self.incoterm
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
        xml = objectify.fromstring(base64.b64decode(invoice.l10n_mx_edi_cfdi))
        self.assertTrue(xml.Complemento.xpath(
            'cce11:ComercioExterior', namespaces=self.namespaces),
            "The node '<cce11:ComercioExterior> should be present")
        xml_cce = xml.Complemento.xpath(
            'cce11:ComercioExterior', namespaces=self.namespaces)[0]
        xml_cce_expected = self.xml_expected.Complemento.xpath(
            'cce11:ComercioExterior', namespaces=self.namespaces)[0]
        self.assertEqualXML(xml_cce, xml_cce_expected)

        # -------------------------
        # Testing case UMT Aduana, l10n_mx_edi_code_aduana == 1
        # -------------------------
        kg = self.env.ref('uom.product_uom_kgm')
        kg.l10n_mx_edi_code_aduana = '01'
        self.product.write({
            'weight': 2,
            'l10n_mx_edi_umt_aduana_id': kg.id,
            'l10n_mx_edi_tariff_fraction_id': self.ref(
                'l10n_mx_edi_external_trade.tariff_fraction_72123099'),
        })
        invoice = self.create_invoice()
        invoice.incoterm_id = self.incoterm
        invoice.post()
        line = invoice.invoice_line_ids
        self.assertEqual(line.l10n_mx_edi_qty_umt,
                         line.product_id.weight * line.quantity,
                         'Qty UMT != weight * quantity')
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))

        # ------------------------
        # Testing case UMT Aduana, UMT Custom != Kg and UMT Custom != uos_id
        # ------------------------
        kg.l10n_mx_edi_code_aduana = '08'
        self.product.write({
            'l10n_mx_edi_tariff_fraction_id': self.ref(
                'l10n_mx_edi_external_trade.tariff_fraction_27101299'),
        })
        invoice = self.create_invoice()
        invoice.incoterm_id = self.incoterm
        # Manually add the value Qty UMT
        line = invoice.invoice_line_ids
        self.assertEqual(line.l10n_mx_edi_qty_umt, 0,
                         'Qty umt must be manually assigned')
        invoice.invoice_line_ids.l10n_mx_edi_qty_umt = 2
        invoice.post()
        self.assertEqual(invoice.l10n_mx_edi_pac_status, "signed",
                         invoice.message_ids.mapped('body'))
