odoo.define('iot.IoTDeviceFormView', function (require) {
"use strict";

var IoTDeviceFormController = require('iot.IoTDeviceFormController');
var FormView = require('web.FormView');
var viewRegistry = require('web.view_registry');

var IoTDeviceFormView = FormView.extend({
    config: _.extend({}, FormView.prototype.config, {
        Controller: IoTDeviceFormController,
    }),
});

viewRegistry.add('iot_device_form', IoTDeviceFormView);

return IoTDeviceFormView;

});
