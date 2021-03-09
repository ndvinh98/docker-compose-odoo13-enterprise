odoo.define('web.menu_tests', function (require) {
"use strict";

var testUtils = require('web.test_utils');
var testUtilsEnterprise = require('web_enterprise.test_utils');

QUnit.module('web_enterprise_menu_tests', {
    beforeEach: function () {
        this.data = {
            all_menu_ids: [3, 4, 5, 6, 7, 8],
            name: "root",
            children: [{
                id: 3,
                name: "CRM",
                children: [{
                    id: 4,
                    name: "Contacts",
                    children: [{
                        id: 7,
                        name: "Contact Tags",
                        children: [],
                    }],
                }, {
                    id: 5,
                    name: "Report",
                    children: [],
                },{
                    id: 6,
                    name: "Configuration",
                    children: [{
                        id: 8,
                        name: "Settings",
                        children: [],
                    }],
                 }],
           }],
        };
    }
}, function () {

    QUnit.module('Menu');

    QUnit.test('Menu rendering', async function (assert) {
        assert.expect(6);
        var menu = await testUtilsEnterprise.createMenu({ menuData: this.data });
        menu.change_menu_section(3);
        assert.ok(menu.$('ul.o_menu_sections').length, "should display the 'Menu'");
        assert.notOk(menu.$('ul.o_menu_sections > li.show').length,
            "shouldn't have menu dropdown");
        // First menu
        await testUtils.dom.click(menu.$('.o_menu_sections > li > a').first());
        assert.isVisible(menu.$('.o_menu_sections > li:eq(0).show'),
            "should have first menu and it's children in dropdown");
        // Second menu
        menu.$('.o_menu_sections > li > a.o_menu_entry_lvl_1').trigger('mouseover'); //.trigger('click');
        assert.notOk(menu.$('.o_menu_sections > li:eq(0).show').length,
            "first menu shouldn't have show class");
        assert.isVisible(menu.$('.o_menu_sections > li:eq(1).show'),
            "second menu should have show class");
        // Third menu
        menu.$('.o_menu_sections > li > a').last().trigger('mouseover');
        assert.isVisible(menu.$('.o_menu_sections > li:eq(2).show'),
            "should have third menu and children in dropdown");
        menu.destroy();
    });
});
});
