odoo.define('web_enterprise.mobile_menu_tests', function (require) {
"use strict";

var Menu = require('web_enterprise.Menu');
var testUtils = require('web.test_utils');
var testUtilsEnterprise = require('web_enterprise.test_utils');
var UserMenu = require('web.UserMenu');

QUnit.module('web_enterprise mobile_menu_tests', {
    afterEach() {
        testUtils.mock.unpatch(Menu);
    },
    beforeEach: function () {
        testUtils.mock.patch(Menu, {
            animationDuration: 0
        });
        // LUL TODO adapt the company switcher widget to handle empty session
        this.session = {
            user_companies: {
                allowed_companies: [[1, "Company 1"]],
                current_company: [1, "Company 1"],
            },
            user_context: { allowed_company_ids: "1" },
        };
        this.data = {
            all_menu_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            name: "root",
            children: [{
                id: 1,
                name: "Discuss",
                children: [],
             }, {
                 id: 2,
                 name: "Calendar",
                 children: []
             }, {
                id: 3,
                name: "Contacts",
                children: [{
                    id: 4,
                    name: "Contacts",
                    children: [],
                }, {
                    id: 5,
                    name: "Configuration",
                    children: [{
                        id: 6,
                        name: "Contact Tags",
                        children: [],
                    }, {
                        id: 7,
                        name: "Contact Titles",
                        children: [],
                    }, {
                        id: 8,
                        name: "Localization",
                        children: [{
                            id: 9,
                            name: "Countries",
                            children: [],
                        }, {
                            id: 10,
                            name: "Fed. States",
                            children: [],
                        }],
                    }],
                 }],
           }],
        };
    }
}, function () {

    QUnit.module('Burger Menu');

    QUnit.test('Burger Menu on home menu', async function (assert) {
        assert.expect(3);

        const mobileMenu = await testUtilsEnterprise.createMenu({
            menuData: this.data,
            session: this.session,
        });

        if (mobileMenu.$burgerMenu.length) {
            var menuInMobileMenu = mobileMenu.$burgerMenu[0].querySelector('.o_burger_menu_user');
            assert.ok(menuInMobileMenu !== null, 'node with class o_burger_menu_user must be in Burger menu');
            if (menuInMobileMenu) {
                var subMenuInMobileMenu = menuInMobileMenu.querySelector('.o_user_menu_mobile');
                assert.ok(subMenuInMobileMenu !== null, 'sub menu (.o_user_menu_mobile) must be in Burger menu');
            }
        }

        await testUtils.dom.click(mobileMenu.$('.o_mobile_menu_toggle'));
        assert.isVisible($(".o_burger_menu"),
            "Burger menu should be opened on button click");
        await testUtils.dom.click($('.o_burger_menu_close'));

        mobileMenu.destroy();
    });

    QUnit.test('Burger Menu on an App', async function (assert) {
        assert.expect(4);

        const mobileMenu = await testUtilsEnterprise.createMenu({
            menuData: this.data,
            session: this.session,
        });

        mobileMenu.change_menu_section(3);
        mobileMenu.toggle_mode(false);

        await testUtils.dom.click(mobileMenu.$('.o_mobile_menu_toggle'));
        assert.isVisible($(".o_burger_menu"),
            "Burger menu should be opened on button click");
        assert.strictEqual($('.o_burger_menu .o_burger_menu_app .o_menu_sections > *').length, 2,
            "Burger menu should contains top levels menu entries");
        await testUtils.dom.click($('.o_burger_menu_topbar'));
        assert.doesNotHaveClass($(".o_burger_menu_content"), 'o_burger_menu_dark',
            "Toggle to usermenu on header click");
        await testUtils.dom.click($('.o_burger_menu_topbar'));
        assert.hasClass($(".o_burger_menu_content"),'o_burger_menu_dark',
            "Toggle back to main sales menu on header click");

        mobileMenu.destroy();
    });

    QUnit.test('Burger menu is closed when it do_action', async function (assert) {
        assert.expect(2);
        testUtils.mock.patch(UserMenu, {
            _onMenuSettings() {
                this.do_action()
            },
        });

        const mobileMenu = await testUtilsEnterprise.createMenu({
            menuData: this.data,
            session: this.session,
            intercepts: {
                do_action: function (ev) {
                    ev.data.on_success();
                    return Promise.resolve();
                },
            },
        });

        await testUtils.dom.click($('.o_mobile_menu_toggle'));
        assert.isVisible($(".o_burger_menu"), "Burger menu should be opened on button click");

        await testUtils.dom.click($('.o_user_menu_mobile a[data-menu="settings"]'));
        assert.isNotVisible($(".o_burger_menu"), "Burger menu should be closed after do_action");

        mobileMenu.destroy();
        testUtils.mock.unpatch(UserMenu);
    });
});
});
