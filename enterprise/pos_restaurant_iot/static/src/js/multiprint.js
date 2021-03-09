odoo.define('pos_restaurant_iot.multiprint', function (require) {
"use strict";

var models = require('point_of_sale.models');
var PrinterProxy = require('pos_iot.Printer');

// The override of create_printer needs to happen after its declaration in
// pos_restaurant. We need to make sure that this code is executed after the
// multiprint file in pos_restaurant.
require('pos_restaurant.multiprint');

models.load_fields("restaurant.printer", 'device_identifier');

var _super_posmodel = models.PosModel.prototype;

models.PosModel = models.PosModel.extend({
    create_printer: function (config) {
        if (config.device_identifier && config.printer_type === "iot"){
            return new PrinterProxy({ iot_ip: config.proxy_ip, identifier: config.device_identifier }, this);
        }
        else {
            return _super_posmodel.create_printer.apply(this, arguments);
        }
    },
});
});
