odoo.define('pos_iot.BarcodeReader', function (require) {
"use strict";

var BarcodeReader = require('point_of_sale.BarcodeReader');

BarcodeReader.include({
    connect_to_proxy: function () {
        var self = this;
        this.scanners = this.pos.iot_device_proxies.scanners;
        for (var identifier in this.scanners) {
            this.scanners[identifier].add_listener(function (barcode) {
                self.scan(barcode.value);
            });
        }
    },

    // the barcode scanner will stop listening on the hw_proxy/scanner remote interface
    disconnect_from_proxy: function () {
        if (this.scanners) {
            for (var identifier in this.scanners) {
                this.scanners[identifier].remove_listener();
            }
        }
    },
});

});
