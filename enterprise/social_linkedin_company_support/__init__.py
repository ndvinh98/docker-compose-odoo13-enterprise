# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api

from . import models


def _remove_existing_linkedin_account(cr, registry):
    """Remove all existing personal LinkedIn accounts"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['social.account'].search([('media_type', '=', 'linkedin'), ('linkedin_account_id', 'ilike', 'urn:li:person')]).unlink()
