# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime, date
from odoo.addons.planning.tests.common import TestCommonPlanning


class TestRecurrencySlotGeneration(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super(TestRecurrencySlotGeneration, cls).setUpClass()
        cls.setUpEmployees()

        cls.recurrency = cls.env['planning.recurrency'].create({
            'repeat_interval': 1,
            'repeat_unit': 'week',
        })

        cls.env['planning.slot'].create({
            'employee_id': cls.employee_bert.id,
            'start_datetime': datetime(2019, 6, 2, 8, 0),
            'end_datetime': datetime(2019, 6, 2, 17, 0),
        })
        cls.env['planning.slot'].create({
            'employee_id': cls.employee_bert.id,
            'start_datetime': datetime(2019, 6, 4, 8, 0),
            'end_datetime': datetime(2019, 6, 5, 17, 0),
        })

        cls.env['planning.slot'].create({
            'employee_id': cls.employee_bert.id,
            'start_datetime': datetime(2019, 6, 3, 8, 0),
            'end_datetime': datetime(2019, 6, 3, 17, 0),
            'recurrency_id': cls.recurrency.id
        })

    def test_dont_duplicate_recurring_slots(self):
        """Original week :  6/2/2019 -> 6/8/2019
           Destination week : 6/9/2019 -> 6/15/2019
            slots:
                6/2/2019 08:00 -> 6/2/2019 17:00
                6/4/2019 08:00 -> 6/5/2019 17:00
                6/3/2019 08:00 -> 6/3/2019 17:00 --> this one should be recurrent therefore not duplicated
        """
        employee = self.employee_bert

        self.assertEqual(len(self.get_by_employee(employee)), 3)

        self.env['planning.slot'].action_copy_previous_week(date(2019, 6, 9))

        self.assertEqual(len(self.get_by_employee(employee)), 5, 'duplicate has only duplicated slots that fit entirely in the period')

        duplicated_slots = self.env['planning.slot'].search([
            ('employee_id', '=', employee.id),
            ('start_datetime', '>', datetime(2019, 6, 9, 0, 0)),
            ('end_datetime', '<', datetime(2019, 6, 15, 23, 59)),
        ])
        self.assertEqual(len(duplicated_slots), 2, 'duplicate has only duplicated slots that fit entirely in the period')
