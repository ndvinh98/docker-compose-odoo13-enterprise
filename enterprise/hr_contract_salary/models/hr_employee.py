# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    id_card = fields.Binary(string="ID Card Copy", groups="hr_contract.group_hr_contract_manager")
    driving_license = fields.Binary(string="Driving License", groups="hr_contract.group_hr_contract_manager")
    mobile_invoice = fields.Binary(string="Mobile Subscription Invoice", groups="hr_contract.group_hr_contract_manager")
    sim_card = fields.Binary(string="SIM Card Copy", groups="hr_contract.group_hr_contract_manager")
    internet_invoice = fields.Binary(string="Internet Subscription Invoice", groups="hr_contract.group_hr_contract_manager")

    def get_partner_values(self, personal_info):
        return {
            'street': personal_info['street'],
            'street2': personal_info['street2'],
            'city': personal_info['city'],
            'zip': personal_info['zip'],
            'state_id': self.env['res.country.state'].search([('name', '=', personal_info['state'])], limit=1).id,
            'country_id': personal_info['country'],
            'phone': personal_info['phone'],
            'email': personal_info['email'],
            'type': 'private',
            'name': personal_info['name'],
        }

    def get_employee_values(self, personal_info):
        fields_list = [
            'gender', 'disabled', 'marital', 'spouse_fiscal_status', 'spouse_net_revenue',
            'spouse_other_net_revenue', 'disabled_spouse_bool', 'disabled_children_bool',
            'children', 'disabled_children_number', 'other_dependent_people',
            'other_senior_dependent', 'other_disabled_senior_dependent', 'other_juniors_dependent',
            'other_disabled_juniors_dependent', 'identification_id', 'country_id',
            'emergency_contact', 'emergency_phone', 'certificate', 'study_field',
            'study_school', 'country_of_birth', 'place_of_birth', 'spouse_complete_name',
            'km_home_work', 'job_title',
        ]
        result = {field: personal_info[field] for field in fields_list}
        for field in ['image_1920', 'id_card', 'driving_license', 'mobile_invoice', 'sim_card', 'internet_invoice']:
            if personal_info.get(field, False):
                result[field] = personal_info.get(field)
        return result

    def update_personal_info(self, personal_info, no_name_write=False):
        self.ensure_one()

        # Update personal info on the partner
        partner_values = self.get_partner_values(personal_info)
        if no_name_write:
            del partner_values['name']

        if self.address_home_id:
            partner = self.address_home_id
            # We shouldn't modify the partner email like this
            partner_values.pop('email', None)
            self.address_home_id.write(partner_values)
        else:
            partner_values['active'] = False
            partner = self.env['res.partner'].create(partner_values)

        # Update personal info on the employee
        vals = self.get_employee_values(personal_info)

        existing_bank_account = self.env['res.partner.bank'].search([('acc_number', '=', personal_info['bank_account'])], limit=1)
        if existing_bank_account:
            bank_account = existing_bank_account
        else:
            bank_account = self.env['res.partner.bank'].create({
                'acc_number': personal_info['bank_account'],
                'partner_id': partner.id,
            })
        vals['bank_account_id'] = bank_account.id
        vals['address_home_id'] = partner.id

        if partner.type != 'private':
            partner.type = 'private'

        if not no_name_write:
            vals['name'] = personal_info['name']

        if personal_info['birthdate'] != '':
            vals.update({'birthday': personal_info['birthdate']})
        if personal_info['spouse_birthdate'] != '':
            vals.update({'spouse_birthdate': personal_info['spouse_birthdate']})

        self.write(vals)
