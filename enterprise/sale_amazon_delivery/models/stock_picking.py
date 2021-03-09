# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_carrier_details(self):
        """ Return the shipper name and tracking number if any. """
        self.ensure_one()
        return self.carrier_id and self.carrier_id.name, self.carrier_tracking_ref
