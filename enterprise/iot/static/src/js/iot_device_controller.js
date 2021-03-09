odoo.define('iot.IoTDeviceFormController', function (require) {
"use strict";

var core = require('web.core');
var FormController = require('web.FormController');
var DeviceProxy = require('iot.widgets').DeviceProxy;

var _t = core._t;

var IotDeviceFormController = FormController.extend({
    /**
     * @override
     */
    saveRecord: function () {
        var self = this;
        var _super = this._super.bind(this);
        if (['keyboard', 'scanner'].indexOf(this.renderer.state.data.type) >= 0) {
            return this._updateKeyboardLayout().then(self._processResult.bind(self, _super));
        } else if (this.renderer.state.data.type === 'display') {
            return this._updateScreenUrl().then(() => _super());
        } else {
            return this._super.apply(this, arguments);
        }
    },
    /**
     * 
     */
    _processResult: function (saveRecord, data) {
        if (data.result === true) {
            saveRecord();
        } else {
            this.do_warn(_t('Connection to Device failed'), _t('Please check if the device is still connected.'));
        }
    },
    /**
     * Send an action to the device to update the keyboard layout
     */
    _updateKeyboardLayout: function () {
        var keyboard_layout = this.renderer.state.data.keyboard_layout;
        var iot_device = new DeviceProxy({ iot_ip: this.renderer.state.data.iot_ip, identifier: this.renderer.state.data.identifier });
        if (keyboard_layout) {
            return this._rpc({
                model: 'iot.keyboard.layout',
                method: 'read',
                args: [[keyboard_layout.res_id], ['layout', 'variant']],
            }).then(function (res) {
                return iot_device.action({'action': 'update_layout', 'layout': res[0].layout, 'variant': res[0].variant});
            });
        } else {
            return iot_device.action({'action': 'update_layout'});
        }
    },
    /**
     * Send an action to the device to update the screen url
     */
    _updateScreenUrl: function () {
        var screen_url = this.renderer.state.data.screen_url;
        var iot_device = new DeviceProxy({ iot_ip: this.renderer.state.data.iot_ip, identifier: this.renderer.state.data.identifier });
        return iot_device.action({'action': 'update_url', 'url': screen_url});
    },
});

return IotDeviceFormController;

});
