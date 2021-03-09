# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo.tests
from odoo.addons.test_mail.tests.common import mail_new_test_user


@odoo.tests.common.at_install(False)
@odoo.tests.common.post_install(True)
class TestUi(odoo.tests.HttpCase):
    def test_ui(self):
        # no user available for belgian company so to set hr responsible change company of demo
        demo = mail_new_test_user(self.env, name="Laurie Poiret", login='be_demo', groups='base.group_user')
        partner_id = self.env.ref('hr_contract_salary.res_partner_laurie_poiret').id
        company_id = self.env.ref('l10n_be_hr_payroll.res_company_be').id
        demo.write({'partner_id': partner_id, 'company_id': company_id, 'company_ids': [(4, company_id)]})
        self.start_tour("/", 'hr_contract_salary_tour', login='admin', timeout=100)
