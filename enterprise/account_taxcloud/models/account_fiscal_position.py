# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountFiscalPositionTemplate(models.Model):
    _inherit = 'account.fiscal.position.template'

    is_taxcloud = fields.Boolean(string='Use TaxCloud API')


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    is_taxcloud_configured = fields.Boolean(related='company_id.is_taxcloud_configured', help='Used to determine whether or not to warn the user to configure TaxCloud.')
    is_taxcloud = fields.Boolean(string='Use TaxCloud API')
