# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    menus_to_remove = [("account.menu_finance_entries", "account.group_account_manager", "account.group_account_user"),
                       ("account.menu_finance_configuration", "account.group_account_user", "account.group_account_manager"),
                       ("account.menu_finance_reports", "account.group_account_user", "account.group_account_manager")]

    for menu_xmlids in menus_to_remove:
        try:
            menu = env.ref(menu_xmlids[0])
            menu.write({'groups_id': [(3, env.ref(menu_xmlids[1]).id), (4, env.ref(menu_xmlids[2]).id)]})
        except ValueError as e:
            _logger.warning(e)

    try:
        group_user = env.ref("account.group_account_user")
        group_user.write({'name': "Show Full Accounting Features",
                          'implied_ids': [(3, env.ref('account.group_account_invoice').id)],
                          'category_id': env.ref("base.module_category_hidden").id})
    except ValueError as e:
            _logger.warning(e)

    try:
        group_manager = env.ref("account.group_account_manager")
        group_manager.write({'name': "Billing Manager",
                             'implied_ids': [(4, env.ref("account.group_account_invoice").id),
                                             (3, env.ref("account.group_account_user").id)]})
    except ValueError as e:
            _logger.warning(e)

    # make the account_accountant features disappear (magic)
    env.ref("account.group_account_user").write({'users': [(5, False, False)]})

    # this menu should always be there, as the module depends on account.
    # if it's not, there is something wrong with the db that should be investigated.
    invoicing_menu = env.ref("account.menu_finance")
    menus_to_move = [
        "account.menu_finance_receivables",
        "account.menu_finance_payables",
        "account.menu_finance_entries",
        "account.menu_finance_reports",
        "account.menu_finance_configuration",
        "account.menu_board_journal_1",
    ]
    for menu_xmlids in menus_to_move:
        try:
            env.ref(menu_xmlids).parent_id = invoicing_menu
        except ValueError as e:
            _logger.warning(e)
