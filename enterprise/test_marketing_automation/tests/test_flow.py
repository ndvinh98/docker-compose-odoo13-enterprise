# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from unittest.mock import patch

from odoo.addons.base.models.ir_mail_server import IrMailServer
from odoo.fields import Datetime
from odoo.tools import mute_logger

from odoo.addons.test_marketing_automation.tests.common import MarketingCampaignTestBase

from odoo.tests import tagged


@tagged('marketing_automation')
class MarketingCampaignTest(MarketingCampaignTestBase):

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_simple_flow(self):
        date = Datetime.from_string('2014-08-01 15:02:32')  # so long, little task
        self.mock_datetime.now.return_value = date
        self.mock_datetime2.now.return_value = date

        Campaign = self.env['marketing.campaign'].with_user(self.user_market)
        Activity = self.env['marketing.activity'].with_user(self.user_market)
        MassMail = self.env['mailing.mailing'].with_user(self.user_market)
        ServerAction = self.env['ir.actions.server'].with_user(self.user_market)

        # Create campaign
        campaign = Campaign.create({
            'name': 'My First Campaign',
            'model_id': self.test_model.id,
            'domain': '%s' % ([('name', '!=', 'Invalid')]),
        })

        # Create first activity flow
        mass_mailing = MassMail.create({
            'name': 'Hello',
            'subject': 'Hello',
            'body_html': '<div>My Email Body</div>',
            'mailing_model_id': self.test_model.id,
            'use_in_marketing_automation': True,
        })
        act_0 = Activity.create({
            'name': 'Enter the campaign',
            'campaign_id': campaign.id,
            'activity_type': 'email',
            'mass_mailing_id': mass_mailing.id,
            'trigger_type': 'begin',
            'interval_number': '0',
        })

        # NOTSURE: let us consider currently that a smart admin created the server action for the marketing user, is probably the case actually
        server_action = ServerAction.sudo().create({
            'name': 'Update name',
            'state': 'code',
            'model_id': self.test_model.id,
            'code': '''
for record in records:
    record.write({'name': record.name + 'SA'})'''
        })
        act_1 = Activity.create({
            'name': 'Update name',
            'activity_domain': '%s' % ([('name', 'ilike', 'Test')]),
            'campaign_id': campaign.id,
            'parent_id': act_0.id,
            'activity_type': 'action',
            'server_action_id': server_action.id,
            'trigger_type': 'act',
            'interval_number': '1',
            'interval_type': 'hours',
        })

        # User starts and syncs its campaign
        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')
        campaign.sync_participants()

        # All records not containing Invalid should be added as participants
        self.assertEqual(campaign.running_participant_count, 4)
        self.assertEqual(
            set(campaign.participant_ids.mapped('res_id')),
            set((self.test_rec1 | self.test_rec2 | self.test_rec3 | self.test_rec4).ids)
        )
        self.assertEqual(set(campaign.participant_ids.mapped('state')), set(['running']))

        # Begin activity should contain a trace for each participant
        self.assertEqual(
            act_0.trace_ids.mapped('participant_id'),
            campaign.participant_ids,
        )
        self.assertEqual(set(act_0.trace_ids.mapped('state')), set(['scheduled']))
        self.assertEqual(set(act_0.trace_ids.mapped('schedule_date')), set([date]))

        # No other trace should have been created as the first one are waiting to be processed
        self.assertEqual(act_1.trace_ids, self.env['marketing.trace'])

        # First traces are processed, emails are sent
        with patch.object(IrMailServer, 'connect'):
            with patch.object(campaign.env.cr, 'commit'):
                campaign.execute_activities()

        self.assertEqual(set(act_0.trace_ids.mapped('state')), set(['processed']))

        # Child traces should have been generated for all traces of parent activity as filter is taken into account at processing, not generation
        self.assertEqual(
            set(act_1.trace_ids.mapped('participant_id.res_id')),
            set((self.test_rec1 | self.test_rec2 | self.test_rec3 | self.test_rec4).ids)
        )
        self.assertEqual(set(act_1.trace_ids.mapped('state')), set(['scheduled']))
        self.assertEqual(set(act_1.trace_ids.mapped('schedule_date')), set([date + relativedelta(hours=1)]))

        # Traces are processed, but this is not the time to execute child traces
        with patch.object(campaign.env.cr, 'commit'):
            campaign.execute_activities()
        self.assertEqual(set(act_1.trace_ids.mapped('state')), set(['scheduled']))

        # Time is coming, a bit like the winter
        date = Datetime.from_string('2014-08-01 17:02:32')  # wow, a two hour span ! so much incredible !
        self.mock_datetime.now.return_value = date
        self.mock_datetime2.now.return_value = date

        with patch.object(campaign.env.cr, 'commit'):
            campaign.execute_activities()
        # There should be one rejected activity not matching the filter
        self.assertEqual(
            set(act_1.trace_ids.filtered(lambda tr: tr.participant_id.res_id != self.test_rec4.id).mapped('state')),
            set(['processed'])
        )
        self.assertEqual(
            set(act_1.trace_ids.filtered(lambda tr: tr.participant_id.res_id == self.test_rec4.id).mapped('state')),
            set(['rejected'])
        )
        # Check server action was actually processed
        self.assertTrue([
            'SA' in record.name
            for record in self.test_rec1 | self.test_rec2 | self.test_rec3])
        self.assertTrue([
            'SA' not in record.name
            for record in self.test_rec4])

    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_unique_field_many2one(self):
        self.test_rec3.write({'partner_id': self.test_partner2.id})

        Campaign = self.env['marketing.campaign'].with_user(self.user_market)
        Activity = self.env['marketing.activity'].with_user(self.user_market)
        MassMail = self.env['mailing.mailing'].with_user(self.user_market)

        partner_field = self.env['ir.model.fields'].search(
            [('model_id', '=', self.test_model.id), ('name', '=', 'partner_id')])

        campaign = Campaign.create({
            'name': 'My First Campaign',
            'model_id': self.test_model.id,
            'domain': '%s' % ([('name', '!=', 'Invalid')]),
            'unique_field_id': partner_field.id,
        })

        mass_mailing = MassMail.create({
            'name': 'Hello',
            'subject': 'Hello',
            'body_html': '<div>My Email Body</div>',
            'mailing_model_id': self.test_model.id,
            'use_in_marketing_automation': True,
        })
        act_0 = Activity.create({
            'name': 'Enter the campaign',
            'campaign_id': campaign.id,
            'activity_type': 'email',
            'mass_mailing_id': mass_mailing.id,
            'trigger_type': 'begin',
            'interval_number': '0',
        })

        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 2)
        self.assertEqual(
            self.TestModel.browse(campaign.participant_ids.mapped('res_id')).mapped(partner_field.name),
            (self.test_rec1 | self.test_rec2).mapped(partner_field.name)
        )

        self.test_rec_new = self.TestModel.create({'name': 'Test_New', 'partner_id': self.test_partner3.id})
        self.test_rec_old = self.TestModel.create({'name': 'Test_Old', 'partner_id': self.test_partner2.id})
        campaign.sync_participants()

        self.assertEqual(campaign.running_participant_count, 3)
        self.assertEqual(
            self.TestModel.browse(campaign.participant_ids.mapped('res_id')).mapped(partner_field.name),
            (self.test_rec1 | self.test_rec2 | self.test_rec_new).mapped(partner_field.name)
        )

    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_unique_field(self):
        Campaign = self.env['marketing.campaign'].with_user(self.user_market)
        Activity = self.env['marketing.activity'].with_user(self.user_market)
        MassMail = self.env['mailing.mailing'].with_user(self.user_market)

        name_field = self.env['ir.model.fields'].search(
            [('model_id', '=', self.test_model.id), ('name', '=', 'display_name')])

        campaign = Campaign.create({
            'name': 'My First Campaign',
            'model_id': self.test_model.id,
            'domain': '%s' % ([('name', '!=', 'Invalid')]),
            'unique_field_id': name_field.id,
        })

        mass_mailing = MassMail.create({
            'name': 'Hello',
            'subject': 'Hello',
            'body_html': '<div>My Email Body</div>',
            'mailing_model_id': self.test_model.id,
            'use_in_marketing_automation': True,
        })
        act_0 = Activity.create({
            'name': 'Enter the campaign',
            'campaign_id': campaign.id,
            'activity_type': 'email',
            'mass_mailing_id': mass_mailing.id,
            'trigger_type': 'begin',
            'interval_number': '0',
        })

        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')
        campaign.sync_participants()

        first_recordset = self.test_rec1 | self.test_rec2 | self.test_rec3 | self.test_rec4

        self.assertEqual(campaign.running_participant_count, 4)
        self.assertEqual(
            set(self.TestModel.browse(campaign.participant_ids.mapped('res_id')).mapped(name_field.name)),
            set(first_recordset.mapped(name_field.name))
        )

        self.test_rec_new = self.TestModel.create({'name': 'Test_4'})
        self.test_rec_old = self.TestModel.create({'name': 'Test_1'})
        campaign.sync_participants()

        # the record with a new value should have been added, not the other
        self.assertEqual(campaign.running_participant_count, 5)
        self.assertEqual(
            set(self.TestModel.browse(campaign.participant_ids.mapped('res_id')).mapped(name_field.name)),
            set((first_recordset | self.test_rec_new).mapped(name_field.name))
        )

    @mute_logger('odoo.addons.base.ir.ir_model', 'odoo.models')
    def test_campaign_duplicate(self):
        """
        The copy/duplicate of a campaign :
            - COPY activities, new activities related to the new campaign
            - DO NOT COPY the recipients AND the trace_ids AND the state (draft by default)
            - Normal Copy of other fields
            - Copy child of activity and keep coherence in parent_id
        """
        Campaign = self.env['marketing.campaign'].with_user(self.user_market)
        Activity = self.env['marketing.activity'].with_user(self.user_market)
        MassMail = self.env['mailing.mailing'].with_user(self.user_market)

        # Create campaign
        campaign = Campaign.create({
            'name': 'COPY CAMPAIGN',
            'model_id': self.test_model.id,
            'domain': '%s' % ([('name', '!=', 'Invalid')]),
        })

        # Create first activity flow
        mass_mailing = MassMail.create({
            'name': 'Hello',
            'subject': 'Hello',
            'body_html': '<div>My Email Body</div>',
            'mailing_model_id': self.test_model.id,
            'use_in_marketing_automation': True,
        })
        name_activity = "Name of the activity (2 after the duplicate with the same name)"
        act_0 = Activity.create({
            'name': name_activity,
            'campaign_id': campaign.id,
            'activity_type': 'email',
            'mass_mailing_id': mass_mailing.id,
            'trigger_type': 'begin',
            'interval_number': '0',
        })

        child_act_1 = Activity.create({
            'name': 'child_activity',
            'campaign_id': campaign.id,
            'activity_type': 'email',
            'mass_mailing_id': mass_mailing.id,
            'parent_id': act_0.id,
            'trigger_type': 'act',
            'interval_number': '1',
            'interval_type': 'hours',
        })

        self.assertEqual(int(Activity.search_count([('name', '=', name_activity)])), 1)

        # User starts and syncs its campaign
        campaign.action_start_campaign()
        self.assertEqual(campaign.state, 'running')
        campaign.sync_participants()

        # Begin activity should contain a trace for each participant (4)
        self.assertEqual(
            act_0.trace_ids.mapped('participant_id'),
            campaign.participant_ids,
        )

        campaign2 = campaign.copy()

        # Check if campaign activities is unchanged
        self.assertEqual(len(campaign.marketing_activity_ids), 2)

        # Two activities with the same name but not related to the same campaign
        self.assertEqual(int(Activity.search_count([('name', '=', name_activity)])), 2)
        self.assertEqual(len(campaign2.marketing_activity_ids), 2)

        # The copied child activity has not the old activity as parent,
        # but the new one
        self.assertTrue(
            campaign2.marketing_activity_ids[1].parent_id,
            campaign2.marketing_activity_ids[0])

        # State = draft
        self.assertEqual(campaign2.state, 'draft')

        act_0_copy = campaign2.marketing_activity_ids[0]
        # No participant and no trace (in the activity) is copied
        self.assertEqual(len(campaign2.participant_ids), 0)
        self.assertEqual(len(act_0_copy.trace_ids), 0)
