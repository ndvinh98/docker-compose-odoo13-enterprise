# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import common
from odoo.addons.test_mail.tests.common import mail_new_test_user


class TestDMFA(common.TransactionCase):

    def test_dmfa(self):
        user = mail_new_test_user(self.env, login='blou', groups='hr_payroll.group_hr_payroll_manager,fleet.fleet_group_manager')
        lap = self.env.ref('hr_contract_salary.hr_employee_laurie_poiret')
        company = lap.company_id
        user.company_ids = [(4, company.id)]
        today = date.today()
        lap.address_id = lap.company_id.partner_id
        company.dmfa_employer_class = 456
        company.onss_registration_number = 45645
        company.onss_company_id = 45645
        self.env['l10n_be.dmfa.location.unit'].with_user(user).create({
            'company_id': lap.company_id.id,
            'code': 123,
            'partner_id': lap.address_id.id,
        })
        dmfa = self.env['l10n_be.dmfa'].with_user(user).create({
            'reference': 'TESTDMFA',
            'company_id': self.env.ref('l10n_be_hr_payroll.res_company_be').id
        })
        dmfa.generate_dmfa_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.validation_state, 'done')
