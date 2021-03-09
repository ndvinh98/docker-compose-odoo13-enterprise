odoo.define('pos_iot.customer_display', function (require) {
"use strict";

var DebugWidget = require('point_of_sale.chrome').DebugWidget;
var ClientScreenWidget = require('point_of_sale.chrome').ClientScreenWidget;
var ProxyDevice = require('point_of_sale.devices').ProxyDevice;

DebugWidget.include({
    start: function () {
        var self = this;
        this._super();
        this.$('.button.display_refresh').unbind('click').click(function (ev) {
            ev.preventDefault();
            if (self.pos.iot_device_proxies.display) {
                self.pos.iot_device_proxies.display.action({ action: 'display_refresh' });
            }
        });
    }
});

ClientScreenWidget.include({
    check_owner: function (data) {
        if (data.error) {
            this.change_status_display('not_found');
        } else if (data.owner === this.pos.iot_device_proxies.display._iot_longpolling._session_id) {
            this.change_status_display('success');
        } else {
            this.change_status_display('warning');
        }
    },

    start: function(){
        var self = this;
        if (this.pos.proxy.posbox_supports_display && this.pos.iot_device_proxies.display) {
                this.show();
                this.pos.iot_device_proxies.display.add_listener(self.check_owner.bind(self));
                // The listener starts after 1.5s so wait before getting the owner of the display
                setTimeout(function () {
                    self.pos.iot_device_proxies.display.action({action: 'get_owner'});
                }, 1500);
                this.$el.click(function(){
                    self.pos.render_html_for_customer_facing_display().then(function(rendered_html) {
                        self.pos.proxy.take_ownership_over_client_screen(rendered_html);
                    });
                });
        } else {
            this.hide();
        }
    },
});

ProxyDevice.include({
    update_customer_facing_display: function(html) {
        if (this.pos.iot_device_proxies.display) {
            return this.pos.iot_device_proxies.display.action({
                action: 'customer_facing_display',
                html: html,
            });
        }
    },

    take_ownership_over_client_screen: function(html) {
        return this.pos.iot_device_proxies.display.action({
            action: "take_control",
            html: html,
        });
    },
});
});
