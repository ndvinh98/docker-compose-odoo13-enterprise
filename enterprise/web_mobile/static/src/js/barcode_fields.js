odoo.define('web_mobile.barcode_fields', function (require) {
"use strict";

var field_registry = require('web.field_registry');
require('web._field_registry');
var relational_fields = require('web.relational_fields');

var mobile = require('web_mobile.rpc');

/**
 * Override the Many2One to open a dialog in mobile.
 */
var FieldMany2OneBarcode = relational_fields.FieldMany2One.extend({
    template: "FieldMany2OneBarcode",
    events: _.extend({}, relational_fields.FieldMany2One.prototype.events, {
        'click .o_barcode_mobile': '_onBarcodeButtonClick',
    }),

    /**
     * @override
     */
    start: function () {
        var result = this._super.apply(this, arguments);
        this._startBarcode();
        return result;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * External button is visible
     *
     * @return {boolean}
     * @private
     */
    _isExternalButtonVisible: function () {
        return this.$external_button.is(':visible');
    },
    /**
     * @override
     * @private
     */
    _renderEdit: function () {
        this._super.apply(this, arguments);
        // Hide button if a record is set or external button is visible
        if (this.$barcode_button) {
            this.$barcode_button.toggle(!this._isExternalButtonVisible());
        }
    },
    /**
     * Initialisation of barcode button
     *
     * @private
     */
    _startBarcode: function () {
        this.$barcode_button = this.$('.o_barcode_mobile');
        // Hide button if a record is set
        this.$barcode_button.toggle(!this.isSet());
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * On click on button
     *
     * @private
     */
    _onBarcodeButtonClick: function () {
        var self = this;
        mobile.methods.scanBarcode().then(function (response){
            var barcode = response.data;
            if (barcode) {
                self._onBarcodeScanned(barcode);
                mobile.methods.vibrate({
                    duration: 100,
                });
            } else {
                mobile.methods.showToast({
                    message: 'Please, scan again !!',
                });
            }
        });
    },
    /**
     * When barcode is scanned
     *
     * @param barcode
     * @private
     */
    _onBarcodeScanned: function (barcode) {
        this._search(barcode);
    },
});

if (mobile.methods.scanBarcode) {
    field_registry.add('many2one_barcode', FieldMany2OneBarcode);
}

return FieldMany2OneBarcode;
});
