# -*- coding: utf-8 -*-
from odoo.tests import common

from mock import Mock


class TestScoring(common.TransactionCase):

    def setUp(self):
        super(TestScoring, self).setUp()

        self.env.cr.commit = Mock(return_value=None)

        # empty tables before testing to only use test records
        self.env.cr.execute("""
                UPDATE res_partner SET team_id=NULL;
        """)
        self.env.cr.execute("""
                TRUNCATE TABLE team_user;
        """)
        self.env.cr.execute("""
                DELETE FROM crm_team;
        """)
        self.env.cr.execute("""
                DELETE FROM crm_lead;
        """)
        self.env.cr.execute("""
                DELETE FROM website_crm_score;
        """)

        # Usefull models
        self.crm_lead = self.env['crm.lead']
        self.website_crm_score = self.env['website.crm.score']
        self.team = self.env['crm.team']
        self.res_users = self.env['res.users']
        self.team_user = self.env['team.user']
        self.country = self.env['res.country']
        self.crm_stage = self.env['crm.stage']

        self.belgium = self.country.search([('name', '=', 'Belgium')], limit=1).id
        self.france = self.country.search([('name', '=', 'France')], limit=1).id

        self.stage = self.crm_stage.create({
            'name': 'testing',
        }).id

        # Lead Data
        self.lead0 = self.crm_lead.create({
            'name': 'lead0',
            'country_id': self.belgium,
            'email_from': 'lead0@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id
        self.lead1 = self.crm_lead.create({
            'name': 'lead1',
            'country_id': self.france,
            'email_from': 'lead1@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id
        self.lead2 = self.crm_lead.create({
            'name': 'lead2',
            'email_from': 'lead2@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id
        self.lead3 = self.crm_lead.create({
            'name': 'lead3 to archive',
            'email_from': 'lead3@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id
        self.lead4 = self.crm_lead.create({
            'name': 'lead4 to delete',
            'email_from': 'lead4@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id
        self.lead5 = self.crm_lead.create({
            'name': 'lead5 less 1 hour',
            'email_from': 'lead5@test.com',
            'user_id': None,
            'team_id': False,
            'stage_id': self.stage,
        }).id

        self.env.cr.execute("UPDATE crm_lead SET create_date = '2010-01-01 00:00:00' WHERE id != %s", (self.lead5,))

        # Salesteam
        self.team0 = self.team.create({
            'name': 'team0',
            'score_team_domain': [('country_id', '=', 'Belgium')],
        }).id
        self.team1 = self.team.create({
            'name': 'team1',
            'score_team_domain': [('country_id', '=', 'France')],
        }).id

        # Salesmen
        self.salesmen0 = self.res_users.with_context({'no_reset_password': True}).create({
            'name': 'salesmen0',
            'login': 'salesmen0',
            'email': 'salesmen0@example.com',
            # 'groups_id': [(6, 0, [self.group_employee_id])]
        }).id
        self.salesmen1 = self.res_users.with_context({'no_reset_password': True}).create({
            'name': 'salesmen1',
            'login': 'salesmen1',
            'email': 'salesmen1@example.com',
            # 'groups_id': [(6, 0, [self.group_employee_id])]
        }).id

        # team_user
        self.team_user0 = self.team_user.create({
            'user_id': self.salesmen0,
            'team_id': self.team0,
            'maximum_user_leads': 1,
            'team_user_domain': [('country_id', '=', 'Belgium')],
        }).id
        self.team_user1 = self.team_user.create({
            'user_id': self.salesmen1,
            'team_id': self.team0,
            'maximum_user_leads': 0,
            'team_user_domain': [('country_id', '=', 'France')],
        }).id
        self.team_user2 = self.team_user.create({
            'user_id': self.salesmen1,
            'team_id': self.team1,
            'maximum_user_leads': 1,
        }).id

        # Score
        self.score2 = self.website_crm_score.create({
            'name': 'score2',
            'value': 0,
            'domain': "[('name', '=like', '% to archive')]",
            'rule_type': 'active',
        }).id
        self.score4 = self.website_crm_score.create({
            'name': 'score3',
            'value': 0,
            'domain': "[('name', '=like', '% to delete')]",
            'rule_type': 'unlink',
        }).id

    def tearDown(self):
        super(TestScoring, self).tearDown()
