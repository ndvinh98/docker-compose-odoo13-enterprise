# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from odoo.fields import Datetime
from odoo.tests import common


class MarketingCampaignTestBase(common.TransactionCase):

    def setUp(self):
        super(MarketingCampaignTestBase, self).setUp()

        Users = self.env['res.users'].with_context(no_reset_password=True)
        self.user_market = Users.create({
            'name': 'Juliette MarketUser',
            'login': 'juliette',
            'email': 'juliette.marketuser@example.com',
            'groups_id': [(6, 0, [self.ref('base.group_user'), self.ref('marketing_automation.group_marketing_automation_user')])]
        })
        Partners = self.env['res.partner']
        self.test_partner1 = Partners.create({'name': 'P1', 'email': 'p1@example.com'})
        self.test_partner2 = Partners.create({'name': 'P2', 'email': 'p2@example.com'})
        self.test_partner3 = Partners.create({'name': 'P3', 'email': 'p3@example.com'})
        self.test_model = self.env.ref('test_marketing_automation.model_test_marketing_automation_test_simple')
        self.TestModel = self.env['test_marketing_automation.test.simple']
        self.test_rec0 = self.TestModel.create({'name': 'Invalid', 'email_from': 'invalid@example.com'})
        self.test_rec1 = self.TestModel.create({'name': 'Test_1', 'email_from': 'p1@example.com', 'partner_id': self.test_partner1.id})
        self.test_rec2 = self.TestModel.create({'name': 'Test_2', 'email_from': 'p2@example.com', 'partner_id': self.test_partner2.id})
        self.test_rec3 = self.TestModel.create({'name': 'Test_3', 'email_from': 'p3@example.com', 'partner_id': self.test_partner3.id})
        self.test_rec4 = self.TestModel.create({'name': 'Brol_1', 'email_from': 'brol@example.com'})

        self.patcher = patch('odoo.addons.marketing_automation.models.marketing_campaign.Datetime', wraps=Datetime)
        self.patcher2 = patch('odoo.addons.marketing_automation.models.marketing_participant.Datetime', wraps=Datetime)

        self.mock_datetime = self.patcher.start()
        self.mock_datetime2 = self.patcher2.start()

    def tearDown(self):
        self.patcher.stop()
        super(MarketingCampaignTestBase, self).tearDown()
