# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, http, models, _, SUPERUSER_ID

from odoo.addons.sign.controllers.main import Sign
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import consteq
from odoo.tools.image import image_data_uri

from werkzeug.exceptions import NotFound
from werkzeug.wsgi import get_current_url


class SignContract(Sign):

    @http.route([
        '/sign/sign/<int:id>/<token>',
        '/sign/sign/<int:id>/<token>/<sms_token>'
        ], type='json', auth='public')
    def sign(self, id, token, sms_token=False, signature=None):
        result = super(SignContract, self).sign(id, token, sms_token=sms_token, signature=signature)
        request_item = request.env['sign.request.item'].sudo().search([('access_token', '=', token)])
        contract = request.env['hr.contract'].sudo().with_context(active_test=False).search([
            ('sign_request_ids', 'in', request_item.sign_request_id.ids)])
        request_template_id = request_item.sign_request_id.template_id.id
        # Only if the signed document is the document to sign from the salary package
        contract_documents = [
            contract.sign_template_id.id,
            contract.contract_update_template_id.id,
        ]
        if contract and request_template_id in contract_documents:
            self._update_contract_on_signature(request_item, contract)
            return {'url': '/salary_package/thank_you/' + str(contract.id)}
        return result

    def _update_contract_on_signature(self, request_item, contract):
        # Only the applicant/employee has signed
        if request_item.sign_request_id.nb_closed == 1:
            contract.active = True
            contract.access_token_consumed = True
            if contract.applicant_id:
                contract.applicant_id.access_token = False
                contract.applicant_id.emp_id = contract.employee_id
            if contract.car_id and contract.driver_id != contract.employee_id.address_home_id:
                contract.car_id.future_driver_id = contract.employee_id.address_home_id
        # Both applicant/employee and HR responsible have signed
        if request_item.sign_request_id.nb_closed == 2:
            if contract.employee_id:
                contract.employee_id.active = True
            if contract.employee_id.address_home_id:
                contract.employee_id.address_home_id.active = True
            if contract.new_car:
                model = contract.new_car_model_id.sudo()
                contract.car_id = request.env['fleet.vehicle'].sudo().create({
                    'model_id': model.id,
                    'state_id': request.env.ref('fleet.fleet_vehicle_state_new_request').id,
                    'future_driver_id': contract.employee_id.address_home_id.id,
                    'car_value': model.default_car_value,
                    'co2': model.default_co2,
                    'fuel_type': model.default_fuel_type,
                })
                vehicle_contract = contract.car_id.log_contracts[0]
                vehicle_contract.recurring_cost_amount_depreciated = model.default_recurring_cost_amount_depreciated
                vehicle_contract.cost_generated = model.default_recurring_cost_amount_depreciated
                vehicle_contract.cost_frequency = 'no'
                vehicle_contract.purchaser_id = contract.employee_id.address_home_id.id
                contract.new_car = False
                contract.new_car_model_id = False


