odoo.define('pos_iot.Printer', function (require) {
"use strict";

var PrinterMixin = require('point_of_sale.Printer').PrinterMixin;
var DeviceProxy = require('iot.widgets').DeviceProxy;

var PrinterProxy = DeviceProxy.extend(PrinterMixin, {
    init: function (device, pos) {
        PrinterMixin.init.call(this, arguments);
        this.pos = pos;
        this._super(device);
    },
    open_cashbox: function () {
        var self = this;
        return this.action({ action: 'cashbox' })
            .then(self._onIoTActionResult.bind(self))
            .guardedCatch(self._onIoTActionFail.bind(self));
    },
    send_printing_job: function (img) {
        return this.action({
            action: 'print_receipt',
            receipt: img,
        });

    },
});

return PrinterProxy;

});
