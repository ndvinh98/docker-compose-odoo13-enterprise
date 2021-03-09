odoo.define('mrp_workorder_iot.pedal_form', function(require) {
"use strict";

var PDFViewerNoReload = require('mrp_workorder.PDFViewerNoReload');
var FormController = require('web.FormController');
var view_registry = require('web.view_registry');

var TabletPDFViewer = PDFViewerNoReload.TabletPDFViewer;
var PDFViewerNoReloadRenderer = PDFViewerNoReload.PDFViewerNoReloadRenderer;

var PedalRenderer = PDFViewerNoReloadRenderer.extend({
    events: _.extend({}, PDFViewerNoReloadRenderer.prototype.events, {
        'click .o_pedal_status_button': '_onPedalStatusButtonClicked',
    }),

    init: function () {
        this._super.apply(this, arguments);
        this.pedal_connect = false;
        this.show_pedal_button = false;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    showPedalStatusButton: function (connected) {
        this.pedal_connect = connected;
        this.show_pedal_button = true;
        return this._updatePedalStatusButton(); // maybe only update the button
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _render: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._updatePedalStatusButton();
        });
    },

    _updatePedalStatusButton: function () {
        this.$('.o_pedal_status_button').remove();
        var self = this;
        if (this.show_pedal_button) {
            var button = $('<button>', {
                class: 'btn o_pedal_status_button ' + (self.pedal_connect ? ' btn-primary o_active ' : ' btn-warning'),
                disabled: self.pedal_connect,
            });
            button.html('<i class="fa fa-clipboard"></i>');
            this.$('.o_workorder_actions').append(button);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onPedalStatusButtonClicked: function (ev) {
        ev.preventDefault();
        this.trigger_up('pedal_status_button_clicked');
    },
});


var PedalController = FormController.extend({
    custom_events: _.extend({}, FormController.prototype.custom_events, {
        'pedal_status_button_clicked': '_onTakeOwnership',
    }),

    /**
    * When it starts, it needs to check if the tab owns or can take ownership of the devices
    * already.  If not, an indicator button will show in orange and you can click on it
    * in order to still take ownership.
    **/
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.renderer.showPedalStatusButton(false);
            var state = self.model.get(self.handle);
            self.triggers = JSON.parse(state.data.boxes);
            var boxes = self.triggers;
            for (var box in boxes) {
                var devices = [];
                for (var device in boxes[box]) {
                    devices.push(boxes[box][device][0]);
                }
                self.call('iot_longpolling', 'addListener', box, devices, self._onValueChange.bind(self));
            }
            self.takeOwnerships();
        });
    },

    /**
     * When the foot switch change state this function check if this session_id are the owner of the foot switch
     * and perform the right action by comparing the value received with the letter associated with an action
     *
     * @param {Object} data.owner
     * @param {Object} data.session_id
     * @param {Object} data.device_id
     * @param {Object} data.value
     */
    _onValueChange: function (data){
        var boxes = this.triggers;
        if (data.owner && data.owner !== data.session_id) {
            this.renderer.showPedalStatusButton(false);
        } else {
            for (var box in boxes) {
                for (var device in boxes[box]) {
                    if ( data.device_id === boxes[box][device][0] && data.value.toUpperCase() === boxes[box][device][1].toUpperCase()){
                        this.$("button[barcode_trigger='" + boxes[box][device][2] + "']:visible").click();
                    }
                }
            }
        }
    },

    /*
    * This function tells the IoT Box that this browser tab will take control
    * over the devices of this workcenter.  When done, a timer is started to
    * check if a pedal was pressed every half second, which will handle further actions.
    */
    takeOwnerships: function() {
        this.renderer.showPedalStatusButton(true);
        var boxes = this.triggers;
        for (var box in boxes) {
            for (var device in boxes[box]) {
                this.call(
                    'iot_longpolling',
                    'action',
                    box,
                    boxes[box][device][0],
                    '',
                    '',
                    ''
                );
            }
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onTakeOwnership: function (ev) {
        ev.stopPropagation();
        this.takeOwnerships();
    },
});

var PedalForm = TabletPDFViewer.extend({
    config: _.extend({}, TabletPDFViewer.prototype.config, {
        Controller: PedalController,
        Renderer: PedalRenderer,
    }),
});

view_registry.add('pedal_form', PedalForm);

return {
    PedalRenderer: PedalRenderer,
    PedalController: PedalController,
    PedalForm: PedalForm,
};
});