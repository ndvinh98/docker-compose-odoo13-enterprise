odoo.define('quality_iot.iot_picture', function (require) {
"use strict";

var registry = require('web.field_registry');
var TabletImage = require('quality.tablet_image_field').TabletImage;
var iot_widgets = require('iot.widgets');
var Dialog = require('web.Dialog');
var core = require('web.core');
var _t = core._t;

var TabletImageIot = TabletImage.extend(iot_widgets.IotValueFieldMixin, {
    events: _.extend({}, TabletImage.prototype.events, {
        'click .o_input_file': '_onButtonClick',
    }),

    /**
     * @private
     */
    _getDeviceInfo: function() {
        var record_data = this.record.data;
        if (record_data.test_type === 'picture' && record_data.identifier) {
            this.iot_device = new iot_widgets.DeviceProxy({ iot_ip: record_data.ip, identifier: record_data.identifier });
        }
        return Promise.resolve();
    },

    _onButtonClick: function (ev) {
        var self = this;
        ev.stopImmediatePropagation();
        if (this.iot_device) {
            ev.preventDefault();
            this.do_notify(_t('Capture image...'));
            this.iot_device.action('')
                .then(function(data) {
                    self._onIoTActionResult(data);
                })
                .guardedCatch(self._onIoTActionFail);
        }
    },
    /**
     * When the camera change state (after a action that call to take a picture) this function render the picture to the right owner
     *
     * @param {Object} data.owner
     * @param {Object} data.session_id
     * @param {Object} data.message
     * @param {Object} data.image in base64
     */
    _onValueChange: function (data){
        if (data.owner && data.owner === data.session_id) {
            this.do_notify(data.message);
            if (data.image){
                this._setValue(data.image);
            }
        }
    },
});

registry.add('iot_picture', TabletImageIot);

return TabletImageIot;
});
