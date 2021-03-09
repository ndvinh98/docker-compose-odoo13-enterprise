odoo.define('website_sale_dashboard.WebsiteSaleDashboardView', function (require) {
"use strict";

/**
 * This file defines the WebsiteSaleDashboard view and adds it to the view registry.
 * The only difference with Dashboard View is that it has a control panel with a
 * "Go to website" button.
 */

var DashboardView = require('web_dashboard.DashboardView');
var viewRegistry = require('web.view_registry');
var WebsiteSaleDashboardController = require('website_sale_dashboard.WebsiteSaleDashboardController');

var WebsiteSaleDashboardView = DashboardView.extend({

    config: _.extend({}, DashboardView.prototype.config, {Controller: WebsiteSaleDashboardController}) ,

});

viewRegistry.add('website_sale_dashboard', WebsiteSaleDashboardView);

return WebsiteSaleDashboardView;

});
