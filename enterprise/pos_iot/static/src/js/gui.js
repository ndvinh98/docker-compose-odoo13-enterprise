odoo.define('pos_iot.gui', function (require) {
"use strict";

var gui = require('point_of_sale.gui');

gui.Gui.include({
    /**
     * Closes the shift of the payment terminal then closes the POS session
     * 
     * @override
     */
    close: function () {
        var self = this;
        if (this.pos.useIoTPaymentTerminal()) {
            var close_promises = [];
            this.pos.payment_methods.forEach(function(payment_method) {
                if (payment_method.terminal_proxy) {
                    close_promises.push(payment_method.terminal_proxy.action({ messageType: 'CloseShift' }));
                };
            });
            Promise.all(close_promises).finally(self._super.bind(self));
        } else {
            this._super();
        };
    },
});
});
