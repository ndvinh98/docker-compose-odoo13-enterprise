odoo.define('website_sale_dashboard.website_sale_dashboard_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var WebsiteSaleDashboardView = require('website_sale_dashboard.WebsiteSaleDashboardView');

var createView = testUtils.createView;

QUnit.module('Views', {
    beforeEach: function () {
        this.data = {
            test_report : {
                fields: {},
                records: [],
            },
        };
    }
}, function () {

    QUnit.module('WebsiteSaleDashboardView');

    QUnit.test('The website sale dashboard view has a "Go to Website" Button', async function (assert) {
        assert.expect(1);

        var dashboard = await createView({
            View: WebsiteSaleDashboardView,
            model: 'test_report',
            data: this.data,
            arch: '<dashboard js_class="website_sale_dashboard"></dashboard>',
        });

        assert.containsOnce(dashboard.$buttons, '.btn-primary[title="Go to Website"]',
            "the control panel should contain a 'Go to Website' button");

        dashboard.destroy();
    });
});

});
