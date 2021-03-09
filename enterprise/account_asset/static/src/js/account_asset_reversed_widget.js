odoo.define('account_asset.widget', function(require) {
"use strict";

/**
 * The purpose of this widget is to shows a toggle button on depreciation and
 * installment lines for posted/unposted line. When clicked, it calls the method
 * create_move on the object account.asset.depreciation.line.
 * Note that this widget can only work on the account.asset.depreciation.line
 * model as some of its fields are harcoded.
 */

var AbstractField = require('web.AbstractField');
var core = require('web.core');
var registry = require('web.field_registry');

var _t = core._t;

var AccountAssetReversedWidget = AbstractField.extend({
    noLabel: true,

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    isSet: function () {
        return true; // it should always be displayed, whatever its value
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _render: function () {
        if (this.recordData.reversal_move_id.res_ids.length) {
            var $icon = $('<i/>', {
                title: _t('This move has been reversed')
            }).addClass('fa fa-exclamation-circle')
            this.$el.html($icon);
        }
    },

});

registry.add("deprec_lines_reversed", AccountAssetReversedWidget);

});
