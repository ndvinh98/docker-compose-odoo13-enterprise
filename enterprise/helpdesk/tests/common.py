# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from contextlib import contextmanager

from odoo import fields
from odoo.tests.common import SavepointCase
from odoo import fields


class HelpdeskCommon(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(HelpdeskCommon, cls).setUpClass()

        # we create a helpdesk user and a manager
        Users = cls.env['res.users'].with_context(tracking_disable=True)
        cls.main_company_id = cls.env.ref('base.main_company').id
        cls.helpdesk_manager = Users.create({
            'company_id': cls.main_company_id,
            'name': 'Helpdesk Manager',
            'login': 'hm',
            'email': 'hm@example.com',
            'groups_id': [(6, 0, [cls.env.ref('helpdesk.group_helpdesk_manager').id])]
        })
        cls.helpdesk_user = Users.create({
            'company_id': cls.main_company_id,
            'name': 'Helpdesk User',
            'login': 'hu',
            'email': 'hu@example.com',
            'groups_id': [(6, 0, [cls.env.ref('helpdesk.group_helpdesk_user').id])]
        })
        # the manager defines a team for our tests (the .sudo() at the end is to avoid potential uid problems)
        cls.test_team = cls.env['helpdesk.team'].with_user(cls.helpdesk_manager).create({'name': 'Test Team'}).sudo()
        # He then defines its stages
        stage_as_manager = cls.env['helpdesk.stage'].with_user(cls.helpdesk_manager)
        cls.stage_new = stage_as_manager.create({
            'name': 'New',
            'sequence': 10,
            'team_ids': [(4, cls.test_team.id, 0)],
            'is_close': False,
        })
        cls.stage_progress = stage_as_manager.create({
            'name': 'In Progress',
            'sequence': 20,
            'team_ids': [(4, cls.test_team.id, 0)],
            'is_close': False,
        })
        cls.stage_done = stage_as_manager.create({
            'name': 'Done',
            'sequence': 30,
            'team_ids': [(4, cls.test_team.id, 0)],
            'is_close': True,
        })
        cls.stage_cancel = stage_as_manager.create({
            'name': 'Cancelled',
            'sequence': 40,
            'team_ids': [(4, cls.test_team.id, 0)],
            'is_close': True,
        })

        # He also creates a ticket types for Question and Issue
        cls.type_question = cls.env['helpdesk.ticket.type'].with_user(cls.helpdesk_manager).create({
            'name': 'Question_test',
        }).sudo()
        cls.type_issue = cls.env['helpdesk.ticket.type'].with_user(cls.helpdesk_manager).create({
            'name': 'Issue_test',
        }).sudo()

    @classmethod
    def setUpSLATeam(cls):
        """ Generate Team, some stage and SLAs for the team """
        # create team and stages
        cls.team_with_sla = cls.env['helpdesk.team'].create({
            'name': 'Team with SLAs',
            'use_sla': True
        })

        Stage = cls.env['helpdesk.stage']
        cls.team_sla_stage_new = Stage.create({
            'name': 'New',
            'sequence': 10,
            'team_ids': [(4, cls.team_with_sla.id, 0)],
            'is_close': False,
        })
        cls.team_sla_stage_progress = Stage.create({
            'name': 'In Progress',
            'sequence': 20,
            'team_ids': [(4, cls.team_with_sla.id, 0)],
            'is_close': False,
        })
        cls.team_sla_stage_done = Stage.create({
            'name': 'Done',
            'sequence': 30,
            'team_ids': [(4, cls.team_with_sla.id, 0)],
            'is_close': True,
        })
        cls.team_sla_stage_cancel = Stage.create({
            'name': 'Cancelled',
            'sequence': 40,
            'team_ids': [(4, cls.team_with_sla.id, 0)],
            'is_close': True,
        })

        # create SLAs
        SLA = cls.env['helpdesk.sla']
        cls.sla_1_progress = SLA.create({
            'name': "2 days to be in progress",
            'stage_id': cls.team_sla_stage_progress.id,
            'time_days': 2,
            'team_id': cls.team_with_sla.id,
        })
        cls.sla_2_done = SLA.create({
            'name': "7 days to be in progress",
            'stage_id': cls.team_sla_stage_done.id,
            'time_days': 7,
            'team_id': cls.team_with_sla.id,
            'priority': '0',
        })
        cls.sla_3_done_prior = SLA.create({
            'name': "5 days to be in done for 3 stars ticket",
            'stage_id': cls.team_sla_stage_done.id,
            'time_days': 5,
            'team_id': cls.team_with_sla.id,
            'priority': '3',
        })

    def _utils_set_create_date(self, records, date_str):
        """ This method is a hack in order to be able to define/redefine the create_date
            of the any recordset. This is done in SQL because ORM does not allow to write
            onto the create_date field.
            :param records: recordset of any odoo models
        """
        query = """
            UPDATE %s
            SET create_date = %%s
            WHERE id IN %%s
        """ % (records._table,)
        self.env.cr.execute(query, (date_str, tuple(records.ids)))

        records.invalidate_cache()

        if records._name == 'helpdesk.ticket':
            field = self.env['helpdesk.sla.status']._fields['deadline']
            self.env.add_to_compute(field, records.sla_status_ids)
            records.recompute()

    @contextmanager
    def _ticket_patch_now(self, datetime_str):
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
