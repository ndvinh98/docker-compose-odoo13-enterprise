# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch
from dateutil.relativedelta import relativedelta
from datetime import datetime

from odoo import fields
from odoo.tests.common import SavepointCase
from .test_helpdesk_sla import HelpdeskCommon


NOW = datetime(2018, 10, 10, 9, 18)

@patch.object(fields.Date, 'today', lambda: NOW.date())
@patch.object(fields.Datetime, 'today', lambda: NOW.replace(hour=0, minute=0, second=0))
@patch.object(fields.Datetime, 'now', lambda: NOW)
class HelpdeskDashboardTest(HelpdeskCommon):

    def setUp(self):
        super().setUp()
        self.sla.time_days = 0
        self.sla.time_hours = 3

    def test_failed_tickets(self):
        # Failed ticket
        failed_ticket = self.create_ticket(user_id=self.env.user.id, create_date=NOW - relativedelta(hours=3, minutes=2))

        # Not failed ticket
        ticket = self.create_ticket(user_id=self.env.user.id, create_date=NOW - relativedelta(hours=2, minutes=2))

        data = self.env['helpdesk.team'].retrieve_dashboard()
        self.assertEqual(data['my_all']['count'], 2, "There should be 2 tickets")
        self.assertEqual(data['my_all']['failed'], 1, "There should be 1 failed ticket")
