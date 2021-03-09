# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from .common import HelpdeskCommon
from odoo import fields
from odoo.exceptions import AccessError


class TestHelpdeskFlow(HelpdeskCommon):
    """ Test used to check that the base functionalities of Helpdesk function as expected.
        - test_access_rights: tests a few access rights constraints
        - test_assign_close_dates: tests the assignation and closing time get computed correctly
        - test_ticket_partners: tests the number of tickets of a partner is computed correctly
        - test_team_assignation_[method]: tests the team assignation method work as expected
    """

    def setUp(self):
        super(TestHelpdeskFlow, self).setUp()

    def test_access_rights(self):
        # helpdesk user should only be able to:
        #   read: teams, stages, SLAs, ticket types
        #   read, create, write, unlink: tickets, tags
        # helpdesk manager:
        #   read, create, write, unlink: everything (from helpdesk)
        # we consider in these tests that if the user can do it, the manager can do it as well (as the group is implied)
        def test_write_and_unlink(record):
            record.write({'name': 'test_write'})
            record.unlink()

        def test_not_write_and_unlink(self, record):
            with self.assertRaises(AccessError):
                record.write({'name': 'test_write'})
            with self.assertRaises(AccessError):
                record.unlink()
            # self.assertRaises(AccessError, record.write({'name': 'test_write'})) # , "Helpdesk user should not be able to write on %s" % record._name)
            # self.assertRaises(AccessError, record.unlink(), "Helpdesk user could unlink %s" % record._name)

        # helpdesk.team access rights
        team = self.env['helpdesk.team'].with_user(self.helpdesk_manager).create({'name': 'test'})
        team.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, team.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            team.with_user(self.helpdesk_user).create({'name': 'test create'})
        test_write_and_unlink(team)

        # helpdesk.ticket access rights
        ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({'name': 'test'})
        ticket.read()
        test_write_and_unlink(ticket)

        # helpdesk.stage access rights
        stage = self.env['helpdesk.stage'].with_user(self.helpdesk_manager).create({
            'name': 'test',
            'team_ids': [(6, 0, [self.test_team.id])],
        })
        stage.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, stage.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            stage.with_user(self.helpdesk_user).create({
                'name': 'test create',
                'team_ids': [(6, 0, [self.test_team.id])],
            })
        test_write_and_unlink(stage)

        # helpdesk.sla access rights
        sla = self.env['helpdesk.sla'].with_user(self.helpdesk_manager).create({
            'name': 'test',
            'team_id': self.test_team.id,
            'stage_id': self.stage_done.id,
        })
        sla.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, sla.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            sla.with_user(self.helpdesk_user).create({
                'name': 'test create',
                'team_id': self.test_team.id,
                'stage_id': self.stage_done.id,
            })
        test_write_and_unlink(sla)

        # helpdesk.ticket.type access rights
        ticket_type = self.env['helpdesk.ticket.type'].with_user(self.helpdesk_manager).create({
            'name': 'test with unique name please',
        })
        ticket_type.with_user(self.helpdesk_user).read()
        test_not_write_and_unlink(self, ticket_type.with_user(self.helpdesk_user))
        with self.assertRaises(AccessError):
            ticket_type.with_user(self.helpdesk_user).create({
                'name': 'test create with unique name please',
            })
        test_write_and_unlink(ticket_type)

        # helpdesk.tag access rights
        tag = self.env['helpdesk.tag'].with_user(self.helpdesk_user).create({'name': 'test with unique name please'})
        tag.read()
        test_write_and_unlink(tag)

    def test_assign_close_dates(self):
        # helpdesk user create a ticket
        ticket1 = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'test ticket 1',
            'team_id': self.test_team.id,
        })
        self._utils_set_create_date(ticket1, '2019-01-08 12:00:00')

        with self._ticket_patch_now('2019-01-10 13:00:00'):
            # the helpdesk user takes the ticket
            ticket1.assign_ticket_to_self()
            # we verify the ticket is correctly assigned
            self.assertEqual(ticket1.user_id.id, ticket1._uid, "Assignation for ticket not correct")
            self.assertEqual(ticket1.assign_hours, 17, "Assignation time for ticket not correct")
        with self._ticket_patch_now('2019-01-10 15:00:00'):
            # we close the ticket and verify its closing time
            ticket1.write({'stage_id': self.stage_done.id})
            self.assertEqual(ticket1.close_hours, 19, "Close time for ticket not correct")

    def test_ticket_partners(self):
        # we create a partner
        partner = self.env['res.partner'].create({
            'name': 'Freddy Krueger'
        })
        # helpdesk user creates 2 tickets for the partner
        ticket1 = self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'partner ticket 1',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
        })
        self.env['helpdesk.ticket'].with_user(self.helpdesk_user).create({
            'name': 'partner ticket 2',
            'team_id': self.test_team.id,
            'partner_id': partner.id,
        })
        self.assertTrue(ticket1.partner_ticket_count == 2, "Incorrect number of tickets from the same partner.")

    def test_team_assignation_randomly(self):
        # we put the helpdesk user and manager in the test_team's members
        self.test_team.member_ids = [(6, 0, [self.helpdesk_user.id, self.helpdesk_manager.id])]
        # we set the assignation method to randomly (=uniformly distributed)
        self.test_team.assign_method = 'randomly'
        # we create a bunch of tickets
        for i in range(10):
            self.env['helpdesk.ticket'].create({
                'name': 'test ticket ' + str(i),
                'team_id': self.test_team.id,
            })
        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id)]), 5)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id)]), 5)

    def test_team_assignation_balanced(self):
        # we put the helpdesk user and manager in the test_team's members
        self.test_team.member_ids = [(6, 0, [self.helpdesk_user.id, self.helpdesk_manager.id])]
        # we set the assignation method to randomly (=uniformly distributed)
        self.test_team.assign_method = 'balanced'
        # we create a bunch of tickets
        for i in range(4):
            self.env['helpdesk.ticket'].create({
                'name': 'test ticket ' + str(i),
                'team_id': self.test_team.id,
            })
        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id)]), 2)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id)]), 2)

        # helpdesk user finishes his 2 tickets
        self.env['helpdesk.ticket'].search([('user_id', '=', self.helpdesk_user.id)]).write({'stage_id': self.stage_done.id})

        # we create 4 new tickets
        for i in range(4):
            self.env['helpdesk.ticket'].create({
                'name': 'test ticket ' + str(i),
                'team_id': self.test_team.id,
            })

        # ensure both members have the same amount of tickets assigned
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_user.id), ('close_date', '=', False)]), 3)
        self.assertEqual(self.env['helpdesk.ticket'].search_count([('user_id', '=', self.helpdesk_manager.id), ('close_date', '=', False)]), 3)

    def test_create_from_email_multicompany(self):
        company0 = self.env.company
        company1 = self.env['res.company'].create({'name': 'new_company0'})
        Partner = self.env['res.partner']

        self.env.user.write({
            'company_ids': [(4, company0.id, False), (4, company1.id, False)],
        })

        helpdesk_team_model = self.env['ir.model'].search([('model', '=', 'helpdesk_team')])
        ticket_model = self.env['ir.model'].search([('model', '=', 'helpdesk.ticket')])
        self.env["ir.config_parameter"].sudo().set_param("mail.catchall.domain", 'aqualung.com')

        helpdesk_team0 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team 0',
            'company_id': company0.id,
        })
        helpdesk_team1 = self.env['helpdesk.team'].create({
            'name': 'helpdesk team 1',
            'company_id': company1.id,
        })

        mail_alias0 = self.env['mail.alias'].create({
            'alias_name': 'helpdesk_team_0',
            'alias_model_id': ticket_model.id,
            'alias_parent_model_id': helpdesk_team_model.id,
            'alias_parent_thread_id': helpdesk_team0.id,
            'alias_defaults': "{'team_id': %s}" % helpdesk_team0.id,
        })
        mail_alias1 = self.env['mail.alias'].create({
            'alias_name': 'helpdesk_team_1',
            'alias_model_id': ticket_model.id,
            'alias_parent_model_id': helpdesk_team_model.id,
            'alias_parent_thread_id': helpdesk_team1.id,
            'alias_defaults': "{'team_id': %s}" % helpdesk_team1.id,
        })

        new_message0 = """MIME-Version: 1.0
Date: Thu, 27 Dec 2018 16:27:45 +0100
Message-ID: blablabla0
Subject: helpdesk team 0 in company 0
From:  A client <client_a@someprovider.com>
To: helpdesk_team_0@aqualung.com
Content-Type: multipart/alternative; boundary="000000000000a47519057e029630"

--000000000000a47519057e029630
Content-Type: text/plain; charset="UTF-8"


--000000000000a47519057e029630
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div>A good message</div>

--000000000000a47519057e029630--
"""

        new_message1 = """MIME-Version: 1.0
Date: Thu, 27 Dec 2018 16:27:45 +0100
Message-ID: blablabla1
Subject: helpdesk team 1 in company 1
From:  B client <client_b@someprovider.com>
To: helpdesk_team_1@aqualung.com
Content-Type: multipart/alternative; boundary="000000000000a47519057e029630"

--000000000000a47519057e029630
Content-Type: text/plain; charset="UTF-8"


--000000000000a47519057e029630
Content-Type: text/html; charset="UTF-8"
Content-Transfer-Encoding: quoted-printable

<div>A good message bis</div>

--000000000000a47519057e029630--
"""
        partners_exist = Partner.search([('email', 'in', ['client_a@someprovider.com', 'client_b@someprovider.com'])])
        self.assertFalse(partners_exist)

        helpdesk_ticket0_id = self.env['mail.thread'].message_process('helpdesk.ticket', new_message0)
        helpdesk_ticket1_id = self.env['mail.thread'].message_process('helpdesk.ticket', new_message1)

        helpdesk_ticket0 = self.env['helpdesk.ticket'].browse(helpdesk_ticket0_id)
        helpdesk_ticket1 = self.env['helpdesk.ticket'].browse(helpdesk_ticket1_id)

        self.assertEqual(helpdesk_ticket0.team_id, helpdesk_team0)
        self.assertEqual(helpdesk_ticket1.team_id, helpdesk_team1)

        self.assertEqual(helpdesk_ticket0.company_id, company0)
        self.assertEqual(helpdesk_ticket1.company_id, company1)

        partner0 = Partner.search([('email', '=', 'client_a@someprovider.com')])
        partner1 = Partner.search([('email', '=', 'client_b@someprovider.com')])
        self.assertTrue(partner0)
        self.assertTrue(partner1)

        self.assertEqual(partner0.company_id, company0)
        self.assertEqual(partner1.company_id, company1)

        self.assertEqual(helpdesk_ticket0.partner_id, partner0)
        self.assertEqual(helpdesk_ticket1.partner_id, partner1)

        self.assertTrue(partner0 in helpdesk_ticket0.message_follower_ids.mapped('partner_id'))
        self.assertTrue(partner1 in helpdesk_ticket1.message_follower_ids.mapped('partner_id'))

    def test_team_assignation_balanced(self):
        #We create an sla policy with minimum priority set as '2'
        self.test_team.use_sla = True
        sla = self.env['helpdesk.sla'].create({
            'name': 'test sla policy',
            'team_id': self.test_team.id,
            'stage_id': self.stage_progress.id,
            'priority': '2',
            'time_days': 0,
            'time_hours': 1
        })

        #We create a ticket with priority less than what's on the sla policy
        ticket_1 = self.env['helpdesk.ticket'].create({
            'name': 'test ',
            'team_id': self.test_team.id,
            'priority': '1'
        })

        #We create a ticket with priority equal to what's on the sla policy
        ticket_2 = self.env['helpdesk.ticket'].create({
            'name': 'test sla ticket',
            'team_id': self.test_team.id,
            'priority': '2'
        })

        #We create a ticket with priority greater than what's on the sla policy
        ticket_3 = self.env['helpdesk.ticket'].create({
            'name': 'test sla ticket',
            'team_id': self.test_team.id,
            'priority': '3'
        })
        #We confirm that the sla policy has been applied successfully on the ticket.
        #sla policy must not be applied
        self.assertTrue(sla not in ticket_1.sla_status_ids.mapped('sla_id'))
        #sla policy must be applied
        self.assertTrue(sla in ticket_2.sla_status_ids.mapped('sla_id'))
        self.assertTrue(sla in ticket_3.sla_status_ids.mapped('sla_id'))
