# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard

from odoo import api, SUPERUSER_ID


def uninstall_hook(cr, registry):
    # remove reference to mailing.mailing use_in_marketing_automation field
    env = api.Environment(cr, SUPERUSER_ID, {})
    act_window = env.ref('mass_mailing.mailing_mailing_action_mail', False)
    if act_window and act_window.domain and 'use_in_marketing_automation' in act_window.domain:
        act_window.domain = [('mailing_type', '=', 'mail')]
