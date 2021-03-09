odoo.define('stock_barcode.LinesQualityWidget', function (require) {
'use strict';

var LinesWidget = require('stock_barcode.LinesWidget');

var LinesQualityWidget = LinesWidget.include({
    events: _.extend({}, LinesWidget.prototype.events, {
        'click .o_check_quality': '_onClickCheckQuality',
    }),

    init: function (parent, page, pageIndex, nbPages) {
        this._super.apply(this, arguments);
        this.quality_check_todo = parent.currentState.quality_check_todo;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the click on the `Quality Checks` button.
     *
     * @private
     * @param {MouseEvent} ev
     */
     _onClickCheckQuality: function (ev) {
        ev.stopPropagation();
        this.trigger_up('picking_check_quality');
    },
});

return LinesQualityWidget;

});
