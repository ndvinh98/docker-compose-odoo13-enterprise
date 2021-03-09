# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import exceptions, fields, models, _


class AmazonMarketplace(models.Model):
    _name = 'amazon.marketplace'
    _description = "Amazon Marketplace"
    _rec_name = 'domain'

    name = fields.Char("Name", required=True, translate=True)
    code = fields.Char("Code", help="The country code in ISO 3166-1 format", required=True)
    domain = fields.Char(
        "Domain", help="The domain name associated with the marketplace", required=True)
    api_ref = fields.Char(
        "API Identifier", help="The Amazon-defined marketplace reference", required=True)

    _sql_constraints = [(
        'unique_api_ref',
        'UNIQUE(api_ref)',
        "There can only exist one marketplace for a given API Identifier."
    )]

    def unlink(self):
        raise exceptions.UserError(_('Amazon marketplaces cannot be deleted.'))
