odoo.define('pos_iot.test.payment_terminals', function (require) {
'use strict';

var tour = require('web_tour.tour');

var DeviceProxy = require('iot.widgets').DeviceProxy;

var TerminalProxy = DeviceProxy.extend({
    /**
     * @override
     */
    action: function (data) {
        var self = this;
        switch(data.messageType) {
            case 'Transaction':
                if (!this.transaction) {
                    this.transaction = true;
                    this.cid = data.cid;
                    setTimeout(function () {
                        self.listener({
                            Stage: 'WaitingForCard',
                            cid: self.cid,
                        });
                    });
                    this.timer = setTimeout(function () {
                        self.listener({
                            Response: 'Approved',
                            Reversal: true,
                            cid: self.cid,
                        });
                    }, 1000);
                } else {
                    throw "Another transaction is still running";
                }
                break;
            case 'Cancel':
                clearTimeout(this.timer);
                this.transaction = false;
                setTimeout(function () {
                    self.listener({
                        Error: 'Canceled',
                        cid: self.cid,
                    });
                });
                break;
            case 'Reversal':
                this.transaction = false;
                setTimeout(function () {
                    self.listener({
                        Response: 'Reversed',
                        cid: data.cid,
                    });
                });
                break;
        }
        return Promise.resolve({
            result: true
        });
    },
    /**
     * @override
     */
    add_listener: function(callback) {
        this.listener = callback;
    },
    /**
     * @override
     */
    remove_listener: function() {
        this.listener = false;
    },
});

tour.register('payment_terminals_tour', {
    test: true,
    url: '/web',
}, [tour.STEPS.SHOW_APPS_MENU_ITEM,
    {
        content: 'Select PoS app',
        trigger: '.o_app[data-menu-xmlid="point_of_sale.menu_point_root"]',
    }, {
        content: 'Start session',
        trigger: ".o_pos_kanban button.oe_kanban_action_button",
    }, {
        content: 'Waiting for loading to finish',
        trigger: 'body:has(.loader:hidden)',
        run: function () {
            //Overrides the methods inside DeviceProxy to mock the IoT Box
            posmodel.payment_methods.forEach(function(payment_method) {
                if (payment_method.terminal_proxy) {
                    payment_method.terminal_proxy = new TerminalProxy({iot_ip: payment_method.terminal_proxy._iot_ip, identifier: payment_method.terminal_proxy._identifier});
                }
            });
        },
    }, { // Leave category displayed by default
        content: "Click category switch",
        trigger: ".js-category-switch",
    }, {
        content: 'Buy a Desk Organizer',
        trigger: '.product-list .product-name:contains("Desk Organizer")',
    }, {
        content: 'The Desk Organizer has been added to the order',
        trigger: '.order .product-name:contains("Desk Organizer")',
        run: function () {}, // it's a check
    }, {
        content: "Go to payment screen",
        trigger: '.button.pay',
    }, {
        content: "Pay with payment terminal",
        trigger: '.paymentmethod:contains("Terminal")',
    }, {
        content: "Remove payment line",
        trigger: '.delete-button',
    }, {
        content: "Pay with payment terminal",
        trigger: '.paymentmethod:contains("Terminal")',
    }, {
        content: "Send payment to terminal",
        trigger: '.button.send_payment_request.highlight',
    }, {
        content: "Cancel payment",
        trigger: '.button.send_payment_cancel',
    }, {
        content: "Retry to send payment to terminal",
        trigger: '.button.send_payment_request.highlight',
    }, {
        content: "Check that the payment is confirmed",
        trigger: '.button.next.highlight',
        run: function () {}, // it's a check
    }, {
        content: "Reverse payment",
        trigger: '.button.send_payment_reversal',
    }, {
        content: "Check that the payment is reversed",
        trigger: '.button.next:not(.highlight)',
        run: function () {}, // it's a check
    }, {
        content: "Pay with payment terminal",
        trigger: '.paymentmethod:contains("Terminal")',
    }, {
        content: "Send payment to terminal",
        trigger: '.button.send_payment_request.highlight',
    }, {
        content: "Validate payment",
        trigger: '.button.next.highlight:contains("Validate")',
    }, {
        content: "Check that we're on the receipt screen",
        trigger: '.button.next.highlight:contains("Next Order")',
        run: function() {}
    }]);
});
