# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo.addons.industry_fsm.tests.test_fsm_flow import TestFsmFlow

class TestFsmStock(TestFsmFlow):

    def test_fsm_flow(self):
        super(TestFsmStock, self).test_fsm_flow()
        self.assertEqual(self.task.sale_order_id.picking_ids.mapped('state'), ['done'], "Pickings should be set as done")
