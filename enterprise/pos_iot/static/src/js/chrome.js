odoo.define('pos_iot.chrome', function (require) {
"use strict";

var chrome = require('point_of_sale.chrome');
var core = require('web.core');

var _t = core._t;

chrome.Chrome.include({
    balance_button_widget: {
        'name': 'balance_button',
        'widget': chrome.HeaderButtonWidget,
        'append': '.pos-rightheader',
        'args': {
            label: _t('Send Balance'),
            action: function () {
                this.chrome._sendBalance();
            }
        }
    },

    /**
     * Instanciates the Balance button
     * 
     * @override
     */
    build_widgets: function () {
        if (this.pos.useIoTPaymentTerminal() && 
                this.pos.payment_methods.some((payment_method) => payment_method.use_payment_terminal === "six")) {
            // Place it left to the Close button
            var close_button_index = _.findIndex(this.widgets, function (widget) {
                return widget.name === "close_button";
            });
            this.widgets.splice(close_button_index, 0, this.balance_button_widget);
        }
        this._super();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Sends an action to the terminal to perform a Balance operation
     *
     * @private
     */
    _sendBalance: function () {
        var self = this;
        this.pos.payment_methods.forEach(function(payment_method) {
            if (payment_method.use_payment_terminal == 'six' && payment_method.terminal_proxy) {
                payment_method.terminal_proxy.add_listener(self._onValueChange.bind(self, payment_method.terminal_proxy));
                payment_method.terminal_proxy.action({ messageType: 'Balance' })
                    .then(self._onTerminalActionResult.bind(self));
            };
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Processes the return value of an action sent to the terminal
     *
     * @param {Object} data 
     * @param {boolean} data.result
     */
    _onTerminalActionResult: function (data) {
        if (data.result === false) {
            this.pos.gui.show_popup('error', {
                'title': _t('Connection to terminal failed'),
                'body':  _t('Please check if the terminal is still connected.'),
            });
        }
    },

    /**
     * Listens for changes from the payment terminal and prints receipts
     * destined to the merchant.
     *
     * @param {Object} data
     * @param {String} data.Error
     * @param {String} data.TicketMerchant
     */
    _onValueChange: function (terminal_proxy, data) {
        if (data.Error) {
            this.pos.gui.show_popup('error', {
                'title': _t('Terminal Error'),
                'body': data.Error,
            });
        } else if (data.TicketMerchant && this.pos.proxy.printer) {
            this.pos.proxy.printer.print_receipt("<div class='pos-receipt'><div class='pos-payment-terminal-receipt'>" + data.TicketMerchant.replace(/\n/g, "<br />") + "</div></div>");
        }
        terminal_proxy.remove_listener();
    },
});

});
