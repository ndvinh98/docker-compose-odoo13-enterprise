# -*- coding: utf-8 -*-
from odoo.addons.website_crm_score.tests.common import TestScoring
from odoo.tools import mute_logger


class test_assign(TestScoring):

    @mute_logger('odoo.addons.base.models.ir_model', 'odoo.models')
    def test_00_assign(self):
        all_lead_ids = [self.lead0, self.lead1, self.lead2, self.lead3, self.lead4, self.lead5]

        count = self.crm_lead.search_count([('id', 'in', all_lead_ids)])
        self.assertEqual(count, len(all_lead_ids), 'Some leads are missing for test %s vs %s' % (count, len(all_lead_ids)))
        # scoring
        self.website_crm_score.assign_scores_to_leads()

        [l2] = self.crm_lead.browse(self.lead2).read(['score', 'active'])
        [l3] = self.crm_lead.browse(self.lead3).with_context(dict(test_active=False)).read(['score', 'active'])

        self.assertEqual(l2['score'], 0, 'scoring failed')
        self.assertEqual(l2['active'], True, ' should NOT be archived')
        self.assertEqual(l3['active'], False, ' should be archived')

        count = self.crm_lead.search_count([('id', 'in', all_lead_ids)])
        self.assertEqual(count, len(all_lead_ids) - 2, 'One lead should be deleted and one archived')

        # assignation
        self.team.direct_assign_leads()

        [l0] = self.crm_lead.browse(self.lead0).read(['team_id', 'user_id'])
        [l1] = self.crm_lead.browse(self.lead1).read(['team_id', 'user_id'])
        [l2] = self.crm_lead.browse(self.lead2).read(['team_id', 'user_id'])
        [l5] = self.crm_lead.browse(self.lead5).read(['team_id', 'user_id'])

        self.assertEqual(l0['team_id'] and l0['team_id'][0], self.team0, 'assignation failed')
        self.assertEqual(l1['team_id'] and l1['team_id'][0], self.team1, 'assignation failed')
        self.assertEqual(l2['team_id'], False, 'assignation failed')
        self.assertEqual(l5['team_id'], False, 'assignation failed, less 1h')

        self.assertEqual(l0['user_id'] and l0['user_id'][0], self.salesmen0, 'assignation failed')
        self.assertEqual(l1['user_id'] and l1['user_id'][0], self.salesmen1, 'assignation failed')
        self.assertEqual(l2['user_id'], False, 'assignation failed')
        self.assertEqual(l5['user_id'], False, 'assignation failed, less 1h')
