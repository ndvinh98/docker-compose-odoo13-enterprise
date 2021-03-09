# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, date

from odoo.addons.test_l10n_be_hr_payroll_account.tests.test_payslip import TestPayslipBase


class TestDoublePecule(TestPayslipBase):

    def test_double_holiday_pay(self):
        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday')
        contract = self.create_contract(date(2015, 1, 1))
        payslip = self.create_payslip(contract, structure, datetime(2019, 1, 1), datetime(2019, 1, 31))

        payslip.compute_sheet()
        self.check_payslip('double holiday pay', payslip, {
            'BASIC': 2500.0,
            'D.P': 2300.0,
            'SALARY': 2125.0,
            'ONSS': -277.74,
            'P.P': -833.79,
            'NET': 1284.04,
        })
