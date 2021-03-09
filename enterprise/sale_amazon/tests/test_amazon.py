# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from unittest.mock import patch, Mock

from odoo.tests import TransactionCase
from odoo.tools import mute_logger

BASE_ORDER_DATA = {
    'AmazonOrderId': {'value': '123456789'},
    'PurchaseDate': {'value': '1378-04-08T00:00:00.000Z'},
    'LastUpdateDate': {'value': '1976-08-21T07:00:00.000Z'},
    'OrderStatus': {'value': 'Unshipped'},
    'FulfillmentChannel': {'value': 'MFN'},
    'ShipServiceLevel': {'value': 'SHIPPING-CODE'},
    'ShippingAddress': {
        'City': {'value': 'OdooCity'},
        'AddressType': {'value': 'Commercial'},
        'PostalCode': {'value': '12345-1234'},
        'StateOrRegion': {'value': 'CA'},
        'Phone': {'value': '+1 234-567-8910 ext. 12345'},
        'CountryCode': {'value': 'US'},
        'Name': {'value': 'Gederic Frilson'},
        'AddressLine1': {'value': '123 RainBowMan Street'},
    },
    'OrderTotal': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'MarketplaceId': {'value': 'ATVPDKIKX0DER'},
    'BuyerEmail': {'value': 'iliketurtles@marketplace.amazon.com'},
    'BuyerName': {'value': 'Gederic Frilson'},
    'EarliestDeliveryDate': {'value': '1979-04-20T00:00:00.000Z'},
}

BASE_ITEM_DATA = {
    'OrderItemId': {'value': '123456789'},
    'SellerSKU': {'value': 'SKU'},
    'ConditionId': {'value': 'Used'},
    'ConditionSubtypeId': {'value': 'Good'},
    'Title': {'value': 'OdooBike Spare Wheel, 26x2.1, Pink, 200-Pack'},
    'QuantityOrdered': {'value': '2'},
    'ItemPrice': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '100.00'}},
    'ShippingPrice': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '12.50'}},
    'GiftWrapPrice': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '3.33'}},
    'ItemTax': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'ShippingTax': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'GiftWrapTax': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'ShippingDiscount': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'PromotionDiscount': {'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '0.00'}},
    'IsGift': {'value': 'true'},
    'GiftWrapLevel': {'value': 'WRAP-CODE'},
    'GiftMessageText': {'value': 'Hi,\nEnjoy your gift!\nFrom Gederic Frilson'},
}


