# # -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.addons.hr_referral.tests.common import TestHrReferralBase


class TestHrReferral(TestHrReferralBase):

    def test_referral_share_is_new(self):
        self.job_dev = self.job_dev.with_user(self.richard_user.id)

        self.env['hr.referral.link.to.share'].with_user(self.richard_user.id).create({'job_id': self.job_dev.id}).url
        links = self.env['link.tracker'].search([('campaign_id', '=', self.job_dev.utm_campaign_id.id)])
        self.assertEqual(len(links), 1, "It should have created only one link tracker")

        self.env['hr.referral.link.to.share'].with_user(self.steve_user.id).create({'job_id': self.job_dev.id}).url
        links = self.env['link.tracker'].search([('campaign_id', '=', self.job_dev.utm_campaign_id.id)])
        self.assertEqual(len(links), 2, "It should have created 2 different links tracker (one for each user)")

    def test_referral_change_referrer(self):
        # Create an applicant
        job_applicant = self.env['hr.applicant'].create({
            'name': 'Technical worker',
            'description': 'A nice job offer !',
            'job_id': self.job_dev.id,
            'ref_user_id': self.richard_user.id
        })
        self.assertEqual(job_applicant.ref_user_id, self.richard_user, "Referral is created with the right user")
        points_richard = self.env['hr.referral.points'].search([('ref_user_id', '=', self.richard_user.id)])
        self.assertEqual(job_applicant.stage_id.points, sum(points_richard.mapped('points')), "Right amount of referral points are created.")
        # We change the referrer on the job applicant, Richard will lose all his points and Steve will get points
        job_applicant.ref_user_id = self.steve_user.id
        self.assertEqual(job_applicant.ref_user_id, self.steve_user, "Referral is modified with as user Steve")
        points_richard = self.env['hr.referral.points'].search([('ref_user_id', '=', self.richard_user.id)])
        self.assertEqual(sum(points_richard.mapped('points')), 0, "Richard has no more points")
        points_steve = self.env['hr.referral.points'].search([('ref_user_id', '=', self.steve_user.id)])
        self.assertEqual(sum(points_steve.mapped('points')), job_applicant.stage_id.points, "Right amount of referral points are created for Steve")

    def test_referral_add_points(self):
        with self.assertRaises(UserError):
            self.mug_shop.sudo().buy()
        job_applicant = self.env['hr.applicant'].create({
            'name': 'Technical worker',
            'description': 'A nice applicant !',
            'job_id': self.job_dev.id,
            'ref_user_id': self.richard_user.id,
            'company_id': self.company_1.id
        })
        self.assertEqual(job_applicant.earned_points, job_applicant.stage_id.points, "Richard received points corresponding to the first stage.")
        stages = self.env['hr.recruitment.stage'].search([('job_ids', '=', False)])
        # We jump some stages of process, multiple points must be given
        job_applicant.stage_id = stages[-2]
        self.assertEqual(job_applicant.earned_points, sum(stages[:-1].mapped('points')), "Richard received points corresponding to the before last stage.")
        self.assertEqual(job_applicant.referral_state, 'progress', "Referral stay in progress")
        job_applicant.stage_id = stages[-1]
        self.assertEqual(job_applicant.earned_points, sum(stages.mapped('points')), "Richard received points corresponding to the last stage.")
        self.assertEqual(job_applicant.referral_state, 'hired', "Referral is hired")
        self.mug_shop.sudo().buy()
        shopped_item = self.env['hr.referral.points'].search([('ref_user_id', '=', self.richard_user.id), ('hr_referral_reward_id', '!=', False)])
        self.assertEqual(shopped_item.points, -self.mug_shop.cost, "The item bought decrease the number of points.")

    def test_referral_multi_company(self):
        self.job_dev = self.job_dev.with_user(self.richard_user.id)
        self.env['hr.referral.link.to.share'].with_user(self.richard_user.id).create({'job_id': self.job_dev.id}).url

        job_applicant = self.env['hr.applicant'].create({
            'name': 'Technical worker',
            'description': 'A nice applicant !',
            'job_id': self.job_dev.id,
            'source_id': self.richard_user.utm_source_id.id
        })

        self.assertEqual(job_applicant.ref_user_id, self.richard_user, "Referral is created with the right user")
        # self.assertEqual(job_applicant_2.ref_user_id, self.richard_user, "Referral is created with the right user")
        points_richard_c1 = self.env['hr.referral.points'].search([('ref_user_id', '=', self.richard_user.id), ('company_id', '=', self.company_1.id)])
        points_richard_c2 = self.env['hr.referral.points'].search([('ref_user_id', '=', self.richard_user.id), ('company_id', '=', self.company_2.id)])
        # All points are created for employee of company 1 as it's a job offer from company 1. No point in company 2.
        self.assertEqual(job_applicant.stage_id.points, sum(points_richard_c1.mapped('points')), "Right amount of referral points are created.")
        self.assertEqual(0, sum(points_richard_c2.mapped('points')), "Right amount of referral points are created.")

        # This user has no point in company 2 so if he miss as much points as the price of this object (this object is in company 2).
        self.assertEqual(self.red_mug_shop.points_missing, self.red_mug_shop.cost, "10 points are missing")
