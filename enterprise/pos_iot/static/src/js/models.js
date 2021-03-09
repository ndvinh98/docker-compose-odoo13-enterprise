odoo.define('pos_iot.models', function (require) {
"use strict";

var models = require('point_of_sale.models');
var PaymentIOT = require('pos_iot.payment');
var DeviceProxy = require('iot.widgets').DeviceProxy;
var PrinterProxy = require('pos_iot.Printer');

models.load_fields("res.users", "lang");
models.load_fields("pos.payment.method", "iot_device_id");
models.register_payment_method('six', PaymentIOT);
models.register_payment_method('ingenico', PaymentIOT);

models.load_models([{
    model: 'iot.device',
    fields: ['iot_ip', 'iot_id', 'identifier', 'type', 'manufacturer'],
    domain: function(self) {
        var device_ids = self.config.iot_device_ids;
        _.each(self.payment_methods, function (payment_method) {
            if (payment_method.iot_device_id) {
                device_ids.push(payment_method.iot_device_id[0]);
            }
        });
        return [['id', 'in', device_ids]];
    },
    loaded: function(self, iot_devices) {
        if (_.size(iot_devices)) {
            self.config.use_proxy = true;
        }
        self.iot_device_proxies = {};
        self.proxy.iot_boxes = [];
        _.each(iot_devices, function(iot_device) {
            if (!self.proxy.iot_boxes.includes(iot_device.iot_id[0])) {
                self.proxy.iot_boxes.push(iot_device.iot_id[0]);
            }
            switch (iot_device.type) {
                case 'scale':
                case 'fiscal_data_module':
                case 'display':
                    self.iot_device_proxies[iot_device.type] = new DeviceProxy({ iot_ip: iot_device.iot_ip, identifier: iot_device.identifier, manufacturer: iot_device.manufacturer });
                    break;
                case 'printer':
                    self.iot_device_proxies[iot_device.type] = new PrinterProxy({ iot_ip: iot_device.iot_ip, identifier: iot_device.identifier, manufacturer: iot_device.manufacturer });
                    break;
                case 'scanner':
                    if (!self.iot_device_proxies.scanners){
                        self.iot_device_proxies.scanners = {};
                    }
                    self.iot_device_proxies.scanners[iot_device.identifier] = new DeviceProxy({ iot_ip: iot_device.iot_ip, identifier: iot_device.identifier, manufacturer: iot_device.manufacturer });
                    break;
                case 'payment':
                    var payment_method = _.find(self.payment_methods, function (payment_method) {
                        return payment_method.iot_device_id[0] == iot_device.id;
                    });
                    payment_method.terminal_proxy = new DeviceProxy({ iot_ip: iot_device.iot_ip, identifier: iot_device.identifier, manufacturer: iot_device.manufacturer });
                    break;
            }
        });
    },
}, {
    model: 'iot.box',
    fields: ['ip', 'ip_url', 'name'],
    domain: function (self) {
        return [['id', 'in', self.proxy.iot_boxes]];
    },
    loaded: function(self, iot_boxes) {
        self.proxy.iot_boxes = iot_boxes;
    }
}]);

var posmodel_super = models.PosModel.prototype;
models.PosModel = models.PosModel.extend({
    /**
     * Opens the shift on the payment terminal
     *
     * @override
     */
    after_load_server_data: function () {
        var self = this;
        var res = posmodel_super.after_load_server_data.apply(this, arguments);
        if (this.useIoTPaymentTerminal()) {
            res.then(function () {
                self.payment_methods.forEach(function (payment_method) {
                    if (payment_method.terminal_proxy) {
                        payment_method.terminal_proxy.action({
                            messageType: 'OpenShift',
                            language: self.user.lang.split('_')[0],
                        });
                    }
                });
            });
        }
        return res;
    },

    useIoTPaymentTerminal: function () {
        return this.config && this.config.use_proxy
            && this.payment_methods.some(function(payment_method) {
                return payment_method.terminal_proxy;
            });
    },

    connect_to_proxy: function () {
        this.proxy.ping_boxes();
        if (this.config.iface_scan_via_proxy) {
            this.barcode_reader.connect_to_proxy();
        }
        if (this.config.iface_print_via_proxy) {
            this.proxy.connect_to_printer();
        }
        if (!this.proxy.status_loop_running) {
            this.proxy.status_loop();
        }
        return Promise.resolve();
    },
});

});
