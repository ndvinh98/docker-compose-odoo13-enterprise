odoo.define('website_calendar.select_appointment_type', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.websiteCalendarSelect = publicWidget.Widget.extend({
    selector: '.o_website_calendar_appointment',
    events: {
        'change .o_website_appoinment_form select[id="calendarType"]': '_onAppointmentTypeChange'
    },

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        // Check if we cannot replace this by a async handler once the related
        // task is merged in master
        this._onAppointmentTypeChange = _.debounce(this._onAppointmentTypeChange, 250);
    },
    /**
     * @override
     * @param {Object} parent
     */
    start: function (parent) {
        // set default timezone
        var timezone = jstz.determine();
        $(".o_website_appoinment_form select[name='timezone']").val(timezone.name());
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * On appointment type change: adapt appointment intro text and available
     * employees (if option enabled)
     *
     * @override
     * @param {Event} ev
     */
    _onAppointmentTypeChange: function (ev) {
        var appointmentID = $(ev.target).val();
        var previousSelectedEmployeeID = $(".o_website_appoinment_form select[name='employee_id']").val();
        var postURL = '/website/calendar/' + appointmentID + '/appointment';
        $(".o_website_appoinment_form").attr('action', postURL);
        this._rpc({
            route: "/website/calendar/get_appointment_info",
            params: {
                appointment_id: appointmentID,
                prev_emp: previousSelectedEmployeeID,
            },
        }).then(function (data) {
            if (data) {
                $('.o_calendar_intro').html(data.message_intro);
                if (data.assignation_method === 'chosen') {
                    $(".o_website_appoinment_form div[name='employee_select']").replaceWith(data.employee_selection_html);
                } else {
                    $(".o_website_appoinment_form div[name='employee_select']").addClass('o_hidden');
                    $(".o_website_appoinment_form select[name='employee_id']").children().remove();
                }
            }
        });
    },
});
});

//==============================================================================

odoo.define('website_calendar.appointment_form', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.websiteCalendarForm = publicWidget.Widget.extend({
    selector: '.o_website_calendar_form',
    events: {
        'change .appointment_submit_form select[name="country_id"]': '_onCountryChange',
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {Event} ev
     */
    _onCountryChange: function (ev) {
        var countryCode = $(ev.target).find('option:selected').data('phone-code');
        $('.appointment_submit_form #phone_field').val(countryCode);
    },
});
});
