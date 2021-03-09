# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from . import mws_connector as mwsc
from odoo import api, fields, models, _

from odoo.addons.sale_amazon.lib import mws

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    amazon_order_ref = fields.Char(help="The Amazon-defined order reference")
    amazon_channel = fields.Selection(
        [('fbm', "Fulfillment by Merchant"), ('fba', "Fulfillment by Amazon")],
        string="Fulfillment Channel", translate=False)
    amazon_cancellation_pending = fields.Boolean(
        help="Is True if the order cancellation must be notified to Amazon", default=False)

    _sql_constraints = [(
        'unique_amazon_order_ref',
        'UNIQUE(amazon_order_ref)',
        "There can only exist one sale order for a given Amazon Order Reference."
    )]

    def action_cancel(self):
        if not self.env.context.get('canceled_by_amazon', False):
            self.write({'amazon_cancellation_pending': True})
        return super(SaleOrder, self).action_cancel()

    def _action_confirm(self):
        self.filtered('amazon_order_ref').write({'amazon_cancellation_pending': False})
        return super(SaleOrder, self)._action_confirm()

    @api.model
    def _sync_cancellations(self, account_ids=()):
        """
        Notify Amazon to cancel orders marked as cancelled in Odoo. Called by cron.
        We assume that the combined set of orders (of all accounts) to be cancelled will always be
        too small for the cron to be killed before it finishes synchronizing all order cancellations
        If provided, the tuple of account ids restricts the orders waiting for synchronization
        to those whose account is listed. If it is not provided, all orders are synchronized.
        :param account_ids: the ids of accounts whose orders should be synchronized
        """
        orders_by_account = {}
        for order in self.search(
                [('amazon_cancellation_pending', '=', True), ('order_line', '!=', False)]):
            offer = order.order_line[0].amazon_offer_id
            account = offer and offer.account_id  # Offer can be deleted before the cron update
            if not account or (account_ids and account.id not in account_ids):
                continue
            orders_by_account.setdefault(account, self.env['sale.order'])
            orders_by_account[account] += order
        for account, orders in orders_by_account.items():
            orders._cancel_on_amazon(account)

    def _cancel_on_amazon(self, account):
        """ Send the order cancellation feed to Amazon for a batch of orders. """
        error_message = _("An error was encountered when preparing the connection to Amazon.")
        account_data = account.read(account._get_api_key_field_names())[0]
        api_keys = {field_name: account_data.get(field_name)
                    for field_name in account._get_api_key_field_names()}
        feeds_api = mwsc.get_api_connector(
            mws.Feeds,
            account.access_key,
            account.secret_key,
            account.seller_key,
            account.base_marketplace_id.code,
            error_message,
            **account._build_get_api_connector_kwargs(**api_keys))
        for order in self:
            error_message = _("An error was encountered when updating the status of the order with "
                              "amazon ref %s.") % order.amazon_order_ref
            xml_feed = mwsc.generate_order_cancellation_feed(
                account.seller_key, order.amazon_order_ref)
            feed_submission_id, rate_limit_reached = mwsc.submit_feed(
                feeds_api, xml_feed, '_POST_ORDER_ACKNOWLEDGEMENT_DATA_', error_message)
            if rate_limit_reached:
                _logger.warning("rate limit reached when sending cancellation notification "
                                "for account with id %s" % account.id)
                break
            _logger.info("sent cancellation request (feed id %s) to amazon for order with "
                         "amazon_order_ref %s" % (feed_submission_id, order.amazon_order_ref))
        self.write({'amazon_cancellation_pending': False})


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    amazon_item_ref = fields.Char("Amazon-defined item reference")
    amazon_offer_id = fields.Many2one('amazon.offer', "Amazon Offer", ondelete='set null')

    _sql_constraints = [(
        'unique_amazon_item_ref',
        'UNIQUE(amazon_item_ref)',
        "There can only exist one sale order line for a given Amazon Item Reference."
    )]
