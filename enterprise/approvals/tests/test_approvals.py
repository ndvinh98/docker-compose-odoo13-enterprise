# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import common
from odoo.exceptions import UserError


class TestRequest(common.TransactionCase):
    def test_compute_request_status(self):
        category_test = self.env['approval.category'].browse(1)
        record = self.env['approval.request'].create({
            'name': 'test request',
            'category_id': category_test.id,
            'date_start': fields.Datetime.now(),
            'date_end': fields.Datetime.now(),
            'location': 'testland'
        })
        first_approver = self.env['approval.approver'].create({
            'user_id': 1,
            'request_id': record.id,
            'status': 'new'})
        second_approver = self.env['approval.approver'].create({
            'user_id': 2,
            'request_id': record.id,
            'status': 'new'})
        record.approver_ids += first_approver
        record.approver_ids += second_approver

        self.assertEqual(record.request_status, 'new')

        record.action_confirm()

        # Test case 1: Min approval = 1
        self.assertEqual(record.request_status, 'pending')
        record.action_approve(first_approver)
        self.assertEqual(record.request_status, 'approved')
        record.action_approve(second_approver)
        self.assertEqual(record.request_status, 'approved')
        record.action_withdraw(first_approver)
        self.assertEqual(record.request_status, 'approved')
        record.action_refuse(first_approver)
        self.assertEqual(record.request_status, 'refused')

        # Test case 2: Min approval = 1
        category_test.approval_minimum = 2
        record.action_withdraw(first_approver)
        record.action_withdraw(second_approver)
        self.assertEqual(record.request_status, 'pending')
        record.action_approve(first_approver)
        self.assertEqual(record.request_status, 'pending')
        record.action_approve(second_approver)
        self.assertEqual(record.request_status, 'approved')
        record.action_withdraw(second_approver)
        self.assertEqual(record.request_status, 'pending')
        record.action_refuse(second_approver)
        self.assertEqual(record.request_status, 'refused')

        # Test case 3: Check that cancel is erasing the old validations
        record.action_cancel()
        self.assertEqual(first_approver.status, 'cancel')
        self.assertEqual(second_approver.status, 'cancel')
        self.assertEqual(record.request_status, 'cancel')

        # Test case 4: Set the approval request to draft
        record.action_draft()
        self.assertEqual(first_approver.status, 'new')
        self.assertEqual(second_approver.status, 'new')
        self.assertEqual(record.request_status, 'new')

        # Test case 5: Set min approval to an impossible value to reach
        category_test.approval_minimum = 3
        with self.assertRaises(UserError):
            record.action_confirm()
        self.assertEqual(record.request_status, 'new')
