odoo.define('account_accountant_reports_widgets.tour', function (require) {
"use strict";

var tour = require('web_tour.tour');

tour.register('account_reports_widgets', {
    test: true,
    url: '/web?#action=account_reports.action_account_report_pnl',
},
    [
        {
            content: "wait web client",
            trigger: ".o_account_reports_body",
            extra_trigger: ".breadcrumb",
            run: function () {}
        },
        {
            content: "unfold line",
            trigger: '.js_account_report_foldable:first',
            run: 'click',
        },
        {
            content: "check that line has been unfolded",
            trigger: '[data-parent-id]',
        },
        {
            content: 'Open dropdown menu of one of the unfolded line',
            trigger: '[data-parent-id] .o_account_report_line a:first',
            run: 'click',
        },
        {
            content: 'click on the annotate action',
            trigger: '[data-parent-id] .o_account_report_line .o_account_reports_domain_dropdown:first .js_account_reports_add_footnote',
            run: 'click',
        },
        {
            content: 'insert footnote text',
            trigger: '.js_account_reports_footnote_note',
            run: 'text My awesome footnote!'
        },
        {
            content: 'save footnote',
            trigger: '.modal-footer .btn-primary',
            run: 'click'
        },
        {
            content: 'wait for footnote to be saved',
            trigger: '.footnote#footnote1 .text:contains(1. My awesome footnote!)',
            extra_trigger: '.o_account_reports_footnote_sup a[href="#footnote1"]',
        },
        {
            content: "change date filter",
            trigger: ".o_account_reports_filter_date > a",
        },
        {
            content: "change date filter",
            trigger: ".dropdown-item.js_account_report_date_filter[data-filter='last_year']",
            run: 'click'
        },
        {
            content: "wait refresh",
            trigger: ".o_account_reports_level2:last() .o_account_report_column_value:contains(0.00)"
        },
        {
            content: "change comparison filter",
            trigger: ".o_account_reports_filter_date_cmp > a"
        },
        {
            content: "change comparison filter",
            trigger: ".dropdown-item.js_foldable_trigger[data-filter='previous_period_filter']"
        },
        {
            content: "change comparison filter",
            trigger: ".js_account_report_date_cmp_filter[data-filter='previous_period']",
            run: 'click',
        },
        {
            content: "wait refresh, report should have 4 columns",
            trigger: "th + th + th + th"
        },
        {
            content: "change boolean filter",
            trigger: ".o_account_reports_filter_bool > a",
        },
        {
            title: "export xlsx",
            trigger: 'button[action="print_xlsx"]',
            run: 'click'
        },
    ]
);

});
