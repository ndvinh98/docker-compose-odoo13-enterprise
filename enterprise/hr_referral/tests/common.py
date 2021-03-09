# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class TestHrReferralBase(TransactionCase):

    def setUp(self):
        super(TestHrReferralBase, self).setUp()

        self.company_1 = self.env['res.company'].create({'name': 'Opoo'})
        self.company_2 = self.env['res.company'].create({'name': 'Otoo'})
        self.company_ids = [self.company_1.id, self.company_2.id]

        self.dep_rd = self.env['hr.department'].create({
            'name': 'Research and Development',
            'company_id': self.company_1.id
        })

        # I create a new user "Richard"
        self.richard_user = self.env['res.users'].create({
            'name': 'Richard',
            'login': 'ric'
        })

        # I create a new user "Steve"
        self.steve_user = self.env['res.users'].create({
            'name': 'Steve',
            'login': 'stv'
        })

        self.job_dev = self.env['hr.job'].create({
            'name': 'Dev',
            'no_of_recruitment': '5',
            'department_id': self.dep_rd.id,
            'company_id': self.company_1.id,
        })

        self.mug_shop = self.env['hr.referral.reward'].create({
            'name': 'Mug',
            'description': 'Beautiful and usefull',
            'cost': '5',
            'company_id': self.company_1.id,
        })

        self.red_mug_shop = self.env['hr.referral.reward'].create({
            'name': 'Red Mug',
            'description': 'It\'s red',
            'cost': '10',
            'company_id': self.company_2.id,
        })

        self.mug_shop = self.mug_shop.with_user(self.richard_user.id)

        def _get_title_from_url(u):
            return "Hello"

        def _compute_favicon():
            # 1px to avoid real request
            return 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=='

        patcher = patch('odoo.addons.link_tracker.models.link_tracker.LinkTracker._compute_favicon', wraps=_compute_favicon)
        patcher2 = patch('odoo.addons.link_tracker.models.link_tracker.LinkTracker._get_title_from_url', wraps=_get_title_from_url)
        patcher.start()
        patcher2.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(patcher2.stop)
