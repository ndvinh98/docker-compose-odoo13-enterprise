# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard

from odoo import api, SUPERUSER_ID


def _setup_mod_sequences(cr, registry):
    """ Creates a distinct sequence for each existing company,
    for both mod 347 and mod 349 BOE export.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    all_companies = env['res.company'].search([])
    all_companies._create_mod_boe_sequences()