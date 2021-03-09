# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_ebay.tools.ebaysdk import Trading
from ebaysdk.exception import ConnectionError
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ebay_dev_id = fields.Char("Developer Key", default='', config_parameter='ebay_dev_id')
    ebay_sandbox_token = fields.Char("Sandbox Token", default='', config_parameter='ebay_sandbox_token')
    ebay_sandbox_app_id = fields.Char("Sandbox App Key", default='', config_parameter='ebay_sandbox_app_id')
    ebay_sandbox_cert_id = fields.Char("Sandbox Cert Key", default='', config_parameter='ebay_sandbox_cert_id')

    ebay_prod_token = fields.Char("Production Token", default='', config_parameter='ebay_prod_token')
    ebay_prod_app_id = fields.Char("Production App Key", default='', config_parameter='ebay_prod_app_id')
    ebay_prod_cert_id = fields.Char("Production Cert Key", default='', config_parameter='ebay_prod_cert_id')
    ebay_domain = fields.Selection([
        ('prod', 'Production'),
        ('sand', 'Sandbox'),
    ], string='eBay Environment', default='sand', required=True, config_parameter='ebay_domain')
    ebay_currency = fields.Many2one("res.currency", string='ebay Currency',
                                    domain=[('ebay_available', '=', True)], required=True,
                                    default=lambda self: self.env['res.currency'].search([('ebay_available', '=', True)], limit=1).id,
                                    config_parameter='ebay_currency')
    ebay_country = fields.Many2one("res.country", domain=[('ebay_available', '=', True)],
                                   string="Country",
                                   default=lambda self: self.env['res.country'].search([('ebay_available', '=', True)], limit=1).id,
                                   config_parameter='ebay_country')
    ebay_site = fields.Many2one("ebay.site", string="eBay Website",
                                default=lambda self: self.env['ebay.site'].search([('ebay_id', '=', '0')], limit=1).id,
                                config_parameter='ebay_site')
    ebay_zip_code = fields.Char(string="Zip", default='', config_parameter='ebay_zip_code')
    ebay_location = fields.Char(string="Location", default='', config_parameter='')
    ebay_out_of_stock = fields.Boolean("Out Of Stock", default=False)
    ebay_sales_team = fields.Many2one("crm.team", string="ebay Sales Team",
                                      config_parameter='ebay_sales_team')
    ebay_gallery_plus = fields.Boolean("Gallery Plus", default='', config_parameter='ebay_gallery_plus')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        # by default all currencies active field is set to False except EUR and USD
        self.ebay_currency.active = True

        out_of_stock = self.ebay_out_of_stock or ''
        if out_of_stock != self.env['ir.config_parameter'].get_param('ebay_out_of_stock'):
            set_param('ebay_out_of_stock', out_of_stock)
            siteid = self.ebay_site.ebay_id if self.ebay_site else 0

            if self.ebay_domain == 'sand':
                if self.ebay_sandbox_token and self.ebay_sandbox_cert_id and self.ebay_sandbox_app_id:
                    ebay_api = Trading(
                        domain='api.sandbox.ebay.com',
                        config_file=None,
                        appid=self.ebay_sandbox_app_id,
                        devid="ed74122e-6f71-4877-83d8-e0e2585bd78f",
                        certid=self.ebay_sandbox_cert_id,
                        token=self.ebay_sandbox_token,
                        siteid=siteid)
                    call_data = {
                        'OutOfStockControlPreference': 'true' if out_of_stock else 'false',
                    }
                    try:
                        ebay_api.execute('SetUserPreferences', call_data)
                    except ConnectionError:
                        pass
            else:
                if self.ebay_prod_token and self.ebay_prod_cert_id and self.ebay_prod_app_id:
                    ebay_api = Trading(
                        domain='api.ebay.com',
                        config_file=None,
                        appid=self.ebay_prod_app_id,
                        devid="ed74122e-6f71-4877-83d8-e0e2585bd78f",
                        certid=self.ebay_prod_cert_id,
                        token=self.ebay_prod_token,
                        siteid=siteid)
                    call_data = {
                        'OutOfStockControlPreference': 'true' if out_of_stock else 'false',
                    }
                    try:
                        ebay_api.execute('SetUserPreferences', call_data)
                    except ConnectionError:
                        pass

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            ebay_out_of_stock=get_param('ebay_out_of_stock', default=False),
        )
        return res

    @api.model
    def button_sync_categories(self, context=None):
        self.env['ebay.category']._cron_sync()

    @api.model
    def button_sync_product_status(self, context=None):
        self.env['product.template'].sync_product_status()

    @api.model
    def sync_policies(self, context=None):
        self.env['ebay.policy'].sync_policies()

    @api.model
    def sync_ebay_details(self, context=None):
        response = self.env['product.template'].ebay_execute(
            'GeteBayDetails',
            {'DetailName': ['CountryDetails', 'SiteDetails', 'CurrencyDetails']}
        )
        for country in self.env['res.country'].search([('ebay_available', '=', True)]):
            country.ebay_available = False
        for country in response.dict()['CountryDetails']:
            record = self.env['res.country'].search([('code', '=', country['Country'])])
            if record:
                record.ebay_available = True
        for currency in self.env['res.currency'].search([('ebay_available', '=', True)]):
            currency.ebay_available = False
        for currency in response.dict()['CurrencyDetails']:
            record = self.env['res.currency'].with_context(active_test=False).search([('name', '=', currency['Currency'])])
            if record:
                record.ebay_available = True
        for site in response.dict()['SiteDetails']:
            record = self.env['ebay.site'].search([('ebay_id', '=', site['SiteID'])])
            if not record:
                record = self.env['ebay.site'].create({
                    'name': site['Site'],
                    'ebay_id': site['SiteID']
                })
            else:
                record.name = site['Site']
