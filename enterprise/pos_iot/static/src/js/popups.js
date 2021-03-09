odoo.define('pos_iot.popups', function (require) {
"use strict";

var PopupWidget = require('point_of_sale.popups');
var gui = require('point_of_sale.gui');

var IoTErrorPopupWidget = PopupWidget.extend({
    template: 'IoTErrorPopupWidget',
    show: function (options) {
        this._super(options);
        this.gui.play_sound('error');
    },
});

gui.define_popup({ name: 'iot_error', widget: IoTErrorPopupWidget });
});
