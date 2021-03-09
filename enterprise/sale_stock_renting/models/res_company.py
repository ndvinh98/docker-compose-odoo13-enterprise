# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Rental Inventory

    rental_loc_id = fields.Many2one(
        "stock.location", string="In rent",
        domain=[('usage', '=', 'internal')],
        help="This technical location serves as stock for products currently in rental"
        "This location is internal because products in rental"
        "are still considered as company assets.")

    # Padding Time

    padding_time = fields.Float(
        string="Padding Time", default=0.0,
        help="Amount of time (in hours) during which a product is considered unavailable prior to renting (preparation time).")

    def _create_rental_location(self):
        for company in self:
            if not company.rental_loc_id:
                company.rental_loc_id = self.env['stock.location'].sudo().create({
                    "name": "Rental",
                    "usage": "internal",
                    "company_id": company.id,
                })
