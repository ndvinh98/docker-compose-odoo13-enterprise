odoo.define('account_accountant.dashboard.setup.tour', function (require) {
"use strict";

const { _t } = require('web.core');
const tour = require('web_tour.tour');

const { steps } = tour.tours.account_render_report;
const accountMenuClickIndex = steps.findIndex(step => step.id === 'account_menu_click');

steps.splice(accountMenuClickIndex, 1, {
    trigger: '.o_app[data-menu-xmlid="account_accountant.menu_accounting"]',
    position: 'bottom',
}, {
    trigger: `a:contains(${_t("Customer Invoices")})`,
});

});
