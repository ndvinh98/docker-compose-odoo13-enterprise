# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from contextlib import contextmanager

from odoo import fields

from odoo.tests.common import SavepointCase


class TestCommonPlanning(SavepointCase):

    @contextmanager
    def _patch_now(self, datetime_str):
        datetime_now_old = getattr(fields.Datetime, 'now')
        datetime_today_old = getattr(fields.Datetime, 'today')

        def new_now():
            return fields.Datetime.from_string(datetime_str)

        def new_today():
            return fields.Datetime.from_string(datetime_str).replace(hour=0, minute=0, second=0)

        try:
            setattr(fields.Datetime, 'now', new_now)
            setattr(fields.Datetime, 'today', new_today)

            yield
        finally:
            # back
            setattr(fields.Datetime, 'now', datetime_now_old)
            setattr(fields.Datetime, 'today', datetime_today_old)

    def get_by_employee(self, employee):
        return self.env['planning.slot'].search([('employee_id', '=', employee.id)])

    @classmethod
    def setUpEmployees(cls):
        cls.employee_joseph = cls.env['hr.employee'].create({
            'name': 'joseph',
            'work_email': 'joseph@a.be',
            'tz': 'UTC'
        })
        cls.employee_bert = cls.env['hr.employee'].create({
            'name': 'bert',
            'work_email': 'bert@a.be',
            'tz': 'UTC'
        })
