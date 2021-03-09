odoo.define('pos_iot.devices', function (require) {
"use strict";

var rpc = require('web.rpc');
var ProxyDevice = require('point_of_sale.devices').ProxyDevice;

ProxyDevice.include({
    /**
     * @override
     */
    connect_to_printer: function () {
        this.pos.iot_device_proxies.printer.pos = this.pos;
        this.printer = this.pos.iot_device_proxies.printer;
    },
    /**
     * Ping all of the IoT Boxes of the devices set on POS config and update the
     * status icon
     */
    ping_boxes: function () {
        var self = this;
        this.set_connection_status("connecting");
        _.each(this.iot_boxes, function (iot_box) {
            $.ajax({
                url: iot_box.ip_url + '/hw_proxy/hello',
                method: 'GET',
                timeout: 1000,
            }).then(function () {
                self.proxy_connection_status(iot_box.ip, true);
            }).catch(function () {
                self.proxy_connection_status(iot_box.ip, false);
            });
        });
    },
    /**
     * Set the status of the IoT Box that has the specified url and update the
     * status icon
     * 
     * @param {String} url
     * @param {Boolean} connected
     */
    proxy_connection_status: function (url, connected) {
        var iot_box = _.find(this.iot_boxes, function (iot_box) {
            return iot_box.ip == url;
        });
        if (iot_box) {
            iot_box.connected = connected;
            this.update_status_icon();
        }
    },
    /**
     * Check the status of the devices every 5 seconds and update the status
     * icon accordingly. This status is valid only if the IoT Box is connected.
     */
    status_loop: function () {
        var self = this;
        this.status_loop_running = true;
        rpc.query({
            model: 'iot.device',
            method: 'search_read',
            fields: ['type'],
            domain: [['id', 'in', this.pos.config.iot_device_ids], ['connected', '=', true]],
        }).then(function (iot_devices) {
            var drivers_status = {};
            _.each(iot_devices, function(iot_device) {
                drivers_status[iot_device.type] = {status: "connected"};
            });
            var old_status = self.get('status');
            self.set_connection_status(old_status.status, drivers_status, old_status.msg);
            setTimeout(function () {
                self.status_loop();
            }, 5000);
        });
    },
    /**
     * Update the status icon of the proxy depending on the connection of the
     * IoT Boxes
     */
    update_status_icon: function () {
        var disconnected_proxies = _.filter(this.iot_boxes, function (iot_box) {
            return !iot_box.connected;
        });
        if (disconnected_proxies.length) {
            var disconnected_proxies_string = disconnected_proxies.map((proxy) => proxy.name).join(" & ");
            this.set_connection_status("disconnected", false, disconnected_proxies_string + " disconnected");
        } else {
            this.set_connection_status("connected");
        }
    }
});

});
