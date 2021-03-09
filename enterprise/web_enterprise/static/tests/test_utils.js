odoo.define('web_enterprise.test_utils', function (require) {
"use strict";

var Menu = require('web_enterprise.Menu');
var testUtils = require('web.test_utils');
var SystrayMenu = require('web.SystrayMenu');
var UserMenu = require('web.UserMenu');

/**
 * create a menu from given parameters.
 *
 * @param {Object} params This object will be given to addMockEnvironment, so
 *   any parameters from that method applies
 * @param {Object} params.menuData This object will define the menu's data
 *   structure to render
 * @param {Widget[]} [params.systrayMenuItems=[]] This array will define the systray
 *  items to use. Will at least contain and default to UserMenu
 * @returns {Menu}
 */
async function createMenu(params) {
    var parent = testUtils.createParent({});

    var systrayMenuItems = params.systrayMenuItems || [];
    if (params.systrayMenuItems) {
        delete params.systrayMenuItems;
    }

    var initialSystrayMenuItems = _.clone(SystrayMenu.Items);
    SystrayMenu.Items = _.union([UserMenu], systrayMenuItems);

    var menuData = params.menuData || {};
    if (params.menuData) {
        delete params.menuData;
    }

    var menu = new Menu(parent, menuData);
    testUtils.mock.addMockEnvironment(menu, params);
    return menu.appendTo($('#qunit-fixture')).then(function(){
        var menuDestroy = menu.destroy;
        menu.destroy = function () {
            SystrayMenu.Items = initialSystrayMenuItems;
            menuDestroy.call(this);
            parent.destroy();
        };

        return menu;
    });
}

return {
    createMenu: createMenu,
}

});