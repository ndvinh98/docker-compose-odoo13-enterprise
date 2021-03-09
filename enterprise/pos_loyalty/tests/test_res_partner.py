# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestPosPartner(TransactionCase):

    def test_merge_contact_with_loyalty_points(self):
        partner_1 = self.env['res.partner'].create({'name': 'Johny', 'loyalty_points': 100})
        partner_2 = self.env['res.partner'].create({'name': 'Jinny', 'loyalty_points': 200})

        merge_wizard = Form(self.env['base.partner.merge.automatic.wizard'].with_context(
            active_model='res.partner',
            active_ids=[partner_1.id, partner_2.id]
        )).save()

        merge_wizard.action_merge()
        self.assertEqual(partner_2.loyalty_points, 300)
