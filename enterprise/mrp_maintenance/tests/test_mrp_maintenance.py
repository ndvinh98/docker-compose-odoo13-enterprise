# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import datetime, timedelta
from odoo.tests import common, Form


class TestMrpMaintenance(common.TransactionCase):

    def setUp(self):
        super(TestMrpMaintenance, self).setUp()

        # Relative models
        self.ResUsers = self.env['res.users']
        self.equipment = self.env['maintenance.equipment']

        # User references
        self.main_company = self.env.ref('base.main_company')
        self.technician_user_id = self.env.ref('base.user_root')
        self.maintenance_team_id = self.env.ref('maintenance.equipment_team_maintenance')
        self.stage_repaired_id = self.ref('maintenance.stage_3')
        self.stage_id = self.ref('maintenance.stage_0')
        self.category_id = self.env.ref('maintenance.equipment_monitor')

        # Create user
        self.user = self.ResUsers.create({
            'name': "employee",
            'company_id': self.main_company.id,
            'login': "employee",
            'email': "employee@yourcompany.example.com",
            'groups_id': [(6, 0, [self.ref('base.group_user')])]
        })

        # Create user with extra rights
        self.manager = self.ResUsers.create({
            'name': "Equipment Manager",
            'company_id': self.main_company.id,
            'login': "manager",
            'email': "eqmanager@yourcompany.example.com",
            'groups_id': [(6, 0, [self.ref('maintenance.group_equipment_manager')])]
        })

    # Create method for create a maintenance request
    def _create_request(self, name, request_date, equipment_id, maintenance_type):
        values = {
            'name': name,
            'request_date': request_date,
            'user_id': self.user.id,
            'owner_user_id': self.user.id,
            'equipment_id': equipment_id.id,
            'maintenance_type': maintenance_type,
            'stage_id': self.stage_id,
            'maintenance_team_id': self.maintenance_team_id.id,
        }
        return self.env['maintenance.request'].create(values)

    def test_00_mrp_maintenance(self):

        """ In order to check Next preventive maintenance date"""
        """
        ex:  equipment      =     Acer Laptop
             effective_date = 25-04-2018
             period         = 5

            preventive maintenance date = effective date + period
                30-04-2018              = 25-04-2018     + 5 days

            create maintenance request
                request_date  =  effective date + period
                30-04-2018    = 25-04-2018      + 5 days

            close maintenance request and calculate preventive maintenance date
            close_date = 05-05-2018

            preventive maintenance date = close_date + period
                10-05-2018              = 05-05-2018 + 5day
        """

        # Create a new equipment
        equipment_form = Form(self.equipment)
        equipment_form.name = 'Acer Laptop'
        equipment_form.maintenance_team_id = self.maintenance_team_id
        equipment_form.category_id = self.category_id
        equipment_form.technician_user_id = self.technician_user_id
        equipment_form.assign_date = time.strftime('%Y-%m-%d')
        equipment_form.serial_no = 'MT/127/18291015'
        equipment_form.expected_mtbf = 2
        equipment_form.effective_date = (datetime.now().date() + timedelta(days=5)).strftime("%Y-%m-%d")
        equipment_form.period = 5
        equipment_01 = equipment_form.save()

        # Check that equipment is created or not
        self.assertTrue(equipment_01, 'Equipment not created')

        # Check next preventive maintenance date = effective date + period
        self.assertEquals(equipment_01.next_action_date, datetime.now().date() + timedelta(days=10), 'Wrong next preventive maintenance date.')

        # Create a maintenance request
        maintenance_request_01 = self._create_request(name='Display not working', request_date=datetime.now().date() + timedelta(days=10), equipment_id=equipment_01, maintenance_type="preventive")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_01, 'Maintenance Request not created')

        # Check next preventive maintenance date when there is only one maintenance request created
        self.assertEquals(equipment_01.next_action_date, datetime.now().date() + timedelta(days=10), 'Wrong next preventive maintenance calculated when there is maintenance todo')

        # check maintenance request date.
        self.assertEquals(maintenance_request_01.request_date, datetime.now().date() + timedelta(days=10), 'maintenance request_date is wrong')

        # Updating maintenance to Done stage and its close date
        maintenance_request_01.write({'stage_id': self.stage_repaired_id})
        maintenance_request_01.close_date = datetime.now().date() + timedelta(days=15)

        # Now next preventive maintenance date = close date + period
        self.assertEquals(equipment_01.next_action_date, datetime.now().date() + timedelta(days=20), 'Wrong next preventive maintenance calculated when there is maintenance done')

        # Create another request which would be in maintenance todo stage
        maintenance_request_02 = self._create_request(name='Display not working', request_date=datetime.now().date() + timedelta(days=25), equipment_id=equipment_01, maintenance_type="preventive")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_02, 'Maintenance Request not created')

        # Check next preventive maintenance date
        self.assertEquals(equipment_01.next_action_date, datetime.now().date() + timedelta(days=25), 'Wrong next preventive maintenance calculated when there is one maintenance is done and another todo')

    def test_01_mrp_maintenance(self):
        """ In order to check MTBF,MTTR,estimated next failure and estimated
            latest failure equipment requests.
        """

        # Create a new equipment
        equipment_form = Form(self.equipment)
        equipment_form.name = 'Acer Laptop'
        equipment_form.maintenance_team_id = self.maintenance_team_id
        equipment_form.category_id = self.category_id
        equipment_form.technician_user_id = self.technician_user_id
        equipment_form.assign_date = time.strftime('%Y-%m-%d')
        equipment_form.serial_no = 'MT/127/18291015'
        equipment_form.expected_mtbf = 2
        equipment_form.effective_date = '2017-04-13'
        equipment_form.period = 5
        equipment_01 = equipment_form.save()

        # Check that equipment is created or not
        self.assertTrue(equipment_01, 'Equipment not created')

        # Create maintenance requests

        # Maintenance Request          Request Date
        #  1)                          2017-05-03
        #  2)                          2017-05-23
        #  3)                          2017-06-11

        maintenance_request_01 = self._create_request(name='Some keys are not working', request_date=datetime(2017, 5, 3).date(), equipment_id=equipment_01, maintenance_type="corrective")
        maintenance_request_02 = self._create_request(name='Touchpad not working', request_date=datetime(2017, 5, 23).date(), equipment_id=equipment_01, maintenance_type="corrective")
        maintenance_request_03 = self._create_request(name='Battery drains fast', request_date=datetime(2017, 6, 11).date(), equipment_id=equipment_01, maintenance_type="corrective")

        # check that maintenance_request is created or not
        self.assertTrue(maintenance_request_01, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_02, 'Maintenance Request not created')
        self.assertTrue(maintenance_request_03, 'Maintenance Request not created')

        # Request  Request Date  Close Date  diff_days
        #  1)      2017-05-03    2017-05-13     10
        #  2)      2017-05-23    2017-05-28      5
        #  3)      2017-06-11    2017-06-11      0

        # MTTR = Day used to handle maintenance request / No of request
        #   5  =            (10+5+0)15                  /    3

        #  MTBF = Gap in days of between effective date and last request / No of request
        #   19  = (2017-06-11 - 2017-04-13) 59                          /       3

        # estimated next failure = latest failure date + MTBF
        # 2017-06-30 00:00:00    = 2017-06-11           + 19

        # maintenance_request_01 write stage_id and close_date.
        maintenance_request_01.write({'stage_id': self.stage_repaired_id})
        maintenance_request_01.close_date = datetime(2017, 5, 3).date() + timedelta(days=10)
        self.assertEquals(maintenance_request_01.close_date, datetime(2017, 5, 13).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_02 write stage_id and close_date.
        maintenance_request_02.write({'stage_id': self.stage_repaired_id})
        maintenance_request_02.close_date = datetime(2017, 5, 23).date() + timedelta(days=5)
        self.assertEquals(maintenance_request_02.close_date, datetime(2017, 5, 28).date(), 'Wrong close date on maintenance request.')

        # maintenance_request_03 write stage_id and close_date.
        maintenance_request_03.write({'stage_id': self.stage_repaired_id})
        maintenance_request_03.close_date = maintenance_request_03.request_date
        self.assertEquals(maintenance_request_03.close_date, datetime(2017, 6, 11).date(), 'Wrong close date on maintenance request.')

        # Check MTTR = Day used to handle maintenance request / No of request (15 / 3)
        self.assertEquals(equipment_01.mttr, 5, 'Maintenance Equipment MTTR(Mean Time To Repair) should be 5 days')

        # Check MTBF = Gap in days of between effective date and last request / No of request
        self.assertEquals(equipment_01.mtbf, 19, 'Maintenance Equipment MTBF(Mean Time Between Failure) should be 19 days')

        # Check calculation of latest failure date (should be 11-06-2017)
        latest_failure_date = equipment_01.latest_failure_date
        self.assertEquals(maintenance_request_03.request_date, datetime(2017, 6, 11).date(), 'Wrong request_date on maintenance request.')
        self.assertEquals(latest_failure_date, maintenance_request_03.request_date, 'Wrong latest_failure_date on maintenance request.')

        # Check calculation of estimated next failure (should be 30-06-2017)
        # Step-1: latest failure date + MTBF
        estimated_next_failure = equipment_01.latest_failure_date + timedelta(days=equipment_01.mtbf)
        self.assertEquals(estimated_next_failure, datetime(2017, 6, 30).date(), 'Wrong latest_failure_date on maintenance request.')

    def test_02_mrp_maintenance(self):

        """ In order to check cron job to create preventive request (_cron_generate_requests)"""
        """
        EX:
           equipment      =  Acer Laptop
           effective_date = 25-04-2018
           period         =   5

           maintenance request
            request_date =  effective_date  +  period
            30-04-2018   =    25-04-2018    +   5 days
        """

        # Create a new equipment
        equipment_form = Form(self.equipment)
        equipment_form.name = 'Acer Laptop'
        equipment_form.maintenance_team_id = self.maintenance_team_id
        equipment_form.category_id = self.category_id
        equipment_form.technician_user_id = self.technician_user_id
        equipment_form.assign_date = time.strftime('%Y-%m-%d')
        equipment_form.serial_no = 'MT/127/18291015'
        equipment_form.expected_mtbf = 2
        equipment_form.effective_date = datetime.now().date() + timedelta(days=5)
        equipment_form.period = 5
        equipment_01 = equipment_form.save()

        # Check that equipment is created or not
        self.assertTrue(equipment_01, 'Equipment not created')

        # Execute cron job.
        self.equipment._cron_generate_requests()

        # Get maintenence request.
        maintenance_requests = self.env['maintenance.request'].search([('equipment_id', '=', equipment_01.id)])

        # Check whether request is created or not.
        self.assertEquals(len(maintenance_requests), 1, 'Cron job execution failure or request is not created.')

        # check maintenence request request_date
        self.assertEquals(maintenance_requests.request_date, equipment_01.next_action_date, "wrong request_date in maintenence request")

        # Check whether Next preventive date is changed after execution of cron job.
        self.assertEquals(equipment_01.next_action_date, datetime.now().date() + timedelta(days=10), 'Wrong next preventive maintenance date after cron job execution.')
