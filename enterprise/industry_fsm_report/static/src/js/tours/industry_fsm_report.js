odoo.define("industry_fsm_report.tour", function (require) {
"use strict";
/**
 * Add custom steps to take worksheets into account
 */
var tour = require('web_tour.tour');
    require('industry_fsm.tour');
var core = require('web.core');
var _t = core._t;

var fsmStartStepIndex = _.findIndex(tour.tours.industry_fsm_tour.steps, function (step) {
    return (step.id === 'fsm_start');
});

tour.tours.industry_fsm_tour.steps.splice(fsmStartStepIndex + 1, 0, {
    trigger: 'button[name="action_fsm_worksheet"]',
    extra_trigger: 'button[name="action_timer_stop"]',
    content: _t('Fill in your worksheet with the details of your intervention.'),
    position: 'bottom',
}, {
    trigger: ".o_form_button_save",
    content: _t('Save the worksheet.'),
    extra_trigger: '.o_fsm_worksheet_form',
}, {
    trigger: ".breadcrumb-item:not(.active):last",
    extra_trigger: '.o_fsm_worksheet_form',
    content: _t("Use the breadcrumbs to <b>go back to your task</b>."),
    position: "right"

});

var fsmSaveTimesheetStepIndex = _.findIndex(tour.tours.industry_fsm_tour.steps, function (step) {
    return (step.id === 'fsm_save_timesheet');
});

tour.tours.industry_fsm_tour.steps.splice(fsmSaveTimesheetStepIndex + 1, 0, {
    trigger: 'button[name="action_preview_worksheet"]',
    extra_trigger: '.o_fsm_task_form',
    content: _t('Review the worksheet report with your customer and ask him to sign it.'),
    position: 'bottom',
}, {
    trigger: 'a[data-target="#modalaccept"]',
    extra_trigger: 'div[id="o_fsm_worksheet_portal"]',
    content: _t('Make the client sign the worksheet.'),
    position: 'bottom',
}, {
    trigger: '.o_web_sign_auto_button',
    extra_trigger: 'div[id="o_fsm_worksheet_portal"]',
    content: _t('The client may click Auto or draw it manually.'),
    position: 'right',
}, {
    trigger: '.o_portal_sign_submit:enabled',
    extra_trigger: 'div[id="o_fsm_worksheet_portal"]',
    content: _t('Validate the signature.'),
    position: 'right',
}, {
    trigger: 'a:contains(Back to edit mode)',
    extra_trigger: 'div[id="o_fsm_worksheet_portal"]',
    content: _t('Get back to the task in backend.'),
    position: 'right',
}, {
    trigger: 'button[name="action_send_report"]',
    extra_trigger: '.o_fsm_task_form ',
    content: _t('Send the report to your customer by email.'),
    position: 'bottom',
}, {
    trigger: 'button[name="action_send_mail"]',
    extra_trigger: '.o_fsm_task_form ',
    content: _t('<b>Click the send button</b> to send the report.'),
    position: 'bottom',
});

});
