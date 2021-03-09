# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details
from datetime import datetime, timedelta

from odoo.exceptions import ValidationError

from .common import TestCommonForecast
from odoo import tools


class TestForecastCreationAndEditing(TestCommonForecast):

    @classmethod
    def setUpClass(cls):
        super(TestForecastCreationAndEditing, cls).setUpClass()

        cls.setUpEmployees()
        cls.setUpProjects()

    def test_creating_a_planning_shift_allocated_hours_are_correct(self):
        values = {
            'project_id': self.project_opera.id,
            'employee_id': self.employee_bert.id,
            'allocated_hours': 8,
            'start_datetime': datetime(2019, 6, 6, 8, 0, 0),  # 6/6/2019 is a tuesday, so a working day
            'end_datetime': datetime(2019, 6, 6, 17, 0, 0),
            'allocated_percentage': 100,
        }

        # planning_shift on one day (planning mode)
        planning_shift = self.env['planning.slot'].create(values)
        self.assertEqual(planning_shift.allocated_hours, 9.0, 'resource hours should be a full workday')

        planning_shift.write({'allocated_percentage': 50})
        self.assertEqual(planning_shift.allocated_hours, 4.5, 'resource hours should be a half duration')

        # planning_shift on non working days
        values = {
            'allocated_percentage': 100,
            'start_datetime': datetime(2019, 6, 2, 8, 0, 0),  # sunday morning
            'end_datetime': datetime(2019, 6, 2, 17, 0, 0)  # sunday evening, same sunday, so employee is not working
        }
        planning_shift.write(values)

        self.assertEqual(planning_shift.allocated_hours, 9, 'resource hours should be a full day working hours')

        # planning_shift on multiple days (forecast mode)
        values = {
            'allocated_percentage': 100,   # full week
            'start_datetime': datetime(2019, 6, 3, 0, 0, 0),  # 6/3/2019 is a monday
            'end_datetime': datetime(2019, 6, 8, 23, 59, 0)  # 6/8/2019 is a sunday, so we have a full week
        }
        planning_shift.write(values)

        self.assertEqual(planning_shift.allocated_hours, 40, 'resource hours should be a full week\'s available hours')

    def test_task_in_project(self):
        values = {
            'project_id': self.project_opera.id,
            'task_id': self.task_horizon_dawn.id,  # oops, task_horizon_dawn is into another project
            'employee_id': self.employee_bert.id,
            'allocated_hours': 8,
            'start_datetime': datetime(2019, 6, 2, 8, 0, 0),
            'end_datetime': datetime(2019, 6, 2, 17, 0, 0)
        }
        with self.assertRaises(ValidationError, msg="""it should not be possible to create a planning_shift
                                                    linked to a task that is in another project
                                                    than the one linked to the planning_shift"""):
            self.env['planning.slot'].create(values)
