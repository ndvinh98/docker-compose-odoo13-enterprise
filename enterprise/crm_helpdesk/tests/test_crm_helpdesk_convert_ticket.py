# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestConvertToTicket(common.TransactionCase):

    def test_00_test_crm_helpdesk_convert_ticket(self):

        email = 'test@ticket.com'
        description = 'Small Description'
        partner = self.env['res.partner'].create({
            'name': 'TEST PARTNER',
        })

        # Lead with partner name
        lead_A = self.env['crm.lead'].create({
            'name': 'Lead A',
            'partner_name': partner.name,
            'description': description,
        })

        # Lead with partner id
        lead_B = self.env['crm.lead'].create({
            'name': 'Lead B',
            'description': description,
            'partner_id': partner.id
        })

        # Lead with email
        lead_C = self.env['crm.lead'].create({
            'name': 'Lead C',
            'description': description,
            'email_from': email,
        })

        team = self.env['helpdesk.team'].create({
            'name': 'MY TEAM'
        })

        ticket_type = self.env['helpdesk.ticket.type'].create({
            'name': 'MY TYPE'
        })

        new_message = lead_A.message_post(subject="NEW MESSAGE")

        number_messages_lead_A = len(lead_A.message_ids)
        number_messages_lead_B = len(lead_B.message_ids)

        # Create tickets from the leads
        convert_A = self.env['crm.lead.convert2ticket'].with_context({
            'active_model': 'crm.lead',
            'active_id': lead_A.id
        }).create({
                'team_id': team.id,
                'ticket_type_id': ticket_type.id
        })
        convert_A.action_lead_to_helpdesk_ticket()

        convert_B = self.env['crm.lead.convert2ticket'].with_context({
            'active_model': 'crm.lead',
            'active_id': lead_B.id
        }).create({
                'team_id': team.id,
                'ticket_type_id': ticket_type.id
        })
        convert_B.action_lead_to_helpdesk_ticket()

        convert_C = self.env['crm.lead.convert2ticket'].with_context({
            'active_model': 'crm.lead',
            'active_id': lead_C.id
        }).create({
            'team_id': team.id
        })
        convert_C.action_lead_to_helpdesk_ticket()

        # Check leads status
        self.assertFalse(lead_A.active, "The lead has not been archived")
        self.assertFalse(lead_B.active, "The lead has not been archived")
        self.assertFalse(lead_C.active, "The lead has not been archived")

        # Check tickets have been created
        ticket_A = self.env['helpdesk.ticket'].search([('name', '=', 'Lead A')])
        ticket_B = self.env['helpdesk.ticket'].search([('name', '=', 'Lead B')])
        ticket_C = self.env['helpdesk.ticket'].search([('name', '=', 'Lead C')])
        self.assertEqual(len(ticket_A), 1, "No ticket has been created from the lead A")
        self.assertEqual(len(ticket_B), 1, "No ticket has been created from the lead B")
        self.assertEqual(len(ticket_C), 1, "No ticket has been created from the lead C")

        # Check created tickets values
        self.assertEqual(ticket_A.ticket_type_id, ticket_type, "Wrong ticket type for ticket A")
        self.assertFalse(ticket_C.ticket_type_id, "Wrong ticket type for ticket C")
        self.assertEqual(ticket_A.team_id, team, "The ticket A has not been assigned to the right team")
        self.assertEqual(ticket_A.description, description, "Wrong description of ticket A")
        self.assertFalse(ticket_A.user_id, "Ticket A has been wrongfully assigned to an user")
        self.assertFalse(ticket_B.user_id, "Ticket B has been wrongfully assigned to an user")
        self.assertFalse(ticket_C.user_id, "Ticket C has been wrongfully assigned to an user")

        # Check that partner was found from name
        self.assertEqual(ticket_A.partner_id, partner, "Wrong partner in ticket A")

        # Check that partner_id was kept
        self.assertEqual(ticket_B.partner_id, partner, "Wrong partner in ticket B")

        # Check that email was kept
        self.assertEqual(ticket_C.email, email, "Wrong email address in ticket C")

        # Check mail thread transfer
        transferred_message = ticket_A.message_ids.search([('subject', '=', 'NEW MESSAGE')])
        self.assertEqual(transferred_message, new_message,
                         "Thread mailing conversation has not been transferred to ticket A")
        self.assertEqual(len(ticket_A.message_ids), number_messages_lead_A + 2, "Wrong number of messages from lead A")
        self.assertEqual(len(ticket_B.message_ids), number_messages_lead_B + 2, "Wrong number of messages from lead B")
