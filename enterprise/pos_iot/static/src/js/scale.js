odoo.define('pos_iot.screens', function (require) {
    "use strict";

var core = require('web.core');
var screens = require('point_of_sale.screens');

var _t = core._t;

screens.ScaleScreenWidget.include({

    /**
     * @override
     * @private
     */
    show: function () {
        var self = this;
        this.scale = this.pos.iot_device_proxies.scale;
        if (this.scale === undefined) {
            this.gui.show_popup('error', {
                'title': _t('No Scale Detected'),
                'body': _t('It seems that no scale was detected.\nMake sure that the scale is connected and visible in the IoT app.')
            });
        }
        this._error = false;
        this.pos.proxy.on('change:status', this, function (eh, status) {
            if (!self.iot_box.connected || !status.newValue.drivers.scale || status.newValue.drivers.scale.status !== 'connected') {
                if (!self._error) {
                    self._error = true;
                    self.gui.show_popup('error', {
                        'title': _t('Could not connect to IoT scale'),
                        'body': _t('The IoT scale is not responding. You should check your connection.')
                    });
                }
            } else { self._error = false; }
        });
        this.iot_box = _.find(this.pos.proxy.iot_boxes, function (iot_box) {
            return iot_box.ip == self.scale._iot_ip;
        });
        this.manual_reading = this.scale.manufacturer === 'Adam';
        this._super();
        if (this.manual_reading) {
            this.$('.read-weight').click(function(){
                self.pos.proxy_queue.schedule(function () { self.scale.action({ action: 'read_once' }); });
            });
        } else {
            this.pos.proxy_queue.schedule(function () { self.scale.action({ action: 'start_reading' }); });
        }
    },

    /**
     * @override
     * @private
     */
    _read_scale: function () {
        var self = this;
        self.pos.proxy_queue.schedule(function () {
            self.scale.add_listener(self._on_value_change.bind(self))
                .then(function () { self.scale.action({ action: 'read_once' }); });
        });
    },

    /**
     * @override
     * @private
     */
    _on_value_change: function (data) {
        if (data.status.status === 'error') {
            this.gui.show_popup('error-traceback', {
                'title': data.status.message_title,
                'body': data.status.message_body,
            });
        } else {
            this.set_weight(data.value);
        }
    },

    /**
     * @override
     */
    close: function () {
        var self = this;
        this._super();
        this.pos.proxy_queue.schedule(function () { self.scale.action({ action: 'stop_reading' }); });
        if (this.scale) this.scale.remove_listener();
    }
});
});