class website_hr_contract_salary(http.Controller):

    def _check_token_validity(self, token):
        if token:
            contract = request.env['hr.contract'].sudo().search([
                ('access_token', '=', token),
                ('access_token_end_date', '>=', fields.Date.today()),
                ('access_token_consumed', '=', False),
            ], limit=1)
            return contract
        return request.env['hr.contract']

    def _check_employee_access_right(self, contract_id):
        contract_sudo = request.env['hr.contract'].sudo().browse(contract_id)
        if not contract_sudo.employee_id or contract_sudo.employee_id.user_id == request.env.user:
            return contract_sudo
        try:
            contract = request.env['hr.contract'].with_context(allowed_company_ids=request.env.user.company_ids.ids).browse(contract_id)
            contract.check_access_rights('read')
            contract.check_access_rule('read')
            return contract_sudo
        except:
            return request.env['hr.contract']

    def _check_access_rights(self, contract_id, token):
        if token:
            contract = self._check_token_validity(token)
        else:
            contract = self._check_employee_access_right(contract_id)
        return contract

    @http.route(['/salary_package/simulation/contract/<int:contract_id>'], type='http', auth="public", website=True)
    def salary_package(self, contract_id=None, **kw):

        # Used to flatten the response after the rollback.
        # Otherwise assets are generated and rollbacked before the page loading.
        # Leading to crashes (assets not found) when loading the page.
        response = False
        request.env.cr.execute('SAVEPOINT salary')

        contract = request.env['hr.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.render('http_routing.http_error', {'status_code': 'Oops',
                                                         'status_message': 'This contract has been updated, please request an updated link..'})

        if not request.env.user.has_group('hr_contract.group_hr_contract_manager'):
            if kw.get('applicant_id'):
                applicant = request.env['hr.applicant'].sudo().browse(int(kw.get('applicant_id')))
                if not kw.get('token') or \
                        not applicant.access_token or \
                        not consteq(applicant.access_token, kw.get('token')) or \
                        applicant.access_token_end_date < fields.Date.today():
                    return request.render(
                        'http_routing.http_error',
                        {'status_code': 'Oops',
                         'status_message': 'This link is invalid. Please contact the HR Responsible to get a new one...'})
            if contract.employee_id and not contract.employee_id.user_id and not kw.get('applicant_id'):
                return request.render(
                    'http_routing.http_error',
                    {'status_code': 'Oops',
                     'status_message': 'The employee is not linked to an existing user, please contact the administrator..'})
            if contract.employee_id and contract.employee_id.user_id != request.env.user:
                raise NotFound()

        if kw.get('employee_contract_id'):
            employee_contract = request.env['hr.contract'].sudo().browse(int(kw.get('employee_contract_id')))
            if not request.env.user.has_group('hr_contract.group_hr_contract_manager') and employee_contract.employee_id \
                    and employee_contract.employee_id.user_id != request.env.user:
                raise NotFound()

        contract.sudo().configure_access_token()
        if not contract.employee_id:
            contract.employee_id = request.env['hr.employee'].sudo().create({
                'name': 'Enter your name',
                'active': False,
                'country_id': request.env.ref('base.be').id,
            })
            contract.employee_id.address_home_id = request.env['res.partner'].sudo().create({
                'name': 'Simulation',
                'type': 'private',
                'country_id': request.env.ref('base.be').id,
                'active': False,
            })

        values = self.get_salary_package_values(contract)

        redirect_to_job = False
        applicant_id = False
        customer_relation = False
        new_car = False
        contract_type = False
        employee_contract_id = False
        job_title = False
        freeze = False

        final_yearly_costs = contract.final_yearly_costs

        for field_name, value in kw.items():
            old_value = contract
            if field_name == 'car_id':
                contract.car_id = int(value)
                contract.new_car = False
                if int(value) not in values['available_cars'].ids:
                    values['available_cars'] |= request.env['fleet.vehicle'].sudo().browse(int(value))
                    values['available_cars'] = values['available_cars'].sorted(key=lambda car: car.total_depreciated_cost)
            elif field_name == 'new_car_model_id':
                contract.new_car_model_id = int(value)
                contract.new_car = True
                if int(value) not in values['can_be_requested_models'].ids:
                    values['can_be_requested_models'] |= request.env['fleet.vehicle.model'].sudo().browse(int(value))
                    values['can_be_requested_models'] = values['can_be_requested_models'].sorted(key=lambda model: model.default_total_depreciated_cost)
            elif field_name == 'job_id':
                redirect_to_job = value
            elif field_name == 'applicant_id':
                applicant_id = value
            elif field_name == 'employee_contract_id':
                employee_contract_id = value
            elif field_name == 'customer_relation':
                customer_relation = value
            elif field_name == 'new_car':
                new_car = value
            elif field_name == 'contract_type':
                contract_type = value
            elif field_name == 'job_title':
                job_title = value
            elif field_name == 'freeze':
                freeze = value
            elif field_name == 'debug':
                pass
            elif field_name in old_value:
                old_value = old_value[field_name]
            else:
                old_value = ""

            if isinstance(old_value, models.BaseModel):
                old_value = ""
            elif old_value:
                value = float(value)
                if field_name in ["final_yearly_costs", "monthly_yearly_costs"]:
                    final_yearly_costs = (field_name == "monthly_yearly_costs") and value * 12.0 or value
                else:
                    setattr(contract, field_name, value)

        new_gross = contract.sudo()._get_gross_from_employer_costs(final_yearly_costs)
        contract.wage = new_gross

        values.update({
            'need_personal_information': not redirect_to_job,
            'submit': not redirect_to_job,
            'simulation': False,
            'redirect_to_job': redirect_to_job,
            'applicant_id': applicant_id,
            'employee_contract_id': employee_contract_id,
            'customer_relation': customer_relation,
            'new_car': new_car,
            'contract_type': contract_type,
            'job_title': job_title,
            'freeze': freeze,
            'default_mobile': request.env['ir.default'].sudo().get('hr.contract', 'mobile'),
            'original_link': get_current_url(request.httprequest.environ)})

        values.update(self._get_documents_src(contract.employee_id))
        response = request.render("hr_contract_salary.salary_package", values)
        response.flatten()
        request.env['hr.contract'].flush()
        request.env.cr.execute('ROLLBACK TO SAVEPOINT salary')
        return response

    def _get_documents_src(self, employee):
        res = {}
        for field in ['id_card', 'image_1920', 'driving_license', 'mobile_invoice', 'sim_card', 'internet_invoice']:
            if employee[field]:
                if employee[field][:7] == b'JVBERi0':
                    img_src = "data:application/pdf;base64,%s" % (employee[field].decode())
                else:
                    img_src = image_data_uri(employee[field])
                res[field] = img_src
            else:
                res[field] = False
        return res


    @http.route(['/salary_package/thank_you/<int:contract_id>'], type='http', auth="public", website=True)
    def salary_package_thank_you(self, contract_id=None, **kw):
        contract = request.env['hr.contract'].sudo().browse(contract_id)
        return request.render("hr_contract_salary.salary_package_thank_you", {
            'responsible_name': contract.hr_responsible_id.partner_id.name or contract.job_id.user_id.partner_id.name,
            'responsible_email': contract.hr_responsible_id.partner_id.email or contract.job_id.user_id.partner_id.email,
            'responsible_phone': contract.hr_responsible_id.partner_id.phone or contract.job_id.user_id.partner_id.phone,
        })

    def get_salary_package_values(self, contract):
        return {
            'contract': contract,
            'available_cars': request.env['fleet.vehicle'].sudo().search(
                contract._get_available_cars_domain(contract.employee_id.address_home_id)).sorted(key=lambda car: car.total_depreciated_cost),
            'can_be_requested_models': request.env['fleet.vehicle.model'].sudo().search(
                contract._get_possible_model_domain()).sorted(key=lambda model: model.default_total_depreciated_cost),
            'states': request.env['res.country.state'].search([]),
            'countries': request.env['res.country'].search([]),
        }

    def _get_new_contract_values(self, contract, employee, advantages):
        return {
            'active': False,
            'name': contract.name if contract.state == 'draft' else "Package Simulation",
            'job_id': contract.job_id.id,
            'company_id': contract.company_id.id,
            'currency_id': contract.company_id.currency_id.id,
            'employee_id': employee.id,
            'structure_type_id': contract.structure_type_id.id,
            'company_car_total_depreciated_cost': contract.company_car_total_depreciated_cost,
            'wage': advantages['wage'],
            'resource_calendar_id': contract.resource_calendar_id.id,
            'transport_mode_car': advantages['transport_mode_car'],
            'transport_mode_public': advantages['transport_mode_public'],
            'transport_mode_private_car': advantages['transport_mode_private_car'],
            'public_transport_employee_amount': advantages['public_transport_employee_amount'],
            'eco_checks': advantages['eco_checks'],
            'fuel_card': advantages['fuel_card'],
            'holidays': advantages['holidays'],
            'commission_on_target': advantages['commission_on_target'],
            'representation_fees': advantages['representation_fees'],
            'meal_voucher_amount': advantages['meal_voucher_amount'] / 20.0,
            'default_contract_id': contract.default_contract_id.id,
            'hr_responsible_id': contract.hr_responsible_id.id,
            'sign_template_id': contract.sign_template_id.id,
            'contract_update_template_id': contract.contract_update_template_id.id,
            'ip': advantages['ip'],
            'ip_wage_rate': advantages['ip_wage_rate'],
            'contract_type': advantages['contract_type'],
            'internet': advantages['internet'],
            'date_start': fields.Date.today().replace(day=1),
        }

    def create_new_contract(self, contract, advantages, no_write=False, **kw):
        # Generate a new contract with the current modifications
        personal_info = advantages['personal_info']

        if kw.get('employee'):
            employee = kw.get('employee')
        elif contract.employee_id:
            employee = contract.employee_id
        else:
            employee = request.env['hr.employee'].sudo().create({
                'name': 'Simulation Employee',
                'active': False,
                'company_id': contract.company_id.id,
            })
        if personal_info:
            employee.with_context(lang=None).update_personal_info(personal_info, no_name_write=bool(kw.get('employee')))
        new_contract = request.env['hr.contract'].sudo().new(self._get_new_contract_values(contract, employee, advantages))

        if advantages['has_mobile']:
            new_contract.mobile = request.env['ir.default'].sudo().get('hr.contract', 'mobile')
        else:
            new_contract.mobile = 0.0

        if advantages['transport_mode_car']:
            if advantages['new_car']:
                new_contract.new_car = True
                new_contract.new_car_model_id = advantages['car_id']
                new_contract.car_id = False
            else:
                new_contract.new_car = False
                new_contract.car_id = advantages['car_id']
        else:
            new_contract.new_car = False
            new_contract.new_car_model_id = False
            new_contract.car_id = False

        if not advantages['transport_mode_public']:
            new_contract.public_transport_reimbursed_amount = 0.0

        new_contract.wage_with_holidays = advantages['wage']
        new_contract.final_yearly_costs = advantages['final_yearly_costs']
        new_contract._inverse_wage_with_holidays()

        vals = new_contract._convert_to_write(new_contract._cache)


        if not no_write and contract.state == 'draft':
            contract.write(vals)
            contract = contract
        else:
            contract = request.env['hr.contract'].sudo().create(vals)

        if kw.get('no_car_creation', False):
            return contract

        # Create the car after the contract to avoid losing the cache
        if advantages['transport_mode_car'] and advantages['new_car']:
            Fleet = request.env['fleet.vehicle']
            model = request.env['fleet.vehicle.model'].sudo().browse(advantages['car_id'])
            contract.car_id = Fleet.sudo().create({
                'model_id': advantages['car_id'],
                'state_id': request.env.ref('fleet.fleet_vehicle_state_new_request').id,
                'driver_id': employee.address_home_id.id,
                'car_value': model.default_car_value,
                'co2': model.default_co2,
                'fuel_type': model.default_fuel_type,
                'company_id': contract.company_id.id,
            })
            vehicle_contract = contract.car_id.log_contracts[0]
            vehicle_contract.recurring_cost_amount_depreciated = model.default_recurring_cost_amount_depreciated
            vehicle_contract.cost_generated = model.default_recurring_cost_amount_depreciated
            vehicle_contract.cost_frequency = 'no'
            vehicle_contract.purchaser_id = employee.address_home_id.id

        return contract

    @http.route(['/salary_package/update_gross/'], type="json", auth="public")
    def update_gross(self, contract_id=None, token=None, advantages=None, **kw):

        result = {}

        contract = self._check_access_rights(contract_id, token)

        new_contract = self.create_new_contract(contract, advantages)
        new_gross = new_contract._get_gross_from_employer_costs(advantages['final_yearly_costs'])
        new_contract.wage = new_gross
        result['new_gross'] = round(new_gross, 2)

        request.env.cr.rollback()

        return result

    @http.route(['/salary_package/compute_net/'], type='json', auth='public')
    def compute_net(self, contract_id=None, token=None, advantages=None, **kw):

        contract = self._check_access_rights(contract_id, token)

        new_contract = self.create_new_contract(contract, advantages)
        #  Update gross to keep a fixed employer cost
        new_gross = new_contract._get_gross_from_employer_costs(advantages['final_yearly_costs'])
        new_contract.wage = new_gross

        # generate a payslip corresponding to only this contract
        payslip = request.env['hr.payslip'].sudo().create({
            'employee_id': new_contract.employee_id.id,
            'contract_id': new_contract.id,
            'struct_id': new_contract.structure_type_id.default_struct_id.id,
            'company_id': new_contract.employee_id.company_id.id,
            'name': 'Payslip Simulation',
            'date_from': request.env['hr.payslip'].default_get(['date_from'])['date_from'],
            'date_to': request.env['hr.payslip'].default_get(['date_to'])['date_to'],
        })

        payslip.with_context(salary_simulation=True, lang=None).compute_sheet()

        result = self.get_compute_results(new_contract, payslip)
        request.env.cr.rollback()

        return result

    def get_compute_results(self, new_contract, payslip):
        result = {}
        result.update({
            'BASIC': round(payslip._get_salary_line_total('BASIC'), 2),
            'SALARY': round(payslip._get_salary_line_total('SALARY'), 2),
            'ONSS': round(payslip._get_salary_line_total('ONSS'), 2),
            'EMP.BONUS': round(payslip._get_salary_line_total('EmpBonus.1'), 2) or round(payslip._get_salary_line_total('EmpBonus.2'), 2),
            'GROSS': round(payslip._get_salary_line_total('GROSS'), 2),
            'REP.FEES': round(payslip._get_salary_line_total('REP.FEES'), 2),
            'P.P': round(payslip._get_salary_line_total('P.P'), 2),
            'M.ONSS': round(payslip._get_salary_line_total('M.ONSS'), 2),
            'MEAL_V_EMP': round(payslip._get_salary_line_total('MEAL_V_EMP'), 2),
            'ATN.CAR.2': round(payslip._get_salary_line_total('ATN.CAR.2'), 2),
            'CAR.PRIV': round(payslip._get_salary_line_total('CAR.PRIV'), 2),
            'ATN.INT.2': round(payslip._get_salary_line_total('ATN.INT.2'), 2),
            'ATN.MOB.2': round(payslip._get_salary_line_total('ATN.MOB.2'), 2),
            'NET': round(payslip._get_salary_line_total('NET'), 2),
            'wage_with_holidays': round(new_contract.wage_with_holidays, 2),
            'wage': round(new_contract.wage, 2),
            'company_car_total_depreciated_cost': round(new_contract.company_car_total_depreciated_cost, 2),
            'thirteen_month': round(new_contract.wage_with_holidays, 2),
            'double_holidays': round(new_contract.wage_with_holidays * 0.92, 2),
            'IP': round(payslip._get_salary_line_total('IP'), 2),
            'IP.DED': round(payslip._get_salary_line_total('IP.DED'), 2),
            'TAXED': round(
                payslip._get_salary_line_total('NET') -
                payslip._get_salary_line_total('IP') -
                payslip._get_salary_line_total('IP.DED') -
                payslip._get_salary_line_total('REP.FEES') -
                payslip._get_salary_line_total('CAR.PRIV'), 2
            )
        })

        transport_advantage = 0.0
        if new_contract.transport_mode_public:
            transport_advantage += new_contract.public_transport_reimbursed_amount
        elif new_contract.transport_mode_private_car:
            transport_advantage += new_contract.private_car_reimbursed_amount
        elif new_contract.transport_mode_car:
            transport_advantage += new_contract.company_car_total_depreciated_cost

        thirteen_month_net = payslip._get_salary_line_total('NET')
        double_holidays_net = payslip._get_salary_line_total('NET') * 0.92

        monthly_nature = round(transport_advantage + new_contract.internet + new_contract.mobile, 2)
        monthly_cash = round(new_contract.warrant_value_employee / 12.0 + new_contract.meal_voucher_amount * 20.0 + new_contract.fuel_card, 2)
        yearly_cash = round(new_contract.eco_checks + thirteen_month_net + double_holidays_net, 2)
        monthly_total = round(monthly_nature + monthly_cash + yearly_cash / 12.0 + payslip._get_salary_line_total('NET') - new_contract.representation_fees, 2)

        result.update({
            'monthly_nature': monthly_nature,
            'monthly_cash': monthly_cash,
            'yearly_cash': yearly_cash,
            'monthly_total': monthly_total,
            'employee_total_cost': round(new_contract.final_yearly_costs, 2),
        })

        return result

    @http.route(['/salary_package/onchange_mobile/'], type='json', auth='public')
    def onchange_mobile(self, has_mobile):
        return request.env['hr.contract'].sudo()._get_mobile_amount(has_mobile)

    @http.route(['/salary_package/onchange_car/'], type='json', auth='public')
    def onchange_car(self, car_option, vehicle_id):
        if car_option == "new":
            vehicle = request.env['fleet.vehicle.model'].sudo().browse(vehicle_id)
            co2 = vehicle.default_co2
            fuel_type = vehicle.default_fuel_type
            door_number = odometer = immatriculation = False
        else:
            vehicle = request.env['fleet.vehicle'].sudo().browse(vehicle_id)
            co2 = vehicle.co2
            fuel_type = vehicle.fuel_type
            door_number = vehicle.doors
            odometer = vehicle.odometer
            immatriculation = vehicle.acquisition_date
        return {'co2': co2, 'fuel_type': fuel_type, 'door_number': door_number, 'odometer': odometer, 'immatriculation': immatriculation}

    @http.route(['/salary_package/onchange_public_transport/'], type='json', auth='public')
    def onchange_public_transport(self, public_transport_employee_amount):
        return round(request.env['hr.contract'].sudo()._get_public_transport_reimbursed_amount(public_transport_employee_amount), 2)

    @http.route(['/salary_package/onchange_km_home_work/'], type='json', auth='public')
    def onchange_home_company_distance(self, distance):
        return round(request.env['hr.contract']._get_private_car_reimbursed_amount(distance), 2)

    @http.route(['/salary_package/send_email/'], type='json', auth='public')
    def send_email(self, contract_id=None, token=None, advantages=None, **kw):
        contract = self._check_access_rights(contract_id, token)

        car_name = model_name = False
        if advantages['transport_mode_car']:
            if not advantages['new_car']:
                car_name = request.env['fleet.vehicle'].sudo().browse(advantages['car_id']).name
            else:
                model_name = request.env['fleet.vehicle.model'].sudo().browse(advantages['car_id']).name

        if advantages['personal_info']['country_id']:
            nationality_name = request.env['res.country'].sudo().browse(advantages['personal_info']['country_id']).name
        else:
            nationality_name = ''

        if advantages['personal_info']['country_of_birth']:
            country_of_birth_name = request.env['res.country'].sudo().browse(advantages['personal_info']['country_of_birth']).name
        else:
            country_of_birth_name = ''
        values = {
            'contract': contract,
            'advantages': advantages,
            'car_name': car_name,
            'model_name': model_name,
            'nationality_name': nationality_name,
            'country_of_birth_name': country_of_birth_name,
            'country_name': request.env['res.country'].sudo().browse(advantages['personal_info']['country']).name,
            'original_link': kw.get('original_link'),
            'contract_type': kw.get('contract_type'),
        }

        if kw.get('applicant_id'):
            request.env['hr.applicant'].sudo().browse(kw.get('applicant_id')).message_post_with_view(
                'hr_contract_salary.hr_contract_salary_email_template',
                values=values)
        elif kw.get('employee_contract_id'):
            request.env['hr.contract'].sudo().browse(kw.get('employee_contract_id')).message_post_with_view(
                'hr_contract_salary.hr_contract_salary_email_template',
                values=values)
        else:
            body = request.env.ref('hr_contract_salary.hr_contract_salary_email_template').render(values)
            request.env['mail.mail'].sudo().create({
                'subject': '[%s] New salary package request' % (advantages['personal_info']['name']),
                'body_html': body,
                'email_from': advantages['personal_info']['email'] or '',
                'author_id': False,
                'email_to': contract.hr_responsible_id.email,
            })

        return contract.id

    @http.route(['/salary_package/submit/'], type='json', auth='public')
    def submit(self, contract_id=None, token=None, advantages=None, **kw):
        contract = self._check_access_rights(contract_id, token)

        if advantages['transport_mode_car'] and not advantages['new_car'] and advantages.get('car_id'):
            car = request.env['fleet.vehicle'].sudo().browse(int(advantages['car_id']))
            available_cars = request.env['fleet.vehicle'].sudo().search(contract._get_available_cars_domain(contract.employee_id.address_home_id))
            if car not in available_cars and car.future_driver_id and car.future_driver_id != contract.employee_id.address_home_id:
                return {'error': 1, 'error_msg': _('Unfortunately the car you have selected is not available anymore. Please choose another one.')}

        self.send_email(contract_id=contract_id, token=token, advantages=advantages, **kw)

        if kw.get('employee_contract_id', False):
            contract = request.env['hr.contract'].sudo().browse(kw.get('employee_contract_id'))
            if contract.employee_id.user_id == request.env.user:
                kw['employee'] = contract.employee_id

        kw['no_car_creation'] = True
        new_contract = self.create_new_contract(contract, advantages, no_write=True, **kw)

        # Create new car in waiting list if more than max_unused_cars available cars
        if advantages['waiting_list'] and advantages['waiting_list_model']:
            model = request.env['fleet.vehicle.model'].sudo().browse(advantages['waiting_list_model'])
            car = request.env['fleet.vehicle'].sudo().create({
                'model_id': advantages['waiting_list_model'],
                'state_id': request.env.ref('hr_contract_salary.fleet_vehicle_state_waiting_list').id,
                'car_value': model.default_car_value,
                'co2': model.default_co2,
                'fuel_type': model.default_fuel_type,
                'acquisition_date': new_contract.car_id.acquisition_date or fields.Date.today()
            })

            vehicle_contract = car.log_contracts[0]
            vehicle_contract.recurring_cost_amount_depreciated = model.default_recurring_cost_amount_depreciated
            vehicle_contract.cost_generated = model.default_recurring_cost_amount_depreciated
            vehicle_contract.cost_frequency = 'no'
            vehicle_contract.purchaser_id = new_contract.employee_id.address_home_id.id

        if new_contract.id != contract.id:
            new_contract.write({
                'state': 'draft',
                'name': 'New contract - ' + new_contract.employee_id.name,
                'origin_contract_id': contract_id,
            })

        # Take specific contract to sign
        if kw.get('employee_contract_id'):
            sign_template = new_contract.contract_update_template_id
        elif kw.get('applicant_id'):
            sign_template = new_contract.sign_template_id

        if not sign_template:
            return {'error': 1, 'error_msg': _('No signature template defined on the contract. Please contact the HR responsible.')}

        if not new_contract.hr_responsible_id:
            return {'error': 1, 'error_msg': _('No HR responsible defined on the job position. Please contact an administrator.')}

        if not request.env.user.email_formatted:
            sign_request = request.env['sign.request'].with_user(SUPERUSER_ID)
        else:
            sign_request = request.env['sign.request'].sudo()

        res = sign_request.initialize_new(
            sign_template.id,
            [
                {'role': request.env.ref('sign.sign_item_role_employee').id, 'partner_id': new_contract.employee_id.address_home_id.id},
                {'role': request.env.ref('hr_contract_sign.sign_item_role_job_responsible').id, 'partner_id': new_contract.hr_responsible_id.partner_id.id}
            ],
            [new_contract.hr_responsible_id.partner_id.id],
            'Signature Request - ' + new_contract.name,
            'Signature Request - ' + new_contract.name,
            '',
            False
        )

        items = request.env['sign.item'].sudo().search([
            ('template_id', '=', sign_template.id),
            ('name', '!=', '')
        ])
        for item in items:
            new_value = new_contract
            for elem in item.name.split('.'):
                if elem in new_value:
                    new_value = new_value[elem]
                else:
                    new_value = ''
                if elem == 'car' and new_contract.transport_mode_car:
                    if not new_contract.new_car and new_contract.car_id:
                        new_value = new_contract.car_id.model_id.name
                    elif new_contract.new_car and new_contract.new_car_model_id:
                        new_value = new_contract.new_car_model_id.name
            if isinstance(new_value, models.BaseModel):
                new_value = ''
            if isinstance(new_value, float):
                new_value = round(new_value, 2)
            if new_value or (new_value == 0.0):
                sign_request_item_id = http.request.env['sign.request.item'].sudo().search([
                    ('sign_request_id', '=', res['id']),
                    ('role_id', '=', item.responsible_id.id)
                ])
                request.env['sign.request.item.value'].sudo().create({
                    'sign_item_id': item.id,
                    'sign_request_id': res['id'],
                    'value': new_value,
                    'sign_request_item_id': sign_request_item_id.id
                })

        sign_request = request.env['sign.request'].browse(res['id']).sudo()
        sign_request.toggle_favorited()
        sign_request.action_sent()
        sign_request.write({'state': 'sent'})
        sign_request.request_item_ids.write({'state': 'sent'})

        access_token = request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', res['id']),
            ('role_id', '=', request.env.ref('sign.sign_item_role_employee').id)
        ]).access_token

        new_contract.sign_request_ids += sign_request

        if new_contract:
            if kw.get('applicant_id'):
                new_contract.sudo().applicant_id = kw.get('applicant_id')
            if kw.get('employee_contract_id'):
                new_contract.sudo().origin_contract_id = kw.get('employee_contract_id')

        return {'job_id': new_contract.job_id.id, 'request_id': res['id'], 'token': access_token, 'error': 0, 'new_contract_id': new_contract.id}
