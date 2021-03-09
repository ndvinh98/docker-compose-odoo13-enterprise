odoo.define('web_mobile.datepicker', function (require) {
"use strict";

var mobile = require('web_mobile.rpc');

if (!mobile.methods.requestDateTimePicker) {
    return;
}

var web_datepicker = require('web.datepicker');
var Widget = require('web.Widget');

/**
 * Override odoo date-picker (bootstrap date-picker) to display mobile native
 * date picker. Because of it is better to show native mobile date-picker to
 * improve usability of Application (Due to Mobile users are used to native
 * date picker).
 */

web_datepicker.DateWidget.include({
    /**
     * @override
     */
    start: function () {
        this.$input = this.$('input.o_datepicker_input');
        this._setupMobilePicker();
    },

    /**
     * Bootstrap date-picker already destroyed at initialization
     *
     * @override
     */
    destroy: Widget.prototype.destroy,

    /**
     * @override
     */
    maxDate: function () {
        console.warn('Unsupported in the mobile applications');
    },

    /**
     * @override
     */
    minDate: function () {
        console.warn('Unsupported in the mobile applications');
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _setLibInputValue: function () {},

    /**
     * @private
     */
    _setupMobilePicker: function () {
        var self = this;
        this.$el.on('click', function () {
            mobile.methods.requestDateTimePicker({
                'value': self.getValue() ? self.getValue().format("YYYY-MM-DD HH:mm:ss") : false,
                'type': self.type_of_date,
                'ignore_timezone': true,
            }).then(function (response) {
                self.$input.val(response.data);
                self.changeDatetime();
            });
        });
    },
});

});
