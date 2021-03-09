# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from lxml import objectify
from odoo import fields, _
from odoo.addons.l10n_mx_edi.tests.common import InvoiceTransactionCase

_logger = logging.getLogger()


class LandingCost(InvoiceTransactionCase):

    def setUp(self):
        super(LandingCost, self).setUp()
        self.obj_purchase = self.env['purchase.order']
        self.obj_sale = self.env['sale.order']
        self.landing = self.env['stock.landed.cost']
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        iva_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag
        for rep_line in self.tax_positive.invoice_repartition_line_ids:
            rep_line.tag_ids |= iva_tag
        self.journal_mx = self.env['account.journal'].search([
            ('name', '=', _('Customer Invoices'))], limit=1)
        self.journal_misc = self.env['account.journal'].search([
            ('code', '=', 'MISC')], limit=1)
        self.supplier = self.env.ref('base.res_partner_2')
        self.customer = self.env.ref('base.res_partner_3')
        self.tax_purchase = self.tax_model.search([('name', '=', 'IVA(16%) COMPRAS')])[0]
        self.product.write({
            'landed_cost_ok': True,
            'invoice_policy': 'delivery',
        })
        self.account_inventory = self.env.ref('l10n_mx.1_cuenta115_01')
        self.account_merchancy = self.env.ref('l10n_mx.1_cuenta115_05')
        self.product.categ_id.sudo().write({
            'property_cost_method': 'fifo',
            'property_valuation': 'real_time',
            'property_stock_account_input_categ_id': self.account_merchancy,
            'property_stock_account_output_categ_id': self.account_merchancy,
            'property_stock_valuation_account_id': self.account_inventory,
        })

        node_expected = '''
        <cfdi:InformacionAduanera xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        NumeroPedimento="15  48  3009  0001234"/>
        '''
        self.xml_expected = objectify.fromstring(node_expected)

        # Generated two products
        self.products = {
            'product_1': self.product,
            'product_2': self.product.copy(),
        }

    def create_purchase_order(self):
        return self.obj_purchase.create({
            'partner_id': self.supplier.id,
            'order_line': [(0, 0, ope) for ope in [{
                'name': p.name, 'product_id': p.id, 'product_qty': 2,
                'product_uom': p.uom_id.id, 'price_unit': p.list_price,
                'taxes_id': [(4, self.tax_purchase.id)],
                'date_planned': fields.Datetime.now()
            } for (_, p) in self.products.items()]],
        })

    def create_sale_order(self):
        return self.obj_sale.create({
            'partner_id': self.customer.id,
            'order_line': [(0, 0, ope) for ope in [{
                'name': p.name, 'product_id': p.id, 'product_uom_qty': 2,
                'product_uom': p.uom_id.id, 'price_unit': p.list_price,
                'tax_id': [(4, self.tax_positive.id)],
            } for (_, p) in self.products.items()]],
        })

    def test_10_landing_cost(self):
        """Verify customs information on invoice from landed cost"""
        self.env.user.groups_id |= (
            self.env.ref('purchase.group_purchase_manager') |
            self.env.ref('stock.group_stock_manager') |
            self.env.ref('sales_team.group_sale_manager')
        )
        purchase = self.create_purchase_order()
        purchase.button_confirm()
        picking_purchase = purchase.picking_ids
        picking_purchase.move_line_ids.write({'qty_done': 2})
        picking_purchase.action_done()
        landing = self.landing.create({
            'l10n_mx_edi_customs_number': '15  48  3009  0001234',
            'picking_ids': [(4, picking_purchase.id)],
            'cost_lines': [(0, 0, {
                'product_id': self.product.id,
                'price_unit': 100,
                'split_method': 'by_quantity',
                'account_id': self.env.ref('l10n_mx.1_cuenta108_02').id,
            })],
            'account_journal_id': self.journal_misc.id,
        })
        landing.compute_landed_cost()
        landing.button_validate()
        sale = self.create_sale_order()
        sale.action_confirm()
        picking_sale = sale.picking_ids

        # Generate two moves for procurement by partial delivery
        picking_sale.action_assign()
        picking_sale.move_line_ids.write({'qty_done': 1})
        backorder_wiz_id = picking_sale.button_validate()['res_id']
        backorder_wiz = self.env['stock.backorder.confirmation'].browse(
            [backorder_wiz_id])
        backorder_wiz.process()
        picking_backorder = sale.picking_ids.filtered(
            lambda r: r.state == 'assigned')
        picking_backorder.move_line_ids.write({'qty_done': 1})
        picking_backorder.action_done()

        wizard = self.env['sale.advance.payment.inv'].create({
            'advance_payment_method': 'delivered',
        })
        context = {
            "active_model": 'sale.order',
            "active_ids": [sale.id],
            "active_id": sale.id}
        wizard.with_context(context).create_invoices()
        invoice = sale.invoice_ids
        invoice.write({
            'journal_id': self.journal_mx.id,
        })
        invoice.post()
        customs = invoice.invoice_line_ids[0].l10n_mx_edi_customs_number
        self.assertEqual(customs, landing.l10n_mx_edi_customs_number)
        xml = invoice.l10n_mx_edi_get_xml_etree()
        namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/3'
        }
        custom_xml = xml.Conceptos.Concepto.xpath('cfdi:InformacionAduanera',
                                                  namespaces=namespaces)
        self.assertTrue(custom_xml, 'XML node not load')
        self.assertEqualXML(custom_xml[0], self.xml_expected)
