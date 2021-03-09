odoo.define('hr_contract_salary.tour', function (require) {
'use strict';

var Tour = require('web_tour.tour');

Tour.register('hr_contract_salary_tour', {
        test: true,
        url: '/',
        wait_for: Promise.resolve(odoo.__TipTemplateDef)
    },[
        {
            content: "Go on configurator",
            trigger: 'nav.o_main_navbar',
            run: function () {
                window.location.href = window.location.origin + '/web';
            },
        },
        {
            content: "Log into Belgian Company",
            trigger: '.o_menu_systray .o_switch_company_menu > a',
            run: 'click',
        },
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu .dropdown-item span:contains('Belgian')",
            run: 'click',
        },
        {
            content: "Recruitment",
            trigger: 'a[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
            extra_trigger: ".o_menu_systray .o_switch_company_menu > a > span:contains('Belgian')",
            run: 'click',
        },
        {
            content: "Create Job Position",
            trigger: 'div.o_cp_buttons .o-kanban-button-new',
            extra_trigger: '.o_control_panel .breadcrumb:contains("Job Positions")',
            run: 'click',
        },
        {
            content: "Job\'s Name",
            trigger: "div.modal-dialog input[name='name']",
            run: 'text Experienced Developer (BE)',
        },
        {
            content: "Job\'s Name",
            trigger: "div.modal-dialog button[name='close_dialog']",
            run: 'click',
        },
        {
            content: "Select Experienced Developer",
            trigger: ".o_kanban_record:contains('Experienced Developer') .oe_kanban_action_button",
            run: 'click',
        },
        {
            content: "Create Applicant",
            trigger: '.o_cp_buttons .o-kanban-button-new',
            extra_trigger: 'li.active:contains("Applications")',
            run: 'click',
        },
        {
            content: "Application Name",
            trigger: '.oe_title input[name="name"]',
            run: "text Mitchell's Application",
        },
        {
            content: "Applicant\'s Name",
            trigger: '.oe_title input[name="partner_name"]',
            run: 'text Mitchell Admin',
        },
        {
            content: "Create Employee",
            trigger: ".o_statusbar_buttons > button[name='create_employee_from_applicant']",
            extra_trigger: ".o_statusbar_buttons",
            run: 'click',
        },
        {
            content: "Confirm Employee Creation",
            trigger: ".btn-primary",
            run: 'click'
        },
        {
            content: "Add Manager",
            trigger: ".nav-link:contains('Work Information')",
            run: 'click',
        },
        {
            content: "Manager",
            trigger: '.o_field_widget.o_field_many2one[name=parent_id]',
            run: function (actions) {
                actions.text("Mitchell", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains(Mitchell)",
            auto: true,
        },
        {
            content: "Save",
            trigger: '.o_form_buttons_edit .o_form_button_save',
            extra_trigger: '.o_form_statusbar .o_statusbar_buttons:contains("Launch Plan")',
            run: 'click',
        },
        {
            content: "Create Contract",
            trigger: '.oe_button_box .oe_stat_button:contains("Contracts")',
            extra_trigger: '.o_cp_buttons .btn-primary.o_form_button_edit',
            run: 'click',
        },
        {
            content: "Create",
            trigger: '.o_cp_buttons .o-kanban-button-new',
            extra_trigger: 'li.active:contains("Contracts")',
            run: 'click',
        },
        {
            content: "Contract Reference",
            trigger: '.oe_title input[name="name"]',
            run: 'text Mitchell Admin PFI Contract',
        },
        {
            content: "Salary Structure Type",
            trigger: '.o_field_widget.o_field_many2one[name=structure_type_id]',
            run: function (actions) {
                actions.text("CP200", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains('Belgian Employee')",
            auto: true,
        },
        {
            content: "HR Responsible",
            trigger: '.o_field_widget.o_field_many2one[name=hr_responsible_id]',
            run: function (actions) {
                actions.text("Laurie Poiret", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains('Laurie Poiret')",
            auto: true,
        },
        {
            content: "Contract Update Template",
            trigger: '.o_field_widget.o_field_many2one[name=contract_update_template_id]',
            run: function (actions) {
                actions.text("employee_contract", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains('employee_contract')",
            auto: true,
        },
        {
            content: "Contract Information",
            trigger: ".o_content .o_form_view .o_notebook li.nav-item:eq(1) a",
            run: "click",
        },
        {
            content: "Contract Information",
            trigger: "div.o_input[name='wage'] input",
            run: "text 2950",
        },
        {
            content: "Contract Information",
            trigger: "div.o_input[name='fuel_card'] input",
            run: "text 250",
        },
        {
            content: "Contract Information",
            trigger: "div.o_input[name='commission_on_target'] input",
            run: "text 1000",
        },
        {
            content: "Contract Information",
            trigger: "div.o_field_boolean[name='transport_mode_car'] input",
            run: "click",
        },
        {
            content: "Contract Information",
            trigger: '.o_field_widget.o_field_many2one[name=car_id]',
            run: function (actions) {
                actions.text("JFC", this.$anchor.find("input"));
            },
        },
        {
            trigger: ".ui-autocomplete > li > a:contains('1-JFC-095')",
            auto: true,
        },
        {
            content: "Contract Information",
            trigger: "input.o_input[name='ip_wage_rate']",
            run: "text 25",
        },
        {
            content: "Contract Information",
            trigger: "div.o_field_boolean[name='ip'] input",
            run: "click",
        },
        {
            content: "Generate Simulation Link",
            trigger: ".o_statusbar_buttons > button.btn-primary span:contains('Simulation')",
            extra_trigger: ".o_statusbar_buttons",
            run: 'click',
        },
        {
            content: "Send Offer",
            trigger: "button[name='send_offer']",
            run: 'click',
        },
        {
            content: "Confirm Partner Creation",
            trigger: ".modal-dialog .btn-primary span:contains('Save')",
            run: 'click'
        },
        {
            content: "Send Offer",
            trigger: "button[name='action_send_mail']",
            run: 'click',
        },
        {
            content: "Go on configurator",
            trigger: '.o_mail_thread .o_thread_message:eq(0) a',
            run: function () {
                var simulation_link = $(".o_mail_thread .o_thread_message:eq(0) a")[0].href;
                // Retrieve the link without the origin to avoid
                // mismatch between localhost:8069 and 127.0.0.1:8069
                // when running the tour with chrome headless
                var regex = '/salary_package/simulation/.*';
                var url = simulation_link.match(regex)[0];
                window.location.href = window.location.origin + url;
            },
        },
        {
            content: "BirthDate",
            trigger: 'input[name="birthdate"]',
            run: function () {
                $("input[name='birthdate']").val('2017-09-01');
            },
        },
        {
            content: "National Identification Number",
            trigger: 'input[name="identification_id"]',
            run: 'text 11.11.11-111.11',
        },
        {
            content: "Street",
            trigger: 'input[name="street"]',
            run: 'text Rue des Wallons',
        },
        {
            content: "City",
            trigger: 'input[name="city"]',
            run: 'text Louvain-la-Neuve',
        },
        {
            content: "Zip Code",
            trigger: 'input[name="zip"]',
            run: 'text 1348',
        },
        {
            content: "Email",
            trigger: 'input[name="email"]',
            run: 'text mitchell.stephen@example.com',
        },
        {
            content: "Phone Number",
            trigger: 'input[name="phone"]',
            run: 'text 1234567890',
        },
        {
            content: "Phone Number",
            trigger: 'input[name="place_of_birth"]',
            run: 'text Brussels',
        },
        {
            content: "KM Home/Work",
            trigger: 'input[name="km_home_work"]',
            run: 'text 75',
        },
        {
            content: "Certificate",
            trigger: 'label[for=certificate]',
            run: function () {
                $('select[name=certificate] option:contains(Master)').prop('selected', true);
                $('select[name=certificate]').trigger('change');
            },
        },
        {
            content: "School",
            trigger: 'input[name="study_school"]',
            run: 'text UCL',
        },
        {
            content: "School Level",
            trigger: 'input[name="study_field"]',
            run: 'text Civil Engineering, Applied Mathematics',
        },
        {
            content: "Bank Account",
            trigger: 'input[name="bank_account"]',
            run: 'text BE10 3631 0709 4104',
        },
        {
            content: "Bank Account",
            trigger: 'input[name="emergency_contact"]',
            run: 'text Batman',
        },
        {
            content: "Bank Account",
            trigger: 'input[name="emergency_phone"]',
            run: 'text +32 2 290 34 90',
        },
        {
            content: "Nationality",
            trigger: 'label[for=country_id]',
            run: function () {
                $('select[name=country_id] option:contains(Belgium)').prop('selected', true);
                $('select[name=country_id]').trigger('change');
            },
        },
        {
            content: "Country of Birth",
            trigger: 'label[for=country_of_birth]',
            run: function () {
                $('select[name=country_of_birth] option:contains(Belgium)').prop('selected', true);
                $('select[name=country_of_birth]').trigger('change');
            },
        },
        {
            content: "Country",
            trigger: 'label[for=country]',
            run: function () {
                $('select[name=country] option:contains(Belgium)').prop('selected', true);
                $('select[name=country]').trigger('change');
            },
        },
        {
            content: "submit",
            trigger: 'button#hr_cs_submit',
            run: 'click',
        },
        {
            content: "Next",
            trigger: 'iframe .o_sign_sign_item_navigator',
            run: 'click',
        },
        {
            content: "Type Date",
            trigger: 'iframe input.ui-selected',
            run: 'text 17/09/2018',
        },
        {
            content: "Next",
            trigger: 'iframe .o_sign_sign_item_navigator',
            run: 'click',
        },
        {
            content: "Type Number",
            trigger: 'iframe input.ui-selected',
            run: 'text 58/4',
        },
        // fill signature
        {
            content: "Next",
            trigger: 'iframe .o_sign_sign_item_navigator',
            run: 'click',
        },
        {
            content: "Click Signature",
            trigger: 'iframe button.o_sign_sign_item',
            run: 'click',
        },
        {
            content: "Click Auto",
            trigger: "a.o_web_sign_auto_button:contains('Auto')",
            run: 'click',
        },
        {
            content: "Adopt and Sign",
            trigger: 'footer.modal-footer button.btn-primary:enabled',
            run: 'click',
        },
        {
            content: "Wait modal closed",
            trigger: 'iframe body:not(:has(footer.modal-footer button.btn-primary))',
            run: function () {},
        },
        // fill date
        {
            content: "Next",
            trigger: 'iframe .o_sign_sign_item_navigator:contains("next")',
            run: 'click',
        },
        {
            content: "Type Date",
            trigger: 'iframe input.ui-selected',
            run: function (actions) {
                var self = this;
                setTimeout(function () {
                    actions.text("17/09/2018", self.$anchor);
                }, 10)
            },
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: 'click',
        },
        {
            content: "Go on configurator",
            trigger: 'nav.o_main_navbar',
            run: function () {
                window.location.href = window.location.origin + '/web';
            },
        },
    ]
);

});
