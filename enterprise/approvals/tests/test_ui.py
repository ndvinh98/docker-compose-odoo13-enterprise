# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests


@odoo.tests.tagged('-at_install', 'post_install')
class TestUi(odoo.tests.HttpCase):
    def test_ui(self):
        self.start_tour("/web", 'approvals_tour', login='admin')