class TestAmazon(TransactionCase):

    def setUp(self):

        def _get_available_marketplace_api_refs_mock(*_args, **_kwargs):
            """ Return the API ref of all marketplaces without calling MWS API. """
            return self.env['amazon.marketplace'].search([]).mapped('api_ref'), False

        super(TestAmazon, self).setUp()
        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_available_marketplace_api_refs',
                   new=_get_available_marketplace_api_refs_mock):
            self.account = self.env['amazon.account'].create({
                'name': "TestAccountName",
                **dict.fromkeys(('seller_key', 'access_key', 'secret_key'), ''),
                'base_marketplace_id': 1,
                'company_id': self.env.company.id,
            })

    def test_check_credentials_succeed(self):
        """ Test the credentials check with valid credentials. """
        with patch(
                'odoo.addons.sale_amazon.models.mws_connector.do_account_credentials_check',
                new=lambda *args, **kwargs: False):
            self.assertTrue(self.account.action_check_credentials())

    def test_update_marketplaces_no_change(self):
        """ Test the available marketplaces synchronization with no change. """
        self.marketplaces = self.env['amazon.marketplace'].search([])
        with patch(
                'odoo.addons.sale_amazon.models.amazon_account.AmazonAccount'
                '._get_available_marketplaces',
                new=lambda *args, **kwargs: (self.marketplaces, False)):
            self.account.write({
                'available_marketplace_ids': [(6, 0, self.marketplaces.ids)],
                'active_marketplace_ids': [(6, 0, self.marketplaces.ids)],
            })
            self.account.action_update_available_marketplaces()
            self.assertEqual(self.account.available_marketplace_ids.ids, self.marketplaces.ids)
            self.assertEqual(self.account.active_marketplace_ids.ids, self.marketplaces.ids)

    def test_update_marketplaces_remove(self):
        """ Test the available marketplaces synchronization with a marketplace removal. """
        self.marketplaces = self.env['amazon.marketplace'].search([], limit=2)
        with patch(
                'odoo.addons.sale_amazon.models.amazon_account.AmazonAccount'
                '._get_available_marketplaces',
                new=lambda *args, **kwargs: (self.marketplaces[:1], False)):
            self.account.write({
                'available_marketplace_ids': [(6, 0, self.marketplaces.ids)],
                'active_marketplace_ids': [(6, 0, self.marketplaces.ids)],
            })
            self.account.action_update_available_marketplaces()
            self.assertEqual(self.account.available_marketplace_ids.ids, self.marketplaces.ids[:1])
            self.assertEqual(
                self.account.active_marketplace_ids.ids, self.marketplaces.ids[:1],
                "unavailable marketplaces should be removed from the list of active marketplaces"
            )

    def test_update_marketplaces_add(self):
        """ Test the available marketplaces synchronization with a new marketplace. """
        self.marketplaces = self.env['amazon.marketplace'].search([], limit=2)
        with patch(
                'odoo.addons.sale_amazon.models.amazon_account.AmazonAccount'
                '._get_available_marketplaces',
                new=lambda *args, **kwargs: (self.marketplaces, False)):
            self.account.write({
                'available_marketplace_ids': [(6, 0, self.marketplaces.ids[:1])],
                'active_marketplace_ids': [(6, 0, self.marketplaces.ids[:1])],
            })
            self.account.action_update_available_marketplaces()
            self.assertEqual(self.account.available_marketplace_ids.ids, self.marketplaces.ids)
            self.assertEqual(
                self.account.active_marketplace_ids.ids, self.marketplaces.ids,
                "new available marketplaces should be added to the list of active marketplaces"
            )

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_full(self):
        """ Test the orders synchronization with on-the-fly creation of all required records. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            return [BASE_ORDER_DATA], datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [BASE_ITEM_DATA], None, False

        def _get_product_mock(_self, _product_code, _default_xmlid, _default_name, _default_type):
            """ Return a product created on-the-fly with the product code as internal reference. """
            _product = self.env['product.product'].create({
                'name': _default_name,
                'type': _default_type,
                'list_price': 0.0,
                'sale_ok': False,
                'purchase_ok': False,
                'default_code': _product_code,
            })
            _product.product_tmpl_id.taxes_id = False
            return _product

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock), \
             patch('odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._get_product',
                   new=_get_product_mock):
            self.account._sync_orders(auto_commit=False)
            self.assertEqual(
                self.account.last_orders_sync, datetime(2020, 1, 1),
                "the last_order_sync should be equal to the date returned by get_orders_data when "
                "the synchronization is completed")

            order = self.env['sale.order'].search([('amazon_order_ref', '=', '123456789')])
            self.assertEqual(len(order), 1, "there should have been exactly one order created")
            self.assertEqual(order.origin, 'Amazon Order 123456789')
            self.assertEqual(order.date_order, datetime(1378, 4, 8))
            self.assertEqual(order.company_id.id, self.account.company_id.id)
            self.assertEqual(order.user_id.id, self.account.user_id.id)
            self.assertEqual(order.team_id.id, self.account.team_id.id)
            self.assertEqual(order.amazon_channel, 'fbm')

            order_lines = self.env['sale.order.line'].search([('order_id', '=', order.id)])
            self.assertEqual(
                len(order_lines), 4, "there should have been four order lines created: one for "
                                     "the product, one for the gift wrapping charges, one (note)"
                                     "for the gift message and one for the shipping")
            product_line = order_lines.filtered(lambda l: l.product_id.default_code == 'SKU')
            self.assertEqual(
                product_line.price_unit, 50., "the unitary price should be the quotient of the "
                                              "item price divided by the quantity")
            self.assertEqual(product_line.product_uom_qty, 2.)
            self.assertEqual(product_line.amazon_item_ref, '123456789')
            self.assertTrue(product_line.amazon_offer_id)

            shipping_line = order_lines.filtered(
                lambda l: l.product_id.default_code == 'SHIPPING-CODE')
            self.assertEqual(shipping_line.price_unit, 12.5)
            self.assertEqual(shipping_line.product_uom_qty, 1.)
            self.assertFalse(shipping_line.amazon_item_ref)
            self.assertFalse(shipping_line.amazon_offer_id)

            gift_wrapping_line = order_lines.filtered(
                lambda l: l.product_id.default_code == 'WRAP-CODE')
            self.assertEqual(gift_wrapping_line.price_unit, 3.33)
            self.assertEqual(gift_wrapping_line.product_uom_qty, 1.)
            self.assertFalse(gift_wrapping_line.amazon_item_ref)
            self.assertFalse(gift_wrapping_line.amazon_offer_id)

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_partial(self):
        """ Test the orders synchronization interruption with API throttling. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a two-order batch of test order data without calling MWS API. """
            return [BASE_ORDER_DATA, dict(BASE_ORDER_DATA, AmazonOrderId={'value': '987654321'})],\
                   datetime(2020, 1, 1), None, False

        def _get_items_data_mock(_orders_api, _amazon_order_ref, _error_message, _next_token=None):
            """ Return with rate_limit_reached set to True for the second order. """
            return [BASE_ITEM_DATA], None, _amazon_order_ref == '987654321'

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock):
            self.account._sync_orders(auto_commit=False)
            self.assertEqual(
                self.account.last_orders_sync, datetime(1976, 8, 21, 7),
                "the last_order_sync should be equal to the LastUpdateDate of the last fully"
                "synchronized order if no all orders could be synchronized")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_fail(self):
        """ Test the orders synchronization cancellation with API throttling. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return with rate_limit_reached set to True. """
            return [], datetime(2020, 1, 1), None, True

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock):
            last_order_sync_copy = self.account.last_orders_sync
            self.account._sync_orders(auto_commit=False)
            self.assertEqual(
                self.account.last_orders_sync, last_order_sync_copy,
                "the last_order_sync should be not have been modified if the rate limit of "
                "ListOrders operation was reached when synchronizing the first batch")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_abort(self):
        """ Test the orders synchronization cancellation with no active marketplace. """
        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None):
            last_order_sync_copy = self.account.last_orders_sync
            self.account.active_marketplace_ids = False
            self.account._sync_orders(auto_commit=False)
            self.assertEqual(
                self.account.last_orders_sync, last_order_sync_copy,
                "the last_order_sync should be not have been modified if there is no active"
                "marketplace selected for the account")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_fba(self):
        """ Test the orders synchronization with Fulfillment By Amazon. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            return [dict(BASE_ORDER_DATA, FulfillmentChannel={'value': 'AFN'},
                         OrderStatus={'value': 'Shipped'})], datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [BASE_ITEM_DATA], None, False

        def _get_product_mock(_self, _product_code, _default_xmlid, _default_name, _default_type):
            """ Return a product created on-the-fly with the product code as internal reference. """
            _product = self.env['product.product'].create({
                'name': _default_name,
                'type': _default_type,
                'list_price': 0.0,
                'sale_ok': False,
                'purchase_ok': False,
                'default_code': _product_code,
            })
            _product.product_tmpl_id.taxes_id = False
            return _product

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock), \
             patch('odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._get_product',
                   new=_get_product_mock):
            self.account._sync_orders(auto_commit=False)
            order = self.env['sale.order'].search([('amazon_order_ref', '=', '123456789')])
            self.assertEqual(order.amazon_channel, 'fba')
            picking = self.env['stock.picking'].search([('sale_id', '=', order.id)])
            self.assertEqual(len(picking), 0, "FBA orders should generate no picking")
            products = order.order_line.mapped('product_id').filtered(lambda p: p.type != 'service')
            moves = self.env['stock.move'].search([('product_id', 'in', products.ids)])
            self.assertEqual(len(moves), len(products), "FBA orders should generate one stock move "
                                                        "per product that is not a service")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_europe(self):
        """ Test the orders synchronization with a European marketplace. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            return [dict(BASE_ORDER_DATA, MarketplaceId={'value': 'A13V1IB3VIYZZH'})],\
                   datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [dict(
                BASE_ITEM_DATA,
                ItemTax={'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '20.00'}},
                ShippingTax={'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '2.50'}},
                GiftWrapTax={'CurrencyCode': {'value': 'USD'}, 'Amount': {'value': '1.33'}},
                QuantityOrdered={'value': '1'})], None, False

        def _recompute_subtotal(_self, _subtotal, _tax_amount, _taxes, _currency, _fiscal_pos=None):
            """ Return the subtotal without recomputing it. """
            return _subtotal

        def _get_product_mock(_self, _product_code, _default_xmlid, _default_name, _default_type):
            """ Return a product created on-the-fly with the product code as internal reference. """
            _product = self.env['product.product'].create({
                'name': _default_name,
                'type': _default_type,
                'list_price': 0.0,
                'sale_ok': False,
                'purchase_ok': False,
                'default_code': _product_code,
            })
            _product.product_tmpl_id.taxes_id = False
            return _product

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock), \
             patch('odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._recompute_subtotal',
                   new=_recompute_subtotal), \
             patch('odoo.addons.sale_amazon.models.amazon_account.AmazonAccount._get_product',
                   new=_get_product_mock):
            self.account._sync_orders(auto_commit=False)

            order_lines = self.env['sale.order.line'].search(
                [('order_id.amazon_order_ref', '=', '123456789')])
            product_line = order_lines.filtered(lambda l: l.product_id.default_code == 'SKU')
            shipping_line = order_lines.filtered(
                lambda l: l.product_id.default_code == 'SHIPPING-CODE')
            gift_wrapping_line = order_lines.filtered(
                lambda l: l.product_id.default_code == 'WRAP-CODE')
            self.assertEqual(
                product_line.price_unit, 80,  # 100 - 20
                "tax amount should be deducted from the item price for European marketplaces")
            self.assertEqual(
                shipping_line.price_unit, 10,  # 12.50 - 2.50
                "tax amount should be deducted from the shipping price for European marketplaces")
            self.assertEqual(
                gift_wrapping_line.price_unit, 2,  # 3.33 - 1.33
                "tax amount should be deducted from the gift wrap price for European marketplaces")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    def test_sync_orders_cancel(self):
        """ Test the orders synchronization with cancellation from Amazon. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            _order_status = 'Unshipped' if not self.order_created else 'Canceled'
            return [dict(BASE_ORDER_DATA, OrderStatus={'value': _order_status})], \
                   datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [BASE_ITEM_DATA], None, False

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock):
            self.order_created = False
            self.account._sync_orders(auto_commit=False)
            self.order_created = True
            self.account._sync_orders(auto_commit=False)
            order = self.env['sale.order'].search([('amazon_order_ref', '=', '123456789')])
            self.assertEqual(
                order.state, 'cancel', "cancellation of orders should be synchronized from Amazon")

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    @mute_logger('odoo.addons.sale_amazon.models.sale')
    def test_sync_cancellations(self):
        """ Test the orders cancellation synchronization. """
        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            return [BASE_ORDER_DATA], datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [BASE_ITEM_DATA], None, False

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.submit_feed',
                   new=Mock(return_value=(0, False))) as mock:
            self.account._sync_orders(auto_commit=False)
            order = self.env['sale.order'].search([('amazon_order_ref', '=', '123456789')])
            order.action_cancel()
            self.assertTrue(order.amazon_cancellation_pending)
            order._sync_cancellations(account_ids=(self.account.id,))
            self.assertEqual(mock.call_count, 1, "an order acknowledgement feed should be sent to "
                                                 "Amazon for each canceled order")
            self.assertFalse(order.amazon_cancellation_pending)

    @mute_logger('odoo.addons.sale_amazon.models.amazon_account')
    @mute_logger('odoo.addons.sale_amazon.models.stock_picking')
    def test_sync_pickings(self):
        """ Test the pickings confirmation synchronization. """

        def _get_orders_data_mock(*_args, **_kwargs):
            """ Return a one-order batch of test order data without calling MWS API. """
            return [BASE_ORDER_DATA], datetime(2020, 1, 1), None, False

        def _get_items_data_mock(*_args, **_kwargs):
            """ Return a one-item batch of test order line data without calling MWS API. """
            return [BASE_ITEM_DATA], None, False

        with patch('odoo.addons.sale_amazon.models.mws_connector.get_api_connector',
                   new=lambda *args, **kwargs: None), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_orders_data',
                   new=_get_orders_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.get_items_data',
                   new=_get_items_data_mock), \
             patch('odoo.addons.sale_amazon.models.mws_connector.submit_feed',
                   new=Mock(return_value=(0, False))) as mock:
            self.account._sync_orders(auto_commit=False)
            order = self.env['sale.order'].search([('amazon_order_ref', '=', '123456789')])
            picking = self.env['stock.picking'].search([('sale_id', '=', order.id)])
            self.assertEqual(len(picking), 1, "FBM orders should generate exactly one picking")
            picking.action_done()
            self.assertTrue(picking.amazon_sync_pending)
            picking._sync_pickings(account_ids=(self.account.id,))
            self.assertEqual(mock.call_count, 1, "an order fulfillment feed should be sent to "
                                                 "Amazon for each confirmed picking")
            self.assertFalse(picking.amazon_sync_pending)
    
    def test_get_product_search(self):
        """ Test the product search based on the internal reference. """
        self.env['product.product'].create({
            'name': "Test Name",
            'type': 'consu',
            'default_code': 'TEST_CODE',
        })
        self.assertTrue(self.account._get_product('TEST_CODE', None, None, None))

    def test_get_product_use_fallback(self):
        """ Test the product search failure with use of the fallback. """
        default_product = self.env['product.product'].create({
            'name': "Default Name",
            'type': 'consu',
        })
        self.env['ir.model.data'].create({
            'module': 'sale_amazon',
            'name': 'test_xmlid',
            'model': 'product.product',
            'res_id': default_product.id,
        })
        self.assertTrue(self.account._get_product('INCORRECT_CODE', 'test_xmlid', None, None))

    def test_get_product_regen_fallback(self):
        """ Test the product search failure with regeneration of the fallback. """
        default_product = self.env['product.product'].create({
            'name': "Default Name",
            'type': 'consu',
        })
        self.env['ir.model.data'].create({
            'module': 'sale_amazon',
            'name': 'test_xmlid',
            'model': 'product.product',
            'res_id': default_product.id,
        })
        default_product.unlink()  # Simulate deletion of the default product added with data
        product = self.account._get_product('INCORRECT_CODE', 'test_xmlid', 'Default Name', 'consu')
        self.assertEqual(product.name, 'Default Name')
        self.assertEqual(product.type, 'consu')
        self.assertEqual(product.list_price, 0.)
        self.assertFalse(product.sale_ok)
        self.assertFalse(product.purchase_ok)

    def test_get_product_no_fallback(self):
        """ Test the product search failure without regeneration of the fallback. """
        self.assertFalse(self.account._get_product(
            'INCORRECT_CODE', 'test_xmlid', 'Default Name', 'consu', fallback=False))
        self.assertFalse(self.env.ref('sale_amazon.test_xmlid', raise_if_not_found=False))

    def test_get_pricelist_search(self):
        """ Test the pricelist search. """
        currency = self.env['res.currency'].create({
            'name': 'TEST',
            'symbol': 'T',
        })
        self.env['product.pricelist'].create({
            'name': 'Amazon Pricelist %s' % currency.name,
            'active': False,
            'currency_id': currency.id,
        })
        pricelists_count = self.env['product.pricelist'].with_context(
            active_test=False).search_count([])
        self.assertTrue(self.account._get_pricelist(currency))
        self.assertEqual(self.env['product.pricelist'].with_context(
            active_test=False).search_count([]), pricelists_count)

    def test_get_pricelist_creation(self):
        """ Test the pricelist creation. """
        currency = self.env['res.currency'].create({
            'name': 'TEST',
            'symbol': 'T',
        })
        pricelists_count = self.env['product.pricelist'].with_context(
            active_test=False).search_count([])
        pricelist = self.account._get_pricelist(currency)
        self.assertEqual(self.env['product.pricelist'].with_context(
            active_test=False).search_count([]), pricelists_count + 1)
        self.assertFalse(pricelist.active)
        self.assertEqual(pricelist.currency_id.id, currency.id)

    def test_get_partners_no_creation_same_partners(self):
        """ Test the partners search with contact as delivery. """
        country_id = self.env['res.country'].search([('code', '=', 'US')], limit=1).id
        self.env['res.partner'].create({
            'name': 'Gederic Frilson',
            'is_company': True,
            'street': '123 RainBowMan Street',
            'zip': '12345-1234',
            'city': 'OdooCity',
            'country_id': country_id,
            'state_id': self.env['res.country.state'].search(
                [('country_id', '=', country_id), ('code', '=', 'CA')], limit=1).id,
            'phone': '+1 234-567-8910 ext. 12345',
            'customer_rank': 1,
            'company_id': self.account.company_id.id,
            'amazon_email': 'iliketurtles@marketplace.amazon.com',
        })
        contacts_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(BASE_ORDER_DATA, '123456789')
        self.assertEqual(self.env['res.partner'].search_count([]), contacts_count)
        self.assertEqual(contact.id, delivery.id)
        self.assertEqual(contact.type, 'contact')
        self.assertEqual(contact.amazon_email, 'iliketurtles@marketplace.amazon.com')

    def test_get_partners_no_creation_different_partners(self):
        """ Test the partners search with different partners for contact and delivery. """
        country_id = self.env['res.country'].search([('code', '=', 'US')], limit=1).id
        new_partner_vals = {
            'is_company': True,
            'street': '123 RainBowMan Street',
            'zip': '12345-1234',
            'city': 'OdooCity',
            'country_id': country_id,
            'state_id': self.env['res.country.state'].search(
                [('country_id', '=', country_id), ('code', '=', 'CA')], limit=1).id,
            'phone': '+1 234-567-8910 ext. 12345',
            'customer_rank': 1,
            'company_id': self.account.company_id.id,
            'amazon_email': 'iliketurtles@marketplace.amazon.com',
        }
        contact = self.env['res.partner'].create(dict(new_partner_vals, name='Gederic Frilson'))
        self.env['res.partner'].create(
            dict(new_partner_vals, name='Gederic Frilson Delivery', type='delivery',
                 parent_id=contact.id))
        partners_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(
            dict(BASE_ORDER_DATA, ShippingAddress=dict(
                BASE_ORDER_DATA['ShippingAddress'], Name={'value': 'Gederic Frilson Delivery'})),
            '123456789')
        self.assertEqual(self.env['res.partner'].search_count([]), partners_count)
        self.assertNotEqual(contact.id, delivery.id)
        self.assertEqual(delivery.type, 'delivery')
        self.assertEqual(delivery.parent_id.id, contact.id)
        self.assertEqual(contact.amazon_email, delivery.amazon_email)

    def test_get_partners_creation_delivery(self):
        """ Test the partners search with creation of the delivery. """
        self.env['res.partner'].create({
            'name': 'Gederic Frilson',
            'company_id': self.account.company_id.id,
            'amazon_email': 'iliketurtles@marketplace.amazon.com',
        })
        partners_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(
            dict(BASE_ORDER_DATA, ShippingAddress=dict(
                BASE_ORDER_DATA['ShippingAddress'], Name={'value': 'Gederic Frilson Delivery'})),
            '123456789'
        )
        self.assertEqual(self.env['res.partner'].search_count([]), partners_count + 1,
                         "a delivery partner should be created when a field of the address is "
                         "different from that of the contact")
        self.assertNotEqual(contact.id, delivery.id)
        self.assertEqual(delivery.type, 'delivery')
        self.assertEqual(delivery.parent_id.id, contact.id)
        self.assertEqual(delivery.company_id.id, self.account.company_id.id)
        self.assertEqual(contact.amazon_email, delivery.amazon_email)

    def test_get_partners_creation_contact(self):
        """ Test the partners search with creation of the contact. """
        partners_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(BASE_ORDER_DATA, '123456789')
        self.assertEqual(self.env['res.partner'].search_count([]), partners_count + 1,
                         "no delivery partner should be created when the contact is not found and "
                         "the name on the order is the same as that of the address")
        self.assertEqual(contact.id, delivery.id)
        self.assertEqual(contact.name, 'Gederic Frilson')
        self.assertEqual(contact.type, 'contact')
        self.assertTrue(contact.is_company)
        self.assertEqual(contact.street, '123 RainBowMan Street')
        self.assertFalse(contact.street2)
        self.assertEqual(contact.zip, '12345-1234')
        self.assertEqual(contact.city, 'OdooCity')
        self.assertEqual(contact.country_id.code, 'US')
        self.assertEqual(contact.state_id.code, 'CA')
        self.assertEqual(contact.phone, '+1 234-567-8910 ext. 12345')
        self.assertEqual(contact.customer_rank, 1)
        self.assertEqual(contact.company_id.id, self.account.company_id.id)
        self.assertEqual(contact.amazon_email, 'iliketurtles@marketplace.amazon.com')

    def test_get_partners_creation_contact_delivery(self):
        """ Test the partners search with creation of the contact and delivery. """
        partners_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(
            dict(BASE_ORDER_DATA, ShippingAddress=dict(
                BASE_ORDER_DATA['ShippingAddress'], Name={'value': 'Gederic Frilson Delivery'})),
            '123456789')
        self.assertEqual(self.env['res.partner'].search_count([]), partners_count + 2,
                         "a contact partner and a delivery partner should be created when the "
                         "contact is not found and the name on the order is different from that"
                         "of the address")
        self.assertNotEqual(contact.id, delivery.id)
        self.assertEqual(contact.type, 'contact')
        self.assertEqual(delivery.type, 'delivery')
        self.assertEqual(delivery.parent_id.id, contact.id)
        self.assertEqual(contact.company_id.id, delivery.company_id.id)
        self.assertEqual(contact.amazon_email, delivery.amazon_email)

    def test_get_partners_anonymized_info(self):
        """ Test the partners search with creation of an anonymized contact. """
        partners_count = self.env['res.partner'].search_count([])
        contact, delivery = self.account._get_partners(
            dict(BASE_ORDER_DATA, ShippingAddress=dict(
                BASE_ORDER_DATA['ShippingAddress'], Name={'value': None})),
            '123456789')
        self.assertEqual(self.env['res.partner'].search_count([]), partners_count + 1,
                         "a contact partner should be created regardless of whether another "
                         "contact for the same customer exists when at least one personally"
                         "identifiable information is missing")
        self.assertEqual(contact.id, delivery.id)
        self.assertEqual(contact.type, 'contact')
        self.assertFalse(contact.street)
        self.assertFalse(contact.street2)
        self.assertFalse(contact.phone)
        self.assertEqual(contact.customer_rank, 0)
        self.assertEqual(contact.company_id.id, self.account.company_id.id)
        self.assertFalse(contact.amazon_email)

    def test_get_partners_arbitrary_fields(self):
        """ Test the partners search with all PII filled but in arbitrary fields. """
        contact, _delivery = self.account._get_partners(dict(
            BASE_ORDER_DATA,
            ShippingAddress=dict(
                BASE_ORDER_DATA['ShippingAddress'],
                AddressLine1={'value': None},
                AddressLine2={'value': '123 RainBowMan Street'})
        ), '123456789')
        self.assertFalse(contact.street)
        self.assertTrue(contact.street2)
        self.assertTrue(contact.phone)
        self.assertTrue(contact.customer_rank)
        self.assertTrue(contact.amazon_email)
    
    def test_get_amazon_offer_search(self):
        """ Test the offer search. """
        marketplace = self.env['amazon.marketplace'].search([('api_ref', '=', 'ATVPDKIKX0DER')])
        self.env['amazon.offer'].create({
            'account_id': self.account.id,
            'marketplace_id': marketplace.id,
            'product_id': self.account._get_product(None, 'default_product', None, None).id,
            'sku': 'SKU',
        })
        offers_count = self.env['amazon.offer'].search_count([])
        self.assertTrue(self.account._get_offer(BASE_ORDER_DATA, 'SKU'))
        self.assertEqual(self.env['amazon.offer'].search_count([]), offers_count)

    def test_get_amazon_offer_creation(self):
        """ Test the offer creation. """
        offers_count = self.env['amazon.offer'].search_count([])
        offer = self.account._get_offer(BASE_ORDER_DATA, 'SKU')
        self.assertEqual(self.env['amazon.offer'].search_count([]), offers_count + 1)
        self.assertEqual(offer.account_id.id, self.account.id)
        self.assertEqual(offer.company_id.id, self.account.company_id.id)
        self.assertEqual(offer.marketplace_id.api_ref, 'ATVPDKIKX0DER')
        self.assertEqual(offer.sku, 'SKU')
