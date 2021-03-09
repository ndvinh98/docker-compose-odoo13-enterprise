# Part of Odoo. See LICENSE file for full copyright and licensing details.
# -*- coding: utf-8 -*-

import odoo.tests


@odoo.tests.tagged('post_install', '-at_install')
class TestUi(odoo.tests.HttpCase):

    def test_new_app_and_report(self):
        self.start_tour("/web?studio=app_creator", 'web_studio_new_app_tour', login="admin")

        # the report tour is based on the result of the former tour
        self.start_tour("/web", 'web_studio_new_report_tour', login="admin")
        self.start_tour("/web", "web_studio_new_report_basic_layout_tour", login="admin")

    def test_optional_fields(self):
        self.start_tour("/web", 'web_studio_hide_fields_tour', login="admin")

    def test_rename(self):
        self.start_tour("/web?studio=app_creator", 'web_studio_tests_tour', login="admin", timeout=120)
