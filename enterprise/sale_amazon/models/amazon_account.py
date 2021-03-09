# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from . import mws_connector as mwsc
from odoo import api, exceptions, fields, models, _
from odoo.osv import expression

from odoo.addons.sale_amazon.lib import mws

_logger = logging.getLogger(__name__)

# True if the tax amount is included in the sales price
MARKETPLACES_WITH_TAX_INCLUDED = {
    'A2EUQ1WTGCTBG2': False,  # amazon.ca
    'A1AM78C64UM0Y8': False,  # amazon.com.mx
    'ATVPDKIKX0DER': False,   # amazon.com
    'A1PA6795UKMFR9': True,   # amazon.de
    'A1RKKUPIHCS9HS': True,   # amazon.es
    'A13V1IB3VIYZZH': True,   # amazon.fr
    'APJ6JRA9NG5V4': True,    # amazon.it
    'A1F83G8C2ARO7P': True,   # amazon.co.uk
    'A1805IZSGTT6HS': True,   # amazon.nl
}


class AmazonAccount(models.Model):
    _name = 'amazon.account'
    _description = "Amazon Account"
    _check_company_auto = True
    
    name = fields.Char("Name", help="A user-defined name for the account", required=True)

    base_marketplace_id = fields.Many2one(
        'amazon.marketplace', "Sign-up Marketplace",
        help="The original sign-up marketplace of this account. Used for authentication only.",
        required=True
    )
    seller_key = fields.Char(
        "Seller ID", help="The Merchant ID of the Amazon Seller Central account", required=True,
        groups="base.group_system")
    access_key = fields.Char(
        "Access Key", help="The Access Key ID of the Amazon Seller Central account", required=True,
        groups="base.group_system")
    secret_key = fields.Char(
        "Secret Key", help="The Secret Key of the Amazon Seller Central account", required=True,
        groups="base.group_system")
    
    available_marketplace_ids = fields.Many2many(
        'amazon.marketplace', 'amazon_account_marketplace_rel', string="Available Marketplaces",
        help="The marketplaces this account has access to", copy=False)
    active_marketplace_ids = fields.Many2many(
        'amazon.marketplace', 'amazon_account_active_marketplace_rel', string="Sync Marketplaces",
        help="The marketplaces this account sells on",
        domain="[('id', 'in', available_marketplace_ids)]", copy=False)
    
    user_id = fields.Many2one(
        'res.users', "Salesperson", default=lambda self: self.env.user, check_company=True)
    team_id = fields.Many2one(
        'crm.team', "Sales Team", help="The Sales Team assigned to Amazon orders for reporting",
        check_company=True)
    company_id = fields.Many2one(
        'res.company', "Company", default=lambda self: self.env.company, required=True)
    location_id = fields.Many2one(
        'stock.location', "Stock Location",
        help="The location of the stock managed by Amazon under the Amazon Fulfillment program",
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]", check_company=True)
    active = fields.Boolean(
        "Active", help="If made inactive, this account will no longer be synchronized with Amazon",
        default=True, required=True)
    last_orders_sync = fields.Datetime(
        help="The last synchronization date for orders placed on this account. Orders whose status "
             "has not changed since this date will not be created nor updated in Odoo.",
        default=fields.Datetime.now, required=True)
    
    order_count = fields.Integer(compute='_compute_order_count')
    offer_count = fields.Integer(compute='_compute_offer_count')
    is_follow_up_displayed = fields.Boolean(compute='_compute_is_follow_up_displayed')

    def _compute_order_count(self):
        # Not optimized for large sets of accounts because of the auto-join on order_line in
        # sale.order leading to incorrect results when search_count is used to perform the count.
        # This has trivial impact on performance since the field is rarely computed and the set
        # of accounts will always be of minimal size.
        for account in self:
            account.order_count = len(self.env['sale.order.line'].read_group(
                [('amazon_offer_id.account_id', '=', account.id)], ['order_id'], ['order_id']))
    
    def _compute_offer_count(self):
        offers_data = self.env['amazon.offer'].read_group(
            [('account_id', 'in', self.ids)], ['account_id'], ['account_id'])
        accounts_data = {offer_data['account_id'][0]: offer_data['account_id_count']
                         for offer_data in offers_data}
        for account in self:
            account.offer_count = accounts_data.get(account.id, 0)

    @api.depends('company_id')  # Trick to compute the field on new records
    def _compute_is_follow_up_displayed(self):
        """ Return True is the page Order Follow-up should be displayed in the view form. """
        for account in self:
            account.is_follow_up_displayed = account._origin.id or self.user_has_groups(
                'base.group_multi_company,base.group_no_one')

    @api.onchange('available_marketplace_ids')
    def _onchange_available_marketplace_ids(self):
        """ Remove active marketplaces that are no longer available. """
        for account in self:
            account.active_marketplace_ids &= account.available_marketplace_ids
    
    @api.onchange('last_orders_sync')
    def _onchange_last_orders_sync(self):
        """ Display a warning about the possible consequences of modifying the last orders sync. """
        self.ensure_one()
        if self._origin.id:
            return {
                'warning': {
                    'title': _("Warning"),
                    'message': _("If the date is set in the past, orders placed on this Amazon "
                                 "Account before the first synchronization of the module might be "
                                 "synchronized with Odoo.\n"
                                 "If the date is set in the future, orders placed on this Amazon "
                                 "Account between the previous and the new date will not be "
                                 "synchronized with Odoo.")
                }
            }

    @api.constrains('active_marketplace_ids')
    def _check_actives_subset_of_availables(self):
        for account in self:
            if account.active_marketplace_ids.filtered(
                    lambda m: m.id not in account.available_marketplace_ids.ids):
                raise exceptions.ValidationError(_("Only available marketplaces can be selected"))

    @api.model
    def create(self, vals):
        # Fetch available marketplaces and set them all as active marketplaces
        # In the process, check the credentials and raise if they are incorrect
        base_marketplace = self.env['amazon.marketplace'].browse([vals['base_marketplace_id']])
        api_keys = {field_name: vals.get(field_name)
                    for field_name in self._get_api_key_field_names()}
        available_marketplaces, rate_limit_reached = self._get_available_marketplaces(
            base_marketplace, True, **api_keys)
        vals.update(dict.fromkeys(
            ['available_marketplace_ids', 'active_marketplace_ids'],
            [(6, 0, available_marketplaces.ids)])
        )

        # Find or create the location of the Amazon warehouse to be associated with this account
        location = self.env['stock.location'].search(
            [('amazon_location', '=', True), '|', ('company_id', '=', False),
             ('company_id', '=', vals.get('company_id'))], limit=1)
        if not location:
            parent_location_data = self.env['stock.warehouse'].search_read(
                [('company_id', '=', vals.get('company_id'))], ['view_location_id'], limit=1)
            location = self.env['stock.location'].create({
                'name': 'Amazon',
                'usage': 'internal',
                'location_id': parent_location_data[0]['view_location_id'][0],
                'company_id': vals.get('company_id'),
                'amazon_location': True,
            })
        vals.update({'location_id': location.id})

        # Find or create the sales team to be associated with this account
        team = self.env['crm.team'].search(
            [('amazon_team', '=', True), '|', ('company_id', '=', False),
             ('company_id', '=', vals.get('company_id'))], limit=1)
        if not team:
            team = self.env['crm.team'].create({
                'name': 'Amazon',
                'company_id': vals.get('company_id'),
                'amazon_team': True,
            })
        vals.update({'team_id': team.id})

        return super(AmazonAccount, self).create(vals)

    def write(self, vals):
        api_keys = {field_name: vals.get(field_name)
                    for field_name in self._get_api_key_field_names()}
        if set(vals).intersection(api_keys):
            self.action_check_credentials(**api_keys)
        return super(AmazonAccount, self).write(vals)
    
    @api.model
    def _get_api_key_field_names(self):
        """ Return a tuple of field names used to store API keys.

        The primary use of this method is to allow other modules to inherit it and redefine which
        fields store the keys used for the authentication to the MWS API. If another module were to
        implement an authentication flow requiring a different set of keys than that returned here,
        it would need to override this method and return the relevant field names instead.

        Most of the time, this method should be used to retrieve the values of the fields storing
        the authentication keys and allow to pass them as keyword arguments to the
        `_build_get_api_connector_kwargs` method.

        Note: Excluding one of the returned field names will disable the check for valid credentials
              currently set for that field on create and on write.
        """
        return 'seller_key', 'access_key', 'secret_key'
    
    def toggle_active(self):
        self.filtered(lambda a: not a.active).action_check_credentials()
        super(AmazonAccount, self).toggle_active()

    def action_view_offers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Offers'),
            'res_model': 'amazon.offer',
            'view_mode': 'tree',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }

    def action_view_orders(self):
        self.ensure_one()
        order_lines = self.env['sale.order.line'].search(
            [('amazon_offer_id', '!=', False), ('amazon_offer_id.account_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Orders'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', order_lines.order_id.ids)],
            'context': {'create': False},
        }
    
    def action_check_credentials(self, **api_keys):
        """ Check the credentials validity. Use that of the account if not included in kwargs. """
        self.check_access_rights('write')
        for account in self:
            error_message = _("An error was encountered when preparing the connection to Amazon.")
            sellers_api = mwsc.get_api_connector(
                mws.Sellers,
                api_keys.get('access_key') or account.access_key,
                api_keys.get('secret_key') or account.secret_key,
                api_keys.get('seller_key') or account.seller_key,
                account.base_marketplace_id.code,
                error_message,
                **self._build_get_api_connector_kwargs(**api_keys))
            error_message = _("The authentication to the Amazon Marketplace Web Service failed. "
                              "Please verify your credentials.")
            if mwsc.do_account_credentials_check(sellers_api, error_message):
                _logger.warning("rate limit reached when checking credentials for "
                                "amazon.account with id %s" % account.id)
                raise exceptions.UserError(_("The communication with Amazon is overloaded, "
                                             "please try again later."))
        return {
            'effect': {
                'type': 'rainbow_man',
                'message': _("Everything is correctly set up !"),
            }
        }

    def action_update_available_marketplaces(self):
        """ Update available marketplaces and assign new ones to the account. """
        for account in self:
            account_data = account.read(self._get_api_key_field_names())[0]
            api_keys = {field_name: account_data.get(field_name)
                        for field_name in self._get_api_key_field_names()}
            available_marketplaces, rate_limit_reached = self._get_available_marketplaces(
                account.base_marketplace_id, False, **api_keys)
            if not rate_limit_reached:
                new_marketplaces = available_marketplaces - account.available_marketplace_ids
                account.write({'available_marketplace_ids': [(6, 0, available_marketplaces.ids)]})
                account._onchange_available_marketplace_ids()
                account.active_marketplace_ids += new_marketplaces
        return {
            'effect': {
                'type': 'rainbow_man',
                'message': _("Successfully updated the marketplaces available to this account !"),
            }
        }

    def action_sync_orders(self):
        self._sync_orders()

    def action_sync_pickings(self):
        self.env['stock.picking']._sync_pickings(tuple(self.ids))

    def action_sync_cancellations(self):
        self.env['sale.order']._sync_cancellations(tuple(self.ids))

    def _sync_orders(self, auto_commit=True):
        """
        Sync the orders of the accounts and create missing ones. Called by cron.
        If called on an empty recordset, the orders of all accounts are synchronized instead.
        :param auto_commit: whether committing to db after each order sync should be enabled
        """
        for account in self or self.search([]):
            account = account[0]  # Avoid prefetching after each cache invalidation
            marketplace_api_refs = [marketplace.api_ref
                                    for marketplace in account.active_marketplace_ids]
            if not marketplace_api_refs:
                continue  # Synchronization of orders requires at least one marketplace
            error_message = _("An error was encountered when preparing the connection to Amazon.")
            account_data = account.read(self._get_api_key_field_names())[0]
            api_keys = {field_name: account_data.get(field_name)
                        for field_name in self._get_api_key_field_names()}
            orders_api = mwsc.get_api_connector(
                mws.Orders,
                account.access_key,
                account.secret_key,
                account.seller_key,
                account.base_marketplace_id.code,
                error_message,
                **self._build_get_api_connector_kwargs(**api_keys))
    
            # The last sync date of the account is used as a lower bound on the orders' last status
            # update date. The upper bound is determined by the API and disclosed in the response.
            updated_after = account.last_orders_sync  # Lower bound
            updated_before = None  # Upper bound
    
            # Orders are fetched one batch (of up to 100 orders) at a time.
            # If the fetched batch is full, a next_token is generated and can be used
            # to fetch the next batch with the same query params as the previous one.
            has_next, next_token = True, None
    
            # Because the rate limits of 'ListOrders' and 'ListOrdersByNextToken' operations are
            # shared, it is not possible to anticipate query throttling by the API.
            # If the rate limit is reached, the lower bound of the next query is set to the
            # last update date of the last processed order.
            rate_limit_reached = False
            error_message = _("An error was encountered when synchronizing Amazon orders.")
            while has_next and not rate_limit_reached:
                orders_data_batch, updated_before, next_token, rate_limit_reached = mwsc. \
                    get_orders_data(orders_api, marketplace_api_refs,
                                    updated_after.isoformat(sep='T'), error_message, next_token)
                has_next = bool(next_token)
                if rate_limit_reached:
                    _logger.warning("rate limit reached when synchronizing orders of "
                                    "amazon.account with id %s" % account.id)
                    continue  # The batch is empty, there is no order items to synchronize
        
                # For each order, the items are fetched separately and a sale order is created.
                # If the rate limit is reached when fetching the order items, the current order
                # and all remaining orders are postponed to the next cron run.
                # All changes are committed before moving to the next order(s) to foresee cron kill.
                for order_data in orders_data_batch:
                    if not rate_limit_reached:
                        amazon_order_ref, rate_limit_reached, sync_failure = account._process_order(
                                order_data, orders_api)
                        if sync_failure:
                            account._handle_order_sync_failure(amazon_order_ref)
                            self.env.cr.rollback()
                            continue
                        if rate_limit_reached:
                            _logger.warning(
                                "rate limit reached when synchronizing items of Amazon order %s "
                                "for amazon.account with id %s" % (amazon_order_ref, account.id))
                            continue
                        account.last_orders_sync = mwsc.get_date_value(order_data, 'LastUpdateDate')
                        if auto_commit:
                            self.env.cr.commit()
            if not rate_limit_reached:
                # To always use a lower bound anterior to the upper bound, the lower bound of the
                # next request is set the current upper bound, corresponding either to:
                # 1. the current lower bound if the synchronization failed.
                # 2. the status update of the last synchronized order if synchronization was halted.
                # 3. the upper bound of the API if the synchronization was completed.
                account.last_orders_sync = updated_before

    @api.model
    def _get_available_marketplaces(self, marketplace, raise_if_rate_limit_reached, **api_keys):
        available_marketplaces = None
        error_message = _("An error was encountered when preparing the connection to Amazon.")
        sellers_api = mwsc.get_api_connector(
            mws.Sellers,
            api_keys.get('access_key'),
            api_keys.get('secret_key'),
            api_keys.get('seller_key'),
            marketplace.code,
            error_message,
            **self._build_get_api_connector_kwargs(**api_keys))
        error_message = _("The authentication to the Amazon Marketplace Web Service failed. "
                          "Please verify your credentials.")
        available_marketplace_api_refs, rate_limit_reached = mwsc. \
            get_available_marketplace_api_refs(sellers_api, error_message)
        if rate_limit_reached:
            _logger.warning(
                "rate limit reached when updating available marketplaces for Amazon account "
                "with seller id %s" % api_keys.get('seller_key'))
            if raise_if_rate_limit_reached:
                raise exceptions.UserError(
                    _("The communication with Amazon is overloaded, please try again later."))
        else:  # Don't update marketplaces if they could not all be fetched
            domain = expression.OR([[('api_ref', 'ilike', marketplace_api_ref)]
                                    for marketplace_api_ref in available_marketplace_api_refs])
            available_marketplaces = self.env['amazon.marketplace'].search(domain)
        return available_marketplaces, rate_limit_reached

    @api.model
    def _build_get_api_connector_kwargs(self, **_api_keys):
        """ Build the kwargs passed to `mws_connector.get_api_connector`.

        The primary use of this method is to allow other modules to inherit it and redefine which
        keyword arguments are passed to the `get_api_connector` function. This is the most useful
        when the `get_api_connector` function is monkey-patched in parallel of an override of this
        method to retrieve and use accordingly the extra parameters returned by the override.

        Note: As the dict returned by this method is mostly used as the kwargs argument of the
              `get_api_connector` function which then passes it as-is to the constructor of the
              related `MWS` class, extra parameters returned by an override should either:
              - be acceptable positional parameters of the related `MWS` class,
              - or be removed from kwargs in a overwrite of the `get_api_connector` function.
        """
        return {}
    
    def _process_order(self, order_data, orders_api):
        """ Create a sale order from the data of an Amazon order. """
        self.ensure_one()
        amazon_order_ref = mwsc.get_string_value(order_data, 'AmazonOrderId')
        items_data = []
        
        # Order items are fetched one batch at a time.
        # If the fetched batch is full, a next_token is generated and can be used
        # to fetch the next batch with the same query params as the previous one.
        has_next, next_token = True, None
        
        # Because the rate limits of 'ListOrderItems' and 'ListOrderItemsByNextToken' are shared,
        # it is impossible to anticipate query throttling by the API. If the rate limit is reached,
        # the synchronization of all remaining orders is postponed to the next run.
        rate_limit_reached = False
        sync_failure = False
        error_message = _("An error was encountered when synchronizing Amazon order items.")
        while has_next and not rate_limit_reached:
            items_data_batch, next_token, rate_limit_reached = mwsc.get_items_data(
                orders_api, amazon_order_ref, error_message)
            items_data += items_data_batch
            has_next = bool(next_token)
        
        if not rate_limit_reached:
            try:
                with self.env.cr.savepoint():
                    # Create the sale order if needed and if the status is not 'Canceled'
                    order, order_found, amazon_status = self._get_order(
                        order_data, items_data, amazon_order_ref)
            except Exception as error:
                sync_failure = True
                _logger.exception(error)
            else:
                if amazon_status == 'Canceled' and order_found and order.state != 'cancel':
                    order.with_context(canceled_by_amazon=True).action_cancel()
                    _logger.info("canceled sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                elif not order_found and order:  # New order created
                    if order.amazon_channel == 'fba':
                        self._generate_stock_moves(order)
                    elif order.amazon_channel == 'fbm':
                        order.with_context(mail_notrack=True).action_done()
                    _logger.info("synchronized sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                elif order_found:  # Order already sync
                    _logger.info("ignored already sync sale.order with amazon_order_ref %s for "
                                 "amazon.account with id %s" % (amazon_order_ref, self.id))
                else:  # Combination of status and fulfillment channel not handled
                    _logger.info("ignored %s amazon order with reference %s for amazon.account "
                                 "with id %s" % (amazon_status.lower(), amazon_order_ref, self.id))
        return amazon_order_ref, rate_limit_reached, sync_failure

    def _get_order(self, order_data, items_data, amazon_order_ref):
        """ Find or create a sale order based on Amazon data. """
        self.ensure_one()
        status = mwsc.get_string_value(order_data, 'OrderStatus')
        fulfillment_channel = mwsc.get_string_value(order_data, 'FulfillmentChannel')
        
        order = self.env['sale.order'].search([('amazon_order_ref', '=', amazon_order_ref)], limit=1)
        order_found = bool(order)
        if not order_found and (
                (fulfillment_channel == 'AFN' and status == 'Shipped')
                or (fulfillment_channel == 'MFN' and status == 'Unshipped')):
            currency_code = mwsc.get_currency_value(order_data, 'OrderTotal')
            purchase_date = mwsc.get_date_value(order_data, 'PurchaseDate')
            shipping_code = mwsc.get_string_value(order_data, 'ShipServiceLevel')

            # The order is created in state 'sale' to generate a picking if fulfilled by merchant
            # and in state 'done' to generate no picking if fulfilled by Amazon
            state = 'done' if fulfillment_channel == 'AFN' else 'sale'
            shipping_product = self._get_product(
                shipping_code, 'shipping_product', 'Shipping', 'service')
            currency = self.env['res.currency'].with_context(active_test=False).search(
                [('name', '=', currency_code)], limit=1)
            pricelist = self._get_pricelist(currency)
            contact_partner, delivery_partner = self._get_partners(order_data, amazon_order_ref)
            fiscal_position_id = self.env['account.fiscal.position'].with_context(force_company=self.company_id.id).get_fiscal_position(
                contact_partner.id, delivery_partner.id)
            fiscal_position = self.env['account.fiscal.position'].browse(fiscal_position_id)
            
            order_lines_vals = self._process_order_lines(
                order_data, items_data, shipping_code, shipping_product, currency, fiscal_position)
            order = self.env['sale.order'].with_context(mail_create_nosubscribe=True).create({
                'origin': 'Amazon Order %s' % amazon_order_ref,
                'state': state,
                'date_order': purchase_date,
                'partner_id': contact_partner.id,
                'pricelist_id': pricelist.id,
                'order_line': [(0, 0, order_line_vals) for order_line_vals in order_lines_vals],
                'invoice_status': 'no',
                'partner_shipping_id': delivery_partner.id,
                'require_signature': False,
                'require_payment': False,
                'fiscal_position_id': fiscal_position_id,
                'company_id': self.company_id.id,
                'user_id': self.user_id.id,
                'team_id': self.team_id.id,
                'amazon_order_ref': amazon_order_ref,
                'amazon_channel': 'fba' if fulfillment_channel == 'AFN' else 'fbm',
            })
        return order, order_found, status

    def _process_order_lines(
            self, order_data, items_data, shipping_code, shipping_product, currency, fiscal_pos):
        """ Return a list of sale order line vals based on Amazon order items data. """
        
        def _get_order_line_vals(**kwargs):
            """ Convert and complete a dict of values to comply with fields of sale_order_line. """
            _subtotal = kwargs.get('subtotal', 0)
            _quantity = kwargs.get('quantity', 1)
            return {
                'name': kwargs.get('description', ''),
                'product_id': kwargs.get('product_id'),
                'price_unit': _subtotal / _quantity,
                'tax_id': [(6, 0, kwargs.get('tax_ids', []))],
                'product_uom_qty': _quantity,
                'discount': (kwargs.get('discount', 0) / _subtotal) * 100 if _subtotal else 0,
                'display_type': kwargs.get('display_type', False),
                'amazon_item_ref': kwargs.get('amazon_item_ref'),
                'amazon_offer_id': kwargs.get('amazon_offer_id'),
            }
        
        self.ensure_one()
        marketplace_api_ref = mwsc.get_string_value(order_data, 'MarketplaceId')
        new_order_lines_vals = []  # List of dict of values of new order lines
        for item_data in items_data:
            sku = mwsc.get_string_value(item_data, 'SellerSKU')
            main_condition = mwsc.get_string_value(item_data, 'ConditionId')
            sub_condition = mwsc.get_string_value(item_data, 'ConditionSubtypeId')
            quantity = mwsc.get_integer_value(item_data, 'QuantityOrdered')
            sales_price = mwsc.get_amount_value(item_data, 'ItemPrice')
            tax_amount = mwsc.get_amount_value(item_data, 'ItemTax')

            offer = self._get_offer(order_data, sku)
            product_taxes = offer.product_id.taxes_id.filtered(
                lambda t: t.company_id.id == self.company_id.id)
            taxes = fiscal_pos.map_tax(product_taxes) if fiscal_pos else product_taxes
            subtotal = sales_price - tax_amount if MARKETPLACES_WITH_TAX_INCLUDED.get(
                marketplace_api_ref, False) else sales_price
            subtotal = self._recompute_subtotal(subtotal, tax_amount, taxes, currency, fiscal_pos)
            
            description_template = "[%s] %s" \
                if not main_condition or main_condition.lower() == 'new' \
                else _("[%s] %s\nCondition: %s - %s")
            description_fields = (sku, mwsc.get_string_value(item_data, 'Title')) \
                if not main_condition or main_condition.lower() == 'new' \
                else (sku, mwsc.get_string_value(item_data, 'Title'), main_condition, sub_condition)
            new_order_lines_vals.append(_get_order_line_vals(
                product_id=offer.product_id.id,
                description=description_template % description_fields,
                subtotal=subtotal,
                tax_ids=taxes.ids,
                quantity=quantity,
                discount=mwsc.get_amount_value(item_data, 'PromotionDiscount'),
                amazon_item_ref=mwsc.get_string_value(item_data, 'OrderItemId'),
                amazon_offer_id=offer.id))

            if mwsc.get_string_value(item_data, 'IsGift', 'false') == 'true':
                gift_wrap_code = mwsc.get_string_value(item_data, 'GiftWrapLevel')
                gift_wrap_price = mwsc.get_amount_value(item_data, 'GiftWrapPrice')
                if gift_wrap_code and gift_wrap_price != 0:
                    gift_wrap_product = self._get_product(
                        gift_wrap_code, 'default_product', 'Amazon Sales', 'consu')
                    gift_wrap_product_taxes = gift_wrap_product.taxes_id.filtered(
                        lambda t: t.company_id.id == self.company_id.id)
                    gift_wrap_taxes = fiscal_pos.map_tax(gift_wrap_product_taxes) \
                        if fiscal_pos else gift_wrap_product_taxes
                    gift_wrap_tax_amount = mwsc.get_amount_value(item_data, 'GiftWrapTax')
                    gift_wrap_subtotal = gift_wrap_price - gift_wrap_tax_amount \
                        if MARKETPLACES_WITH_TAX_INCLUDED.get(marketplace_api_ref, False) \
                        else gift_wrap_price
                    gift_wrap_subtotal = self._recompute_subtotal(
                        gift_wrap_subtotal, gift_wrap_tax_amount, gift_wrap_taxes, currency,
                        fiscal_pos)
                    new_order_lines_vals.append(_get_order_line_vals(
                        product_id=gift_wrap_product.id,
                        description=_("[%s] Gift Wrapping Charges for %s") % (
                            gift_wrap_code, offer.product_id.name),
                        subtotal=gift_wrap_subtotal,
                        tax_ids=gift_wrap_taxes.ids))
                gift_message = mwsc.get_string_value(item_data, 'GiftMessageText')
                if gift_message:
                    new_order_lines_vals.append(_get_order_line_vals(
                        description=_("Gift message:\n%s") % gift_message,
                        display_type='line_note'))

            if shipping_code:
                shipping_price = mwsc.get_amount_value(item_data, 'ShippingPrice')

                shipping_product_taxes = shipping_product.taxes_id.filtered(
                    lambda t: t.company_id.id == self.company_id.id)
                shipping_taxes = fiscal_pos.map_tax(shipping_product_taxes) if fiscal_pos \
                    else shipping_product_taxes
                shipping_tax_amount = mwsc.get_amount_value(item_data, 'ShippingTax')
                shipping_subtotal = shipping_price - shipping_tax_amount \
                    if MARKETPLACES_WITH_TAX_INCLUDED.get(marketplace_api_ref, False) \
                    else shipping_price
                shipping_subtotal = self._recompute_subtotal(
                    shipping_subtotal, shipping_tax_amount, shipping_taxes, currency, fiscal_pos)
                new_order_lines_vals.append(_get_order_line_vals(
                    product_id=shipping_product.id,
                    description=_("[%s] Delivery Charges for %s") % (
                        shipping_code, offer.product_id.name),
                    subtotal=shipping_subtotal,
                    tax_ids=shipping_taxes.ids,
                    discount=mwsc.get_amount_value(item_data, 'ShippingDiscount')))

        return new_order_lines_vals

    def _get_product(self, product_code, default_xmlid, default_name, default_type, fallback=True):
        """
        Find a product by its internal reference with a fallback to a default product.
        :param product_code: the code of the item to match with the internal reference of a product
        :param default_xmlid: the xmlid of the default product to use as fallback
        :param default_name: the name of the default product to use as fallback
        :param default_type: the type of the default product to use as fallback
        :param fallback: whether a fallback to the default product is needed
        """
        self.ensure_one()
        product = self.env['product.product'].search(
            [('default_code', '=', product_code), '|', ('product_tmpl_id.company_id', '=', False),
             ('product_tmpl_id.company_id', '=', self.company_id.id)], limit=1)
        if not product and fallback:  # Fallback to the default product
            product = self.env.ref('sale_amazon.%s' % default_xmlid, raise_if_not_found=False)
        if not product and fallback:  # Restore the default product if it was deleted
            product = self.env['product.product']._restore_data_product(
                default_name, default_type, default_xmlid)
        return product

    def _get_pricelist(self, currency):
        """ Find or create a pricelist from the currency. """
        self.ensure_one()
        pricelist = self.env['product.pricelist'].with_context(active_test=False).search(
            [('currency_id', '=', currency.id), '|', ('company_id', '=', False),
             ('company_id', '=', self.company_id.id)], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].with_context(tracking_disable=True).create({
                'name': 'Amazon Pricelist %s' % currency.name,
                'active': False,
                'currency_id': currency.id,
            })
        return pricelist

    def _get_partners(self, order_data, amazon_order_ref):
        """ Find or create two partners of respective type contact and delivery from Amazon data. """
        self.ensure_one()
        anonymized_email = mwsc.get_string_value(order_data, 'BuyerEmail')
        buyer_name = mwsc.get_string_value(order_data, 'BuyerName')
        shipping_address_name = mwsc.get_string_value(order_data, ('ShippingAddress', 'Name'))
        street = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine1'))
        address_line2 = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine2'))
        address_line3 = mwsc.get_string_value(order_data, ('ShippingAddress', 'AddressLine3'))
        street2 = "%s %s" % (address_line2, address_line3) \
            if address_line2 or address_line3 else None
        zip_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'PostalCode'))
        city = mwsc.get_string_value(order_data, ('ShippingAddress', 'City'))
        country_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'CountryCode'))
        state_code = mwsc.get_string_value(order_data, ('ShippingAddress', 'StateOrRegion'))
        phone = mwsc.get_string_value(order_data, ('ShippingAddress', 'Phone'), None)
        is_company = mwsc.get_string_value(
            order_data, ('ShippingAddress', 'AddressType'), 'Residential') == 'Commercial'

        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        state = self.env['res.country.state'].search(
            [('country_id', '=', country.id), '|', ('code', '=', state_code),
             ('name', '=', state_code)], limit=1)
        if not state:
            state = self.env['res.country.state'].with_context(tracking_disable=True).create({
                'country_id': country.id,
                'name': state_code,
                'code': state_code
            })
        # If personal information of the customer are not provided because of API restrictions,
        # all concerned fields are left blank as well as the amazon email to avoid matching an
        # anonymized partner with the same customer if personal info are later provided again.
        anonymized_customer = not all([buyer_name, shipping_address_name, street or street2])
        new_partner_vals = {
            'street': street if not anonymized_customer else None,
            'street2': street2 if not anonymized_customer else None,
            'zip': zip_code,
            'city': city,
            'country_id': country.id,
            'state_id': state.id,
            'phone': phone if not anonymized_customer else None,
            'customer_rank': 1 if not anonymized_customer else 0,
            'company_id': self.company_id.id,
            'amazon_email': anonymized_email if not anonymized_customer else None,
        }
        
        # If personal info are not anonymized, a contact partner is created only for new customers.
        # If personal info are anonymized, a contact partner is always created to avoid matching
        # a non-anonymized partner previously created for the current customer.
        contact = self.env['res.partner'].search(
            [('amazon_email', '=', anonymized_email), ('type', '=', 'contact'),
             '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)], limit=1) \
            if not anonymized_customer else None
        if not contact:
            contact_name = buyer_name if not anonymized_customer \
                               else "Amazon Customer # %s" % amazon_order_ref
            contact = self.env['res.partner'].with_context(tracking_disable=True).create({
                'name': contact_name,
                'is_company': is_company,
                **new_partner_vals,
            })
        # The contact partner acts as delivery partner if the address is either anonymous or
        # strictly equal to that of the contact partner. If not, a delivery partner is required.
        delivery = contact if anonymized_customer \
                              or (contact.name == shipping_address_name and contact.street == street
                                  and (not contact.street2 or contact.street2 == street2)
                                  and contact.zip == zip_code and contact.city == city
                                  and contact.country_id.id == country.id
                                  and contact.state_id.id == state.id) else None
        if not delivery:
            delivery = self.env['res.partner'].search(
                [('parent_id', '=', contact.id), ('type', '=', 'delivery'),
                 ('name', '=', shipping_address_name), ('street', '=', street),
                 '|', ('street2', '=', False), ('street2', '=', street2), ('zip', '=', zip_code),
                 ('city', '=', city), ('country_id', '=', country.id), ('state_id', '=', state.id),
                 '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)], limit=1)
        if not delivery:
            delivery = self.env['res.partner'].with_context(tracking_disable=True).create({
                'name': shipping_address_name,
                'type': 'delivery',
                'parent_id': contact.id,
                **new_partner_vals,
            })
        return contact, delivery

    def _get_offer(self, order_data, sku):
        """ Find or create an amazon offer from Amazon data. """
        self.ensure_one()
        marketplace_api_ref = mwsc.get_string_value(order_data, 'MarketplaceId')
        
        offer = self.env['amazon.offer'].search(
            [('sku', '=', sku), ('account_id', '=', self.id)], limit=1)
        if not offer:
            marketplace = self.active_marketplace_ids.filtered(
                lambda m: m.api_ref == marketplace_api_ref)
            offer = self.env['amazon.offer'].with_context(tracking_disable=True).create({
                'account_id': self.id,
                'marketplace_id': marketplace.id,
                'product_id': self._get_product(sku, 'default_product', 'Amazon Sales', 'consu').id,
                'sku': sku,
            })
        # If the offer has been linked with the default product, search if another product has now
        # been assigned the current SKU as internal reference and update the offer if so.
        # This trades off a bit of performance in exchange for a more expected behavior for the
        # matching of products if one was assigned the right SKU after that the offer was created.
        elif 'sale_amazon.default_product' in offer.product_id._get_external_ids().get(
                offer.product_id.id, []):
            product = self._get_product(sku, None, None, None, fallback=False)
            if product:
                offer.product_id = product.id
        return offer

    def _recompute_subtotal(self, subtotal, tax_amount, taxes, currency, _fiscal_pos=None):
        """
        Recompute the subtotal from the tax amount and the taxes. Overridden in sale_amazon_taxcloud
        As it is not always possible to find the right tax record for a tax rate computed from the
        tax amount because of rounding errors or because of multiple taxes for a given rate, the
        taxes on the product (or those given by the fiscal position) are used instead.
        To achieve this, the subtotal is recomputed from the taxes for the total to match that of
        the order in SellerCentral. If the taxes used are not identical to that used by Amazon, the
        recomputed subtotal will differ from the original subtotal.
        :param subtotal: the original subtotal to use for the computation of the base total
        :param tax_amount: the original tax amount to use for the computation of the base total
        :param taxes: the final taxes to use for the computation of the new subtotal
        :param currency: the currency used by the rounding methods
        :param _fiscal_pos: the fiscal position only used in overrides of this method
        """
        total = subtotal + tax_amount
        taxes_res = taxes.with_context(force_price_include=True).compute_all(
            total, currency=currency)
        subtotal = taxes_res['total_excluded']
        for tax_res in taxes_res['taxes']:
            tax = self.env['account.tax'].browse(tax_res['id'])
            if tax.price_include:
                subtotal += tax_res['amount']
        return subtotal
    
    def _generate_stock_moves(self, order):
        """ Generate a stock move for each product of a sale order. """
        customers_location = self.env.ref('stock.stock_location_customers')
        for order_line in order.order_line.filtered(
                lambda l: l.product_id.type != 'service' and not l.display_type):
            stock_move = self.env['stock.move'].create({
                'name': _('Amazon move : %s') % order.name,
                'company_id': self.company_id.id,
                'product_id': order_line.product_id.id,
                'product_uom_qty': order_line.product_uom_qty,
                'product_uom': order_line.product_uom.id,
                'location_id': self.location_id.id,
                'location_dest_id': customers_location.id,
                'state': 'confirmed',
                'sale_line_id': order_line.id,
            })
            stock_move._action_assign()
            stock_move._set_quantity_done(order_line.product_uom_qty)
            stock_move._action_done()

    def _handle_order_sync_failure(self, amazon_order_ref):
        """ Send a mail to the responsibles to report an order synchronization failure. """
        _logger.exception(
            "failed to synchronize order with amazon id %s for amazon.account with "
            "id %s (seller id %s)" % (amazon_order_ref, self.id, self.seller_key))
        mail_template = self.env.ref('sale_amazon.order_sync_failure', raise_if_not_found=False)
        if not mail_template:
            _logger.warning("the mail template with xmlid sale_amazon.order_sync_failure has "
                            "been deleted.")
        else:
            responsible_emails = {user.email for user in filter(None, (
                self.user_id, self.env.ref('base.user_admin', raise_if_not_found=False)))}
            mail_template.with_context(**{
                'email_to': ','.join(responsible_emails),
                'amazon_order_ref': amazon_order_ref,
            }).send_mail(self.env.user.id)
            _logger.info("sent order synchronization failure notification email to %s"
                         % ', '.join(responsible_emails))
