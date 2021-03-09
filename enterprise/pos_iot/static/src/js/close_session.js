odoo.define('pos_iot.CloseSession', function (require) {
"use static";

var core = require('web.core');
var rpc = require('web.rpc');
var widgetRegistry = require('web.widget_registry');
var Widget = require('web.Widget');
var DeviceProxy = require('iot.widgets').DeviceProxy;
var PrinterProxy = require('pos_iot.Printer');
var AbstractAction = require('web.AbstractAction');

var _t = core._t;

var CloseSession = AbstractAction.extend({
    template: 'CloseSession',
    events: {
        'click': '_onClickCloseSession',
    },

    /**
     * @override
     */
    init: function (parent, record, options) {
        var res = this._super.apply(this, arguments);
        this.attrs = options.attrs;
        this.data = record.data;
        this.loaded = this.load(this.data.config_id.res_id)
        return res;
    },

    load: function (config_id) {
        var self = this;
        return rpc.query({
            model: 'pos.config',
            method: 'read',
            args: [[config_id], ['payment_terminal_device_ids', 'iface_printer_id']]
        }).then(function (config) {
            var device_ids = config[0].payment_terminal_device_ids;
            if (device_ids) {
                device_ids.push(config[0].iface_printer_id && config[0].iface_printer_id[0]);
                rpc.query({
                    model: 'iot.device',
                    method: 'search_read',
                    args: [
                        [['id', 'in', device_ids]],
                        ['id', 'type', 'identifier', 'iot_ip', 'manufacturer'],
                    ],
                }).then(function (devices) {
                    self.terminals = [];
                    devices.forEach(function (device) {
                        if (config[0].iface_printer_id && device.id === config[0].iface_printer_id[0]) {
                            self.printer = new PrinterProxy({
                                iot_ip: device.iot_ip,
                                identifier: device.identifier,
                            });
                        } else if (device.type === "payment" && device.manufacturer == "Six") {
                            self.terminals.push(new DeviceProxy({
                                iot_ip: device.iot_ip,
                                identifier: device.identifier,
                            }));
                        }
                    });
                });
            }
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Calls the method specified in this.action on the current pos.session
     */
    _performAction: function () {
        var self = this;
        return this._rpc({
            model: 'pos.session',
            method: this.attrs.action,
            args: [this.data.id],
        }).then(function (action) {
            if(action){
                self.do_action(action);
            } else {
                self.trigger_up('reload');
            }
        });

    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Sends a Balance operation to the terminal if needed then performs the
     * closing action.
     */
    _onClickCloseSession: function () {
        var self = this;
        this.loaded.then(function () {
            var balance_promises = [];
            if (self.terminals) {
                self.terminals.forEach(function (terminal) {
                    balance_promises.push(
                        new Promise(function (resolve) {
                            terminal.add_listener(self._onValueChange.bind(self, terminal, resolve));
                            terminal.action({ messageType: 'Balance' })
                                .then(self._onTerminalActionResult.bind(self, terminal));
                        })
                    );
                });
                Promise.all(balance_promises).then(self._performAction.bind(self));
            } else {
                self._performAction();
            }
        });
    },

    /**
     * Processes the return value of an action sent to the terminal
     *
     * @param {Object} data
     * @param {boolean} data.result
     */
    _onTerminalActionResult: function (terminal, data) {
        if (data.result === false) {
            this.do_warn(_t('Connection to terminal failed'), _t('Please check if the terminal is still connected.'));
            terminal.remove_listener();
        }
    },

    /**
     * Listens for changes from the payment terminal, prints receipts destined
     * to the merchant then performs the closing action.
     *
     * @param {Object} data
     * @param {String} data.Error
     * @param {String} data.TicketMerchant
     */
    _onValueChange: function (terminal, resolve, data) {
        if (data.Error) {
            this.do_warn(_t('Error performing balance'), data.Error);
            return;
        } else if (data.TicketMerchant && this.printer) {
            $('.pos-receipts').addClass('pos-receipt-print');
            this.printer.print_receipt("<div class='pos-receipt'><div class='pos-payment-terminal-receipt'>" + data.TicketMerchant.replace(/\n/g, "<br />") + "</div></div>");
        }
        terminal.remove_listener();
        resolve(true);
    },
});

widgetRegistry.add('close_session', CloseSession);

});
