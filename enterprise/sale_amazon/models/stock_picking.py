# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from . import mws_connector as mwsc
from odoo import api, fields, models, _

from odoo.addons.sale_amazon.lib import mws

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'
    
    amazon_sync_pending = fields.Boolean(
        help="Is True if the picking must be notified to Amazon", default=False)
    
    def write(self, vals):
        pickings = self
        if 'date_done' in vals:
            amazon_pickings = self.sudo().filtered(lambda p: p.sale_id and p.sale_id.amazon_order_ref)
            super(StockPicking, amazon_pickings).write(dict(amazon_sync_pending=True, **vals))
            pickings -= amazon_pickings
        return super(StockPicking, pickings).write(vals)
    
    @api.model
    def _sync_pickings(self, account_ids=()):
        """
        Notify Amazon to confirm orders whose pickings are marked as done. Called by cron.
        We assume that the combined set of pickings (of all accounts) to be synchronized will always
        be too small for the cron to be killed before it finishes synchronizing all pickings.
        If provided, the tuple of account ids restricts the pickings waiting for synchronization
        to those whose account is listed. If it is not provided, all pickings are synchronized.
        :param account_ids: the ids of accounts whose pickings should be synchronized
        """
        pickings_by_account = {}
        for picking in self.search([('amazon_sync_pending', '=', True)]):
            if picking.sale_id.order_line:
                offer = picking.sale_id.order_line[0].amazon_offer_id
                account = offer and offer.account_id  # Offer can be deleted before the cron update
                if not account or (account_ids and account.id not in account_ids):
                    continue
                pickings_by_account.setdefault(account, self.env['stock.picking'])
                pickings_by_account[account] += picking
        for account, pickings in pickings_by_account.items():
            pickings._confirm_shipment(account)
    
    def _confirm_shipment(self, account):
        """ Send the order confirmation feed to Amazon for a batch of orders. """
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
        for picking in self:
            amazon_order_ref = picking.sale_id.amazon_order_ref
            items_data = picking.move_lines.filtered('sale_line_id.amazon_item_ref').mapped(
                lambda l: (l.sale_line_id.amazon_item_ref, l.quantity_done))
            xml_feed = mwsc.generate_order_fulfillment_feed(
                account.seller_key, amazon_order_ref, items_data, *picking._get_carrier_details())
            error_message = _("An error was encountered when confirming shipping of the order with "
                              "amazon id %s.") % amazon_order_ref
            feed_submission_id, rate_limit_reached = mwsc.submit_feed(
                feeds_api, xml_feed, '_POST_ORDER_FULFILLMENT_DATA_', error_message)
            if rate_limit_reached:
                _logger.warning("rate limit reached when confirming picking with id %s for order "
                                "with id %s" % (picking.id, picking.sale_id.id))
                break
            _logger.info("sent shipment confirmation (feed id %s) to amazon for order with "
                         "amazon_order_ref %s" % (feed_submission_id, amazon_order_ref))
        self.write({'amazon_sync_pending': False})
    
    def _get_carrier_details(self):
        """ Return the shipper name and tracking number. Overridden by sale_amazon_delivery. """
        return None, None
