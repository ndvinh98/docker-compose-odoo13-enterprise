odoo.define('pos_iot.payment', function (require) {
"use strict";

var core = require('web.core');
var PaymentInterface = require('point_of_sale.PaymentInterface');

var _t = core._t;

var PaymentIOT = PaymentInterface.extend({
    send_payment_request: function (cid) {
        var self = this;
        this._super.apply(this, this.arguments);
        var paymentline = this.pos.get_order().get_paymentline(cid)
        var terminal_proxy = paymentline.payment_method.terminal_proxy
        if (!terminal_proxy) {
            this._showErrorConfig();
            return Promise.resolve(false);
        }

        this.terminal = terminal_proxy;

        var data = {
            messageType: 'Transaction',
            TransactionID: parseInt(this.pos.get_order().uid.replace(/-/g, '')),
            cid: cid,
            amount: Math.round(paymentline.amount*100),
            currency: this.pos.currency.name,
            language: this.pos.user.lang.split('_')[0],
        };
        return new Promise(function (resolve) {
            self._waitingResponse = self._waitingPayment;
            self.terminal.add_listener(self._onValueChange.bind(self, resolve, self.pos.get_order()));
            self._send_request(data);
            self._query_terminal();
        });
    },
    send_payment_cancel: function (order, cid) {
        var self = this;
        if (this.terminal) {
            this._super.apply(this, this.arguments);
            var data = {
                messageType: 'Cancel',
                reason: 'manual'
            };
            return new Promise(function (resolve) {
                self._waitingResponse = self._waitingCancel;
                self.terminal.add_listener(self._onValueChange.bind(self, resolve, order));
                self._send_request(data);
            });
        }
        return Promise.reject();
    },
    send_payment_reversal: function (cid) {
        var self = this;
        this._super.apply(this, this.arguments);
        var data = {
            messageType: 'Reversal',
            TransactionID: parseInt(this.pos.get_order().uid.replace(/-/g, '')),
            cid: cid,
            amount: Math.round(this.pos.get_order().get_paymentline(cid).amount*100),
            currency: this.pos.currency.name,
        };
        return new Promise(function (resolve) {
            self._waitingResponse = self._waitingReverse;
            self.terminal.add_listener(self._onValueChange.bind(self, resolve, self.pos.get_order()));
            self._send_request(data);
        });
        
    },

    // extra private methods
    /**
     * Queries the status of the current payment after 3 seconds if no update
     * has been received. If an update has been received, the time should be
     * reset.
     */
    _query_terminal: function () {
        var self = this;
        this.payment_update = setTimeout(function () {
            self.terminal.action({messageType: 'QueryStatus'});
        }, 3000);
    },
    _send_request: function (data) {
        var self = this;
        this.terminal.action(data)
            .then(self._onActionResult.bind(self))
            .guardedCatch(self._onActionFail.bind(self));
    },
    _onActionResult: function (data) {
        if (data.result === false) {
            this.pos.gui.show_popup('error',{
                'title': _t('Connection to terminal failed'),
                'body':  _t('Please check if the terminal is still connected.'),
            });
            if (this.pos.get_order().selected_paymentline) {
                this.pos.get_order().selected_paymentline.set_payment_status('force_done');
            }
            this.pos.chrome.gui.current_screen.render_paymentlines();
        }
    },
    _onActionFail: function () {
        this.pos.gui.show_popup('error',{
            'title': _t('Connection to IoT Box failed'),
            'body':  _t('Please check if the IoT Box is still connected.'),
        });
        if (this.pos.get_order().selected_paymentline) {
            this.pos.get_order().selected_paymentline.set_payment_status('force_done');
        }
        this.pos.chrome.gui.current_screen.render_paymentlines();
    },
    _showErrorConfig: function () {
        this.pos.gui.show_popup('error',{
            'title': _t('Configuration of payment terminal failed'),
            'body':  _t('You must select a payment terminal in your POS config.'),
        });
    },

    _waitingPayment: function (resolve, data, line) {
        if (data.Error) {
            this.pos.gui.show_popup('error',{
                'title': _t('Payment terminal error'),
                'body':  _t(data.Error),
            });
            this.terminal.remove_listener();
            resolve(false);
        } else if (data.Response === 'Approved') {
            clearTimeout(this.payment_timer);
            if (data.Card) {
                line.card_type = data.Card;
                line.transaction_id = data.PaymentTransactionID;
            }
            if (data.Reversal) {
                this.enable_reversals();
            }
            this.terminal.remove_listener();
            resolve(true);
        } else if (['WaitingForCard', 'WaitingForPin'].includes(data.Stage)) {
            line.set_payment_status('waitingCard');
            this.pos.gui.screen_instances.payment.render_paymentlines();
        }
    },

    _waitingCancel: function (resolve, data) {
        if (['Finished', 'None'].includes(data.Stage)) {
            this.terminal.remove_listener();
            resolve(true);
        } else if (data.Error) {
            this.terminal.remove_listener();
            resolve(true);
        }
    },

    _waitingReverse: function (resolve, data) {
        if (data.Response === 'Reversed') {
            this.terminal.remove_listener();
            resolve(true);
        } else if (data.Error) {
            this.pos.gui.show_popup('error',{
                'title': _t('Payment terminal error'),
                'body':  _t(data.Error),
            });
            this.terminal.remove_listener();
            resolve(false);
        }
    },

    /**
     * Function ran when Device status changes.
     *
     * @param {Object} data.Response
     * @param {Object} data.Stage
     * @param {Object} data.Ticket
     * @param {Object} data.device_id
     * @param {Object} data.owner
     * @param {Object} data.session_id
     * @param {Object} data.value
     */
    _onValueChange: function (resolve, order, data) {
        clearTimeout(this.payment_update);
        var line = order.get_paymentline(data.cid);
        var terminal_proxy = this.pos.payment_methods_by_id[line.payment_method.id].terminal_proxy;
        if (line && terminal_proxy && (!data.owner || data.owner === terminal_proxy._iot_longpolling._session_id)) {
            this._waitingResponse(resolve, data, line);
            if (data.processing) {
                this._query_terminal();
            }
            if (data.Ticket) {
                line.set_receipt_info(data.Ticket.replace(/\n/g, "<br />"));
            }
            if (data.TicketMerchant && this.pos.proxy.printer) {
                this.pos.proxy.printer.print_receipt("<div class='pos-receipt'><div class='pos-payment-terminal-receipt'>" + data.TicketMerchant.replace(/\n/g, "<br />") + "</div></div>");
            }
        }
    },
});
return PaymentIOT;
});
