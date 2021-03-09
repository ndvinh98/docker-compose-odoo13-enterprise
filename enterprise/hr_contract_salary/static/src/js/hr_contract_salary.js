odoo.define('hr_contract_salary', function (require) {
"use strict";

var concurrency = require('web.concurrency');
var publicWidget = require('web.public.widget');
var utils = require('web.utils');

publicWidget.registry.SalaryPackageWidget = publicWidget.Widget.extend({
    selector: '#hr_cs_form',

    events: {
        "change .advantage_input": "onchange_advantage",
        "change input[name='mobility']": "onchange_mobility",
        "change input[name='transport_mode_car']": "onchange_mobility",
        "change input[name='transport_mode_public']": "onchange_mobility",
        "change input[name='transport_mode_private_car']": "onchange_mobility",
        "change input[name='representation_fees_radio']": "onchange_representation_fees",
        "change input[name='fuel_card_slider']": "onchange_fuel_card",
        "input input[name='holidays_slider']": "onchange_holidays",
        "change input[name='mobile']": "onchange_mobile",
        "change input[name='internet']": "onchange_internet",
        "change select[name='select_car']": "onchange_car_id",
        "change input[name='public_transport_employee_amount']": "onchange_public_transport",
        "change select[name='marital']": "onchange_marital",
        "change select[name='spouse_fiscal_status']": "onchange_spouse_fiscal_status",
        "change input[name='disabled_children_bool']": "onchange_disabled_children",
        "change input[name='other_dependent_people']": "onchange_other_dependent_people",
        "click #hr_cs_submit": "submit_salary_package",
        "click button[name='compute_button']": "compute_net",
        "click a[name='recompute']": "recompute",
        "click button[name='toggle_personal_information']": "toggle_personal_information",
        "change input[name='ip']": "onchange_ip",
        "change input.km_home_work": "onchange_km_home_work",
        "click #send_email": "send_offer_to_responsible",
        "change select[name='spouse_professional_situation']": "onchange_spouse_professional_situation",
        "change input[name='waiting_list']": "onchange_waiting_list",
        "change input.bg-danger": "check_form_validity",
        "change input.document": "onchange_document",
        "change input.half_name": "onchange_half_name",
    },

    init: function(parent, options) {
        this._super(parent);
        this.dp = new concurrency.DropPrevious();
        this.update_gross_to_net_computation();
        $("div#company_car select").val() === 'new' ? $("div#new_company_car").removeClass('d-none') : $("div#new_company_car").addClass('d-none')
        this.onchange_mobile();
        this.onchange_internet();
        if (!$("input[name='holidays_input']").val()) {
            $("input[name='holidays_slider']").val(0);
            $("input[name='holidays_input']").val(0);
        }
        this.onchange_holidays();
        this.onchange_disabled_children();
        this.onchange_marital();
        this.onchange_car_id();
        this.onchange_spouse_fiscal_status();
        this.onchange_other_dependent_people();
        $('body').attr('id', 'hr_contract_salary');
        this.onchange_mobility();
        $("a[name='recompute']").addClass('d-none');
        $("#hr_contract_salary select").select2({
            minimumResultsForSearch: -1
        });
        // We create a fake event in order to trigger the representation fees onchange. This is
        // necessary since the events are not bound yet, therefore
        // $("input[name='representation_fees_radio']:checked").change() won't work.
        var fake_event = {};
        fake_event.target = {};
        fake_event.target.value = $("input[name='representation_fees_radio']:checked").val();
        this.onchange_representation_fees(fake_event);
        var fuel_card_input = $("input[name='fuel_card_input']");
        var fuel_card_slider = $("input[name='fuel_card_slider']");
        if(parseInt(fuel_card_input.val()) !== parseInt(fuel_card_slider.val())) {
            fuel_card_input.val(0.0);
            fuel_card_slider.val(0.0);
        }
        var eco_checks = $("input[name='eco_checks']");
        if(!eco_checks.val()) {eco_checks.val(0.0);}
        $('b[role="presentation"]').hide();
        $('.select2-arrow').append('<i class="fa fa-chevron-down"></i>');
        this.update_gross = _.debounce(this.update_gross, 1000);
        this.onchange_ip();
        if ($("input[name='freeze']").val()) {
            $('input.advantage_input').attr('disabled', 'disabled');
            $('section#hr_cs_personal_information input.advantage_input').removeAttr('disabled');
        }
    },

    willStart: function() {
        var def1 = this._super();
        var def2 = this.update_gross_to_net_computation();
        return Promise.all([def1, def2]);
    },

    get_personal_documents: function() {
        var document_names = ['id_card', 'image_1920', 'driving_license', 'mobile_invoice', 'sim_card', 'internet_invoice'];
        var document_srcs = {};
        var promises_list = _.map(document_names, function(document_name) {
            var file = $("input[name='" + document_name + "']");
            return new Promise(function(resolve) {
                if (file[0].files[0]) {
                    utils.getDataURLFromFile(file[0].files[0]).then(function (testString) {
                        var regex = new RegExp(",(.{0,})", "g");
                        var img_src = regex.exec(testString)[1];
                        resolve(img_src);
                    });
                } else {
                    resolve(false);
                }
            }).then(function(img_src) {
                document_srcs[document_name] = img_src;
            });
        });

        return Promise.all(promises_list).then(function() {
            var personal_documents = {
                'id_card': document_srcs.id_card,
                'image_1920': document_srcs.image_1920,
                'driving_license': document_srcs.driving_license,
                'mobile_invoice': document_srcs.mobile_invoice,
                'sim_card': document_srcs.sim_card,
                'internet_invoice': document_srcs.internet_invoice,
            };
            return personal_documents;
        });
    },

    get_personal_info: function() {
        return {
            'name': $("input[name='name']").val(),
            'gender': _.find($("input[name='gender']"), function(gender) {
                return gender.checked;
            }).value,
            'disabled': $("input[name='disabled']")[0].checked,
            'marital': $("select[name='marital']").val(),
            'spouse_fiscal_status': $("select[name='spouse_fiscal_status']").val(),
            'spouse_net_revenue': parseFloat($("input[name='spouse_net_revenue']").val()) || 0.0,
            'spouse_other_net_revenue': parseFloat($("input[name='spouse_other_net_revenue']").val()) || 0.0,
            'disabled_spouse_bool': $("input[name='disabled_spouse_bool']")[0].checked,
            'children': parseInt($("input[name='children']").val()) || 0,
            'disabled_children_bool': $("input[name='disabled_children_bool']")[0].checked,
            'disabled_children_number': parseInt($("input[name='disabled_children_number']").val()) || 0,
            'other_dependent_people': $("input[name='other_dependent_people']")[0].checked,
            'other_senior_dependent': parseInt($("input[name='other_senior_dependent']").val()) || 0,
            'other_disabled_senior_dependent': parseInt($("input[name='other_disabled_senior_dependent']").val()) || 0,
            'other_juniors_dependent': parseInt($("input[name='other_juniors_dependent']").val()) || 0,
            'other_disabled_juniors_dependent': parseInt($("input[name='other_disabled_juniors_dependent']").val()) || 0,
            'birthdate': $("input[name='birthdate']").val(),
            'street': $("input[name='street']").val(),
            'street2': $("input[name='street2']").val(),
            'city': $("input[name='city']").val(),
            'zip': $("input[name='zip']").val(),
            'state': $("input[name='state']").val(),
            'country': parseInt($("select[name='country']").val()),
            'email': $("input[name='email']").val(),
            'phone': $("input[name='phone']").val(),
            'identification_id': $("input[name='identification_id']").val(),
            'country_id': parseInt($("select[name='country_id']").val()),
            'certificate': $("select[name='certificate']").val(),
            'study_field': $("input[name='study_field']").val(),
            'study_school': $("input[name='study_school']").val(),
            'bank_account': $("input[name='bank_account']").val(),
            'emergency_contact': $("input[name='emergency_contact']").val(),
            'emergency_phone': $("input[name='emergency_phone']").val(),
            'country_of_birth': parseInt($("select[name='country_of_birth']").val()),
            'place_of_birth': $("input[name='place_of_birth']").val(),
            'spouse_complete_name': $("input[name='spouse_complete_name']").val(),
            'spouse_birthdate': $("input[name='spouse_birthdate']").val(),
            'km_home_work': parseInt($("input[name='km_home_work']").val()),
            'spouse_professional_situation': $("select[name='spouse_professional_situation']").val(),
            'job_title': $("input[name='job_title']").val(),
        };
    },

    get_advantages: function() {
        var has_commission = $("input[name='commission_on_target']").length;
        var has_meal_voucher = $("input[name='meal_voucher_amount']").length;
        var car_value = $("select[name='select_car']").val();
        var car_id = false;
        var new_car = false;
        if (car_value) {
            car_id = parseInt($("select[name='select_car']").val().split('-')[1]);
            if ($("select[name='select_car']").val().split('-')[0] === 'new') {
                new_car = true;
            } else {
                new_car = false;
            }
        }
        return {
            'wage': $("input[name='wage']")[0].value,
            'internet': $("input[name='internet']")[0].value,
            'has_mobile': $("input[name='mobile']")[1].checked,
            'fuel_card': parseFloat($("input[name='fuel_card_input']")[0].value) || 0.0,
            'transport_mode_car': $("input[name='transport_mode_car']")[0].checked,
            'transport_mode_public': $("input[name='transport_mode_public']")[0].checked,
            'transport_mode_private_car': $("input[name='transport_mode_private_car']")[0].checked,
            'car_employee_deduction': parseFloat($("input[name='car_employee_deduction']")[0].value) || 0.0,
            'holidays': parseFloat($("input[name='holidays_slider']")[0].value) || 0.0,
            'commission_on_target': has_commission ? parseFloat($("input[name='commission_on_target']")[0].value) || 0.0 : 0.0,
            'eco_checks': parseFloat($("input[name='eco_checks']")[0].value),
            'representation_fees': parseFloat($("input[name='representation_fees']")[0].value) || 0.0,
            'car_id': car_id,
            'new_car': new_car,
            'public_transport_employee_amount': parseFloat($("input[name='public_transport_employee_amount']")[0].value) || 0.0,
            'personal_info': this.get_personal_info(),
            'meal_voucher_amount': has_meal_voucher ? parseFloat($("input[name='meal_voucher_amount']")[0].value) || 0.0 : 0.0,
            'final_yearly_costs': parseFloat($("input[name='fixed_yearly_costs']")[0].value),
            'ip': $("input[name='ip']")[0].checked,
            'ip_wage_rate': $("input[name='ip_wage_rate']").val(),
            'contract_type': $("input[name='contract_type']").val(),
            'waiting_list': $("input[name='waiting_list']")[0].checked,
            'waiting_list_model': parseInt($("select[name='select_waiting_list_model']").val()),
        };
    },

    update_gross_to_net_computation: function () {
        var self = this;
        return self._rpc({
            route: '/salary_package/compute_net/',
            params: {
                'contract_id': parseInt($("input[name='contract']")[0].id),
                'token': $("input[name='token']").val(),
                'advantages': self.get_advantages(),
            },
        }).then(function(data) {
            self.update_gross_to_net_modal(data);
        });
    },

    update_gross_to_net_modal: function(data) {
        $("input[name='wage']").val(data['wage']);
        $("input[name='thirteen_month']").val(data['thirteen_month']);
        $("input[name='double_holidays']").val(data['double_holidays']);
        $("input[name='wage_with_holidays']").val(data['wage_with_holidays']);
        $("input[name='SALARY']").val(data['SALARY']);
        $("input[name='ONSS']").val(- data['ONSS']);
        $("input[name='GROSS']").val(data['GROSS']);
        $("input[name='P.P']").val(- data['P.P']);
        $("input[name='M.ONSS']").val(- data['M.ONSS']);
        $("input[name='EMP.BONUS']").val(data['EMP.BONUS']);
        $("input[name='MEAL_V_EMP']").val(- data['MEAL_V_EMP']);
        $("input[name='ATN.CAR.1']").val(- data['ATN.CAR.2']);
        $("input[name='ATN.INT.1']").val(- data['ATN.INT.2']);
        $("input[name='ATN.MOB.1']").val(- data['ATN.MOB.2']);
        $("input[name='ATN.CAR.2']").val(- data['ATN.CAR.2']);
        $("input[name='ATN.INT.2']").val(- data['ATN.INT.2']);
        $("input[name='ATN.MOB.2']").val(- data['ATN.MOB.2']);
        $("input[name='NET']").val(data['NET']);
        $("input[name='monthly_nature']").val(data['monthly_nature']);
        $("input[name='monthly_cash']").val(data['monthly_cash']);
        $("input[name='yearly_cash']").val(data['yearly_cash']);
        $("input[name='monthly_total']").val(data['monthly_total']);
        $("input[name='employee_total_cost']").val(data['employee_total_cost']);
        $("input[name='car_employee_deduction']").val(data['company_car_total_depreciated_cost']);
        var mobile_atn_div = $("div[name='mobile_atn']");
        var internet_atn_div = $("div[name='internet_atn']");
        var company_car_atn_div = $("div[name='company_car_atn']");
        var employment_bonus_div = $("div[name='employment_bonus']");
        var withholding_tax_reduction_div = $("div[name='withholding_tax_reduction']");
        var miscellaneous_onss_div = $("div[name='m_onss_div']");
        var representation_fees_div = $("div[name='representation_fees_div']");
        var private_car_amount_div = $("div[name='private_car_amount_div']");
        data['ATN.MOB.2'] ? mobile_atn_div.removeClass('d-none') : mobile_atn_div.addClass('d-none');
        data['ATN.INT.2'] ? internet_atn_div.removeClass('d-none') : internet_atn_div.addClass('d-none');
        data['ATN.CAR.2'] ? company_car_atn_div.removeClass('d-none') : company_car_atn_div.addClass('d-none');
        data['EMP.BONUS'] ? employment_bonus_div.removeClass('d-none') : employment_bonus_div.addClass('d-none');
        data['M.ONSS'] ? miscellaneous_onss_div.removeClass('d-none') : miscellaneous_onss_div.addClass('d-none');
        data['REP.FEES'] ? representation_fees_div.removeClass('d-none') : representation_fees_div.addClass('d-none');
        data['CAR.PRIV'] ? private_car_amount_div.removeClass('d-none') : private_car_amount_div.addClass('d-none');
        $("div[name='compute_loading']").addClass('d-none');
        $("div[name='net']").removeClass('d-none').hide().slideDown( "slow" );
        $("input[name='NET']").removeClass('o_outdated');
        $("input[name='IP']").val(data['IP']);
        $("input[name='IP.DED']").val(-data['IP.DED']);
        var ip_div = $("div[name='ip_div']");
        data['IP'] ? ip_div.removeClass('d-none') : ip_div.addClass('d-none');
        $("input[name='TAXED']").val(data['TAXED']);
        var taxed_div = $("div[name='taxed_div']");
        data['TAXED'] !== data['NET'] ? taxed_div.removeClass('d-none') : taxed_div.addClass('d-none');
    },

    onchange_advantage: function() {
        $("div[name='net']").addClass('d-none');
        $("div[name='compute_net']").removeClass('d-none');
        $("a[name='details']").addClass('d-none');
        $("a[name='recompute']").removeClass('d-none');
        $("input[name='NET']").addClass('o_outdated');
        this.update_gross();
    },

    onchange_half_name: function() {
        var first_name = $("input[name='first_name']").val();
        var last_name = $("input[name='last_name']").val();
        $("input[name='name']").val(first_name + ' ' + last_name);
    },

    onchange_document: function(input) {
        if (input.target.files) {
            utils.getDataURLFromFile(input.target.files[0]).then(function (testString) {
                var regex = new RegExp(",(.{0,})", "g");
                var img_src = regex.exec(testString)[1];
                if (img_src.startsWith('JVBERi0')) {
                    $('iframe#' + input.target.name + '_pdf').attr('src', testString);
                    $('img#' + input.target.name + '_img').addClass('d-none');
                    $('iframe#' + input.target.name + '_pdf').removeClass('d-none');
                } else {
                    $('img#' + input.target.name + '_img').attr('src', testString);
                    $('img#' + input.target.name + '_img').removeClass('d-none');
                    $('iframe#' + input.target.name + '_pdf').addClass('d-none');
                }
            });
        }
    },

    update_gross: function() {
        var self = this;
        return this.dp.add(
            self._rpc({
                route: '/salary_package/update_gross/',
                params: {
                    'contract_id': parseInt($("input[name='contract']")[0].id),
                    'token': $("input[name='token']").val(),
                    'advantages': self.get_advantages(),
                },
            }).then(function(data) {
                $("input[name='wage']").val(data['new_gross']);
                return self.dp.add(self.compute_net());
            })
        );
    },

    compute_net: function() {
        $("a[name='recompute']").addClass('d-none');
        $("a[name='details']").removeClass('d-none');
        return this.update_gross_to_net_computation();
    },

    onchange_mobility: function(event) {
        $(".mobility-options").addClass('d-none');
        var fuel_card_div = $("div[name='fuel_card']");
        var driving_license_div = $("div[name='driving_license']");
        if ($("input[name='transport_mode_car']")[0].checked) {
            $(".mobility-options#company_car").removeClass('d-none');
            fuel_card_div.removeClass('d-none');
            driving_license_div.removeClass('d-none');
        } else {
            $("input[name='fuel_card_input']").val(0.0);
            $("input[name='fuel_card_slider']").val(0.0);
            fuel_card_div.addClass('d-none');
            driving_license_div.addClass('d-none');

        }
        if ($("input[name='transport_mode_public']")[0].checked){
            $(".mobility-options#public_transport").removeClass('d-none');
        }
        if ($("input[name='transport_mode_private_car']")[0].checked){
            $(".mobility-options#private_car").removeClass('d-none');
            $("input[name='private_car_km_home_work']").trigger('change');
        }
    },

    onchange_waiting_list: function() {
        var select_waiting_list_model = $("select[name='select_waiting_list_model']");
        if ($("input[name='waiting_list']")[0].checked) {
            select_waiting_list_model.removeClass('d-none');
        } else {
            select_waiting_list_model.addClass('d-none');
        }
    },

    onchange_representation_fees: function(event) {
        $("input[name='representation_fees']").val(event.target.value);
    },

    onchange_fuel_card: function(event) {
        $("input[name='fuel_card_input']").val(event.target.value);
    },

    onchange_holidays: function(event) {
        var amount_days = $("input[name='holidays_slider']").val();
        $("input[name='holidays_input']").val(amount_days);
    },

    // TODO Restring to useful arguments
    onchange_mobile: function(event) {
        var self = this;
        var has_mobile = $("input[name='mobile']")[1].checked;
        var tooltip = $("span#mobile_tooltip");
        var mobile_invoice_div = $("div[name='mobile_invoice']");
        var sim_card_div = $("div[name='sim_card']");
        has_mobile ? tooltip.removeClass('d-none') : tooltip.addClass('d-none');
        has_mobile ? mobile_invoice_div.removeClass('d-none') : mobile_invoice_div.addClass('d-none');
        has_mobile ? sim_card_div.removeClass('d-none') : sim_card_div.addClass('d-none');
        this._rpc({
            route: '/salary_package/onchange_mobile/',
            params: {
                'has_mobile': $("input[name='mobile']")[1].checked,
            },
        }).then(function(amount) {
            $("input[name='mobile_amount']").val(amount);
        });
    },

    onchange_internet: function(event) {
        var internet = parseInt($("input[name='internet']")[0].value);
        var tooltip = $("span#internet_tooltip");
        var internet_invoice_div = $("div[name='internet_invoice']");
        internet ? tooltip.removeClass('d-none') : tooltip.addClass('d-none');
        internet ? internet_invoice_div.removeClass('d-none') : internet_invoice_div.addClass('d-none');
        $("input[name='internet_amount']").val($("input[name='internet']")[0].value);
    },

    onchange_car_id: function(event) {
        var car_value = $("select[name='select_car']").val();
        var car_option = car_value ? (car_value).split('-')[0] : '';
        var vehicle_id = car_value ? parseInt((car_value).split('-')[1]) : '';
        this._rpc({
            route: '/salary_package/onchange_car',
            params: {
                'car_option': car_option,
                'vehicle_id': vehicle_id,
            },
        }).then(function(data) {
            for(var key in data) {
                if (data[key]) {
                    $("span[name='" + key + "']").html(data[key]);
                    $("li[name='" + key + "']").removeClass('d-none');
                } else {
                    $("li[name='" + key + "']").addClass('d-none');
                }
            }
        });
        $("span[name='car_info']").removeClass('d-none');
        if (car_option === 'new') {
            $("span[name='new_car_message']").removeClass('d-none');
        } else {
            $("span[name='new_car_message']").addClass('d-none');
            this.onchange_advantage();
        }
    },

    onchange_public_transport: function(event) {
        this._rpc({
            route: '/salary_package/onchange_public_transport/',
            params: {
                'public_transport_employee_amount': parseFloat($("input[name='public_transport_employee_amount']")[0].value) || 0.0,
            },
        }).then(function(amount) {
            $("input[name='public_transport_reimbursed_amount']").val(amount);
        });
    },

    onchange_marital: function(event) {
        var marital = $("select[name='marital']").val();
        var spouse_info_div = $("div[name='spouse_information']");
        $("div[name='spouse_fiscal_status']").addClass('d-none');
        var spouse_professional_situation_div = $("div[name='spouse_professional_situation']");
        if (marital === 'married' || marital === 'cohabitant') {
            spouse_info_div.removeClass('d-none');
            $("input[name='spouse_birthdate']").attr('required', '');
            $("input[name='spouse_complete_name']").attr('required', '');
            $("input[name='spouse_professional_situation']").attr('required', '');
            $("input[name='disabled_spouse_bool']").attr('required', '');
            spouse_professional_situation_div.removeClass('d-none');
        } else {
            spouse_info_div.addClass('d-none');
            $("input[name='spouse_birthdate']").removeAttr('required');
            $("input[name='spouse_complete_name']").removeAttr('required');
            $("input[name='spouse_professional_situation']").removeAttr('required');
            $("input[name='disabled_spouse_bool']").removeAttr('required');
            spouse_professional_situation_div.addClass('d-none');
        }
    },

    onchange_spouse_fiscal_status: function(event) {
        var fiscal_status = $("select[name='spouse_fiscal_status']").val();
        var spouse_revenue_info_div = $("div[name='spouse_revenue_information']");
        spouse_revenue_info_div.addClass('d-none');
    },

    onchange_disabled_children: function(event) {
        var disabled_children = $("input[name='disabled_children_bool']")[0].checked;
        var disabled_children_div = $("div[name='disabled_children_info']");
        disabled_children ? disabled_children_div.removeClass('d-none') : disabled_children_div.addClass('d-none');
    },

    onchange_other_dependent_people: function(event) {
        var other_dependent_people = $("input[name='other_dependent_people']")[0].checked;
        var other_dependent_people_div = $("div[name='other_dependent_people_info']");
        other_dependent_people ? other_dependent_people_div.removeClass('d-none') : other_dependent_people_div.addClass('d-none');
    },

    onchange_ip: function(event) {
        var has_ip = $("input[name='ip']")[0].checked;
        var tooltip = $("span#ip_tooltip");
        has_ip ? tooltip.removeClass("d-none") : tooltip.addClass("d-none");
    },

    onchange_km_home_work: function(event) {
        var distance = event.currentTarget.value || 0;
        _.each($("input.km_home_work"), function(input) {
            $(input).val(distance); // set the same distance on both inputs
        });
        this._rpc({
            route: '/salary_package/onchange_km_home_work/',
            params: {
                distance: parseInt(distance),
            }
        }).then(function (amount) {
            $("input[name='private_car_reimbursed_amount']").val(amount);
        });
    },

    onchange_spouse_professional_situation: function() {
        var situation = $("select[name='spouse_professional_situation']").val();
        if (situation === 'without_income') {
            $("select[name='spouse_fiscal_status']").val("without income").change();
            $("input[name='spouse_net_revenue']").val(0);
            $("input[name='spouse_other_net_revenue']").val(0);
        } else {
            $("select[name='spouse_fiscal_status']").val("with income").change();
            if (situation === 'low_income') {
                $("input[name='spouse_net_revenue']").val(1);
                $("input[name='spouse_other_net_revenue']").val(0);
            } else if (situation === 'high_income') {
                $("input[name='spouse_net_revenue']").val(500);
                $("input[name='spouse_other_net_revenue']").val(0);
            } else if (situation === 'low_pension') {
                $("input[name='spouse_net_revenue']").val(0);
                $("input[name='spouse_other_net_revenue']").val(1);
            } else if (situation === 'high_pension') {
                $("input[name='spouse_net_revenue']").val(0);
                $("input[name='spouse_other_net_revenue']").val(500);
            }
        }
    },

    recompute: function(event) {
        $("a[name='details']").removeClass('d-none');
        $("a[name='recompute']").addClass('d-none');
        $("input[name='NET']").removeClass('o_outdated');
    },

    check_form_validity: function() {
        var required_empty_input = _.find($("input:required"), function(input) {return input.value === ''; });
        var required_empty_select = _.find($("select:required"), function(select) {return $(select).val() === ''; });
        var email = $("input[name='email']").val();
        var atpos = email.indexOf("@");
        var dotpos = email.lastIndexOf(".");
        var invalid_email = atpos<1 || dotpos<atpos+2 || dotpos+2>=email.length;
        if(required_empty_input || required_empty_select) {
            $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade show'>" + _('Some required fields are not filled') + "</div>");
            _.each($("input:required"), function(input) {
                if (input.value === '') {
                    $(input).addClass('bg-danger');
                } else {
                    $(input).removeClass('bg-danger');
                }
            });
            _.each($("select:required"), function(select) {
                if ($(select).val() === '') {
                    $(select).parent().find('.select2-choice').addClass('bg-danger');
                } else {
                    $(select).parent().find('.select2-choice').removeClass('bg-danger');
                }
            });
            $("section#hr_cs_personal_information")[0].scrollIntoView({block: "end", behavior: "smooth"});
        }
        if (invalid_email) {
            $("input[name='email']").addClass('bg-danger');
            $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade show'>" + _('Not a valid e-mail address') + "</div>");
            $("section#hr_cs_personal_information")[0].scrollIntoView({block: "end", behavior: "smooth"});
        } else {
            $("input[name='email']").removeClass('bg-danger');
        }
        $(".alert").delay(4000).slideUp(200, function() {
            $(this).alert('close');
        });
        return !invalid_email && !required_empty_input && !required_empty_select;
    },

    get_form_info: function() {
        var self = this;
        return Promise.resolve(self.get_personal_documents()).then(function(personal_documents) {
            var advantages = self.get_advantages();
            _.extend(advantages.personal_info, personal_documents);

            return {
                'contract_id': parseInt($("input[name='contract']")[0].id),
                'token': $("input[name='token']").val(),
                'advantages': advantages,
                'applicant_id': parseInt($("input[name='applicant_id']").val()) || false,
                'employee_contract_id': parseInt($("input[name='employee_contract_id']").val()) || false,
                'original_link': $("input[name='original_link']").val()
            };
        });
    },

    send_offer_to_responsible: function(event) {
        var self = this;
        if (this.check_form_validity()) {
            self._rpc({
                route: '/salary_package/send_email/',
                params: {
                    'contract_id': parseInt($("input[name='contract']")[0].id),
                    'token': $("input[name='token']").val(),
                    'advantages': self.get_advantages(),
                    'applicant_id': parseInt($("input[name='applicant_id']").val()) || false,
                    'original_link': $("input[name='original_link']").val(),
                    'contract_type': $("input[name='contract_type']").val(),
                    'job_title': $("input[name='job_title']").val(),
                },
            }).then(function (data) {
                document.location.pathname = '/salary_package/thank_you/' + data;
            });
        }
    },

    submit_salary_package: function(event) {
        var self = this;
        if (this.check_form_validity()) {
            self.get_form_info().then(function(form_info) {
                self._rpc({
                    route: '/salary_package/submit/',
                    params: form_info,
                }).then(function (data) {
                    if (data['error']) {
                        $("button#hr_cs_submit").parent().append("<div class='alert alert-danger alert-dismissable fade show'>" + data['error_msg'] + "</div>");
                    } else {
                        document.location.pathname = '/sign/document/' + data['request_id'] + '/' + data['token'];
                    }
                });
            })
        }
    },

    toggle_personal_information: function() {
        $("button[name='toggle_personal_information']").toggleClass('d-none');
        $("div[name='personal_info']").toggle(500);
        $("div[name='personal_info_withholding_taxes']").toggle(500);
    },
});

return publicWidget.registry.SalaryPackageWidget;
});
