# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime, date

from .common import TestCommonPlanning

import unittest
from odoo.exceptions import UserError


class TestRecurrencySlotGeneration(TestCommonPlanning):

    @classmethod
    def setUpClass(cls):
        super(TestRecurrencySlotGeneration, cls).setUpClass()
        cls.setUpEmployees()

    def configure_recurrency_span(self, span_qty):
        self.env.company.write({
            'planning_generation_interval': span_qty,
        })

    # ---------------------------------------------------------
    # Repeat "until" mode
    # ---------------------------------------------------------

    def test_repeat_until(self):
        """ Normal case: Test slots get repeated at the right time with company limit
            company_span:           2 weeks
            first run:
                now :                   6/27/2019
                initial_start :         6/27/2019
                repeat_end :            7/11/2019  now + 2 weeks
                generated slots:
                                        6/27/2019
                                        7/4/2019
                                        NOT 7/11/2019 because it hits the soft limit
            1st cron
                now :                   7/11/2019  2 weeks later
                last generated start :  7/4/2019
                repeat_end :            7/25/2019  now + 2 weeks
                generated_slots:
                                        7/11/2019
                                        7/18/2019
                                        NOT 7/25/2019 because it hits the soft limit
        """
        with self._patch_now('2019-06-27 08:00:00'):
            self.configure_recurrency_span(1)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            # repeat once, since repeat span is two week and there's no repeat until, we should have 2 slot
            # because we hit the 'soft_limit'
            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 27, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'until',
                'repeat_until': datetime(2022, 6, 27, 17, 0, 0),
                'repeat_interval': 1,
            })

            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 5, 'initial run should have created 2 slots')
            # TODO JEM: check same employee, attached to same reccurrence, same role, ...

        # now run cron two weeks later, should yield two more slots
        with self._patch_now('2019-07-11 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 7, 'first cron run should have generated 2 more forecasts')

    def test_repeat_until_no_repeat(self):
        """create a recurrency with repeat until set which is less than next cron span, should
            stop repeating upon creation
            company_span:           2 weeks
            first run:
                now :                   6/27/2019
                initial_start :         6/27/2019
                repeat_end :            6/29/2019  recurrency's repeat_until
                generated slots:
                                        6/27/2019
                                        NOT 7/4/2019 because it hits the recurrency's repeat_until
        """
        with self._patch_now('2019-06-27 08:00:00'):

            self.configure_recurrency_span(1)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 27, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'until',
                'repeat_interval': 1,
                'repeat_until': datetime(2019, 6, 29, 8, 0, 0),
            })

            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 1, 'first run should only have created 1 slot since repeat until is set at 1 week')

    def test_repeat_until_cron_idempotent(self):
        """Create a recurrency with repeat_until set, it allows a full first run, but not on next cron
            first run:
                now :                   6/27/2019
                initial_start :         6/27/2019
                repeat_end :            7/11/2019  recurrency's repeat_until
                generated slots:
                                        6/27/2019
                                        7/4/2019
                                        NOT 7/11/2019 because it hits the recurrency's repeat_until
            first cron:
                now:                    7/12/2019
                last generated start:   7/4/2019
                repeat_end:             7/11/2019  still recurrency's repeat_until
                generated slots:
                                        NOT 7/11/2019 because it still hits the repeat end
        """
        with self._patch_now('2019-06-27 08:00:00'):
            self.configure_recurrency_span(1)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            # repeat until is big enough for the first pass to generate all 2 slots
            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 27, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'until',
                'repeat_interval': 1,
                'repeat_until': datetime(2019, 7, 11, 8, 0, 0),
            })
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 2, 'initial run should have generated 2 slots')

            # run the cron, since last generated slot almost hits the repeat until, there won't be more. still two left
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 2, 'runing the cron right after do not generate new slots because of repeat until')

    def test_repeat_until_cron_generation(self):
        """Generate a recurrence with repeat_until that allow first run, then first cron, but shouldn't
            keep generating slots on the second
            first run:
                now :                   8/31/2019
                initial_start :         9/1/2019
                repeat_end :            forever
                generated slots:
                                        9/1/2019
                                        9/8/2019
                                        9/15/2019
                                        9/22/2019
                                        9/29/2019
            first cron:
                now:                    9/14/2019  two weeks later
                repeat_end:             forever
                generated slots:
                                        9/1/2019
                                        9/8/2019
                                        9/15/2019
                                        9/22/2019
                                        9/29/2019
                                        10/6/2019
                                        10/13/2019
            second cron:
                now:                    9/16/2019  two days later
                last generated start:   10/13/2019
                repeat_end:             forever
                generated slots:
                                        NOT 10/20/2019 because all recurring slots are already generated in the company interval
        """
        with self._patch_now('2019-08-31 08:00:00'):
            self.configure_recurrency_span(1)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            # first run, two slots generated
            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 9, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 9, 1, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'forever',
                'repeat_interval': 1,
                'repeat_until': False,
            })
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 5, 'first run should have geenrated 2 slots')
        # run the cron, since last generated slot do not hit the repeat until, there will be 2 more
        with self._patch_now('2019-09-14 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 7, 'first cron should have generated 2 more slot')
        # run the cron again, since last generated slot do hit the repeat until, there won't be more
        with self._patch_now('2019-09-16 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 7, 'second cron has not generated any foreasts because of repeat until')

    def test_repeat_until_long_limit(self):
        """Since the recurrency cron is meant to run every week, make sure generation works accordingly when
            the company's repeat span is much larger
            first run:
                now :                   6/1/2019
                initial_start :         6/1/2019
                repeat_end :            12/1/2019  initial_start + 6 months
                generated slots:
                                        6/1/2019
                                        ...
                                        11/30/2019  (27 items)
            first cron:
                now:                    6/8/2019
                last generated start    11/30/2019
                repeat_end              12/8/2019
                generated slots:
                                        12/7/2019
            only one slot generated: since we are one week later, repeat_end is only one week later and slots are generated every week.
            So there is just enough room for one.
            This ensure slots are always generated up to x time in advance with x being the company's repeat span
        """
        with self._patch_now('2019-06-01 08:00:00'):
            self.configure_recurrency_span(6)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 1, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'until',
                'repeat_interval': 1,
                'repeat_until': datetime(2020, 7, 25, 8, 0, 0),
            })
            # over 6 month, we should have generated 27 slots
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 27, 'first run has generated 27 slots')
        # one week later, always having the slots generated 6 months in advance means we
        # have generated one more, which makes 28
        with self._patch_now('2019-06-08 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 28, 'second cron only has generated 1 more slot because of company span')

    def test_repeat_forever(self):
        """ Since the recurrency cron is meant to run every week, make sure generation works accordingly when
            both the company's repeat span and the repeat interval are much larger
            Company's span is 6 months and repeat_interval is 1 month
            first run:
                now :                   6/1/2019
                initial_start :         6/1/2019
                repeat_end :            12/1/2019  initial_start + 6 months
                generated slots:
                                        6/1/2019
                                        ...
                                        11/1/2019  (27 items)
            first cron:
                now:                    6/8/2019
                last generated start    11/30/2019
                repeat_end              12/8/2019
                generated slots:
                                        12/1/2019
            second cron:
                now:                    6/15/2019
                last generated start    12/1/2019
                repeat_end              12/15/2019
                generated slots:
                                        N/A (we are still 6 months in advance)
        """
        with self._patch_now('2019-06-01 08:00:00'):
            self.configure_recurrency_span(6)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 1, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'forever',
                'repeat_interval': 1,
            })

            # over 6 month, we should have generated 6 slots
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 27, 'first run has generated 6 slots')

        # one week later, always having the slots generated 6 months in advance means we
        # have generated one more, which makes 7
        with self._patch_now('2019-06-08 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 28, 'first cron generated one more slot')

        # again one week later, we are now up-to-date so there should still be 7 slots
        with self._patch_now('2019-06-15 08:00:00'):
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 29, 'second run has not generated any forecats because of company span')

    @unittest.skip
    def kkktest_slot_remove_all(self):
        with self._patch_now('2019-06-01 08:00:00'):
            self.configure_recurrency_span(6)
            initial_start_dt = datetime(2019, 6, 1, 8, 0, 0)
            initial_end_dt = datetime(2019, 6, 1, 17, 0, 0)
            slot_values = {
                'employee_id': self.employee_joseph.id,
            }

            recurrency = self.env['planning.recurrency'].create({
                'repeat_interval': 1,
            })
            self.assertFalse(self.get_by_employee(self.employee_joseph))
            recurrency.create_slot(initial_start_dt, initial_end_dt, slot_values)

            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 27, 'first run has generated 27 slots')
            recurrency.action_remove_all()
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 0, 'calling remove after on any slot from the recurrency remove all slots linked to the recurrency')

    # ---------------------------------------------------------
    # Recurring Slot Misc
    # ---------------------------------------------------------

    def test_recurring_slot_company(self):
        with self._patch_now('2019-06-01 08:00:00'):
            initial_company = self.env['res.company'].create({'name': 'original'})
            initial_company.write({
                'planning_generation_interval': 2,
            })
            # Should be able to create a slot with a company_id != employee.company_id
            slot1 = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 1, 17, 0, 0),
                'employee_id': self.employee_bert.id,
                'repeat': True,
                'repeat_type': 'forever',
                'repeat_interval': 1,
                'company_id': initial_company.id,
            })

            # put the employee in the second company
            self.employee_bert.write({'company_id': initial_company.id})

            slot1 = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 1, 17, 0, 0),
                'employee_id': self.employee_bert.id,
                'repeat': True,
                'repeat_type': 'forever',
                'repeat_interval': 1,
                'company_id': initial_company.id,
            })

            other_company = self.env['res.company'].create({'name': 'other'})
            other_company.write({
                'planning_generation_interval': 1,
            })
            self.employee_joseph.write({'company_id': other_company.id})
            slot2 = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 1, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 1, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'forever',
                'repeat_interval': 1,
                'company_id': other_company.id,
            })

            # initial company's recurrency should have created 9 slots since it's span is two month
            # other company's recurrency should have create 5 slots since it's span is one month
            self.assertEqual(len(self.get_by_employee(self.employee_bert)), 18, 'initial company\'s span is two month, so 2 * 9 slots')
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 5, 'other company\'s span is one month, so only 5 slots')

            self.assertEqual(slot1.company_id, slot1.recurrency_id.company_id, "Recurrence and slots (1) must have the same company")
            self.assertEqual(slot1.recurrency_id.company_id, slot1.recurrency_id.slot_ids.mapped('company_id'), "All slots in the same recurrence (1) must have the same company")
            self.assertEqual(slot2.company_id, slot2.recurrency_id.company_id, "Recurrence and slots (2) must have the same company")
            self.assertEqual(slot2.recurrency_id.company_id, slot2.recurrency_id.slot_ids.mapped('company_id'), "All slots in the same recurrence (1) must have the same company")

    def test_slot_detach_if_some_fields_change(self):
        with self._patch_now('2019-06-27 08:00:00'):
            self.configure_recurrency_span(1)

            self.assertFalse(self.get_by_employee(self.employee_joseph))

            slot = self.env['planning.slot'].create({
                'start_datetime': datetime(2019, 6, 27, 8, 0, 0),
                'end_datetime': datetime(2019, 6, 27, 17, 0, 0),
                'employee_id': self.employee_joseph.id,
                'repeat': True,
                'repeat_type': 'until',
                'repeat_until': datetime(2019, 9, 27, 17, 0, 0),  # 3 months
                'repeat_interval': 1,
            })
            recurrence = slot.recurrency_id

            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), 5)
            self.assertEqual(len(self.get_by_employee(self.employee_joseph)), len(recurrence.slot_ids), 'the recurrency has generated 5 slots')

            self.get_by_employee(self.employee_joseph)[0].write({'employee_id': self.employee_bert.id})

            self.assertEqual(len(recurrence.slot_ids), 4, 'writing on the slot detach it from the recurrency')

    def test_empty_recurrency(self):
        """ Check empty recurrency is removed by cron """
        with self._patch_now('2020-06-27 08:00:00'):
            self.env['planning.recurrency'].create({
                'repeat_interval': 1,
                'repeat_type': 'forever',
                'repeat_until': False,
                'last_generated_end_datetime': datetime(2019, 6, 27, 8, 0, 0)
            })

            self.assertEqual(len(self.env['planning.recurrency'].search([])), 1)
            self.env['planning.recurrency']._cron_schedule_next()
            self.assertFalse(len(self.env['planning.recurrency'].search([])), 'cron with no slot gets deleted (there is no original slot to copy from)')
