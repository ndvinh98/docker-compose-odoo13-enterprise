odoo.define('posiot.scale.tour', function (require) {
    'use strict';

var Tour = require('web_tour.tour');
var DeviceProxy = require('iot.widgets').DeviceProxy;

var PosScaleDummy = DeviceProxy.extend({
    action: function () { },
    remove_listener: function () { },
    add_listener: function (callback) {
        setTimeout(callback({
            status: 'ok',
            value: 2.35
        }), 1000);
        return Promise.resolve();
    }
});

Tour.register('pos_iot_scale_tour', {
    url: '/web',
    test: true
    }, [Tour.STEPS.SHOW_APPS_MENU_ITEM,
    {
        trigger: '.o_app[data-menu-xmlid="point_of_sale.menu_point_root"]',
    }, {
        trigger: ".o_pos_kanban button.oe_kanban_action_button",
    }, { // Leave category displayed by default
        trigger: ".js-category-switch",
    }, {
        trigger: 'body:has(.loader:hidden)',
        run: function () {
            posmodel.iot_device_proxies.scale = new PosScaleDummy({ iot_ip: '', identifier: '' });
        }
    }, {
        trigger: '.product:contains("Whiteboard Pen")',
    }, {
        trigger: '.js-weight:contains("2.35")',
    }, {
        trigger: '.buy-product',
    }, {
        trigger: ".header-button",
    }, {
        trigger: ".header-button",
        run: function () { }, //it's a check,
    }]);
});
