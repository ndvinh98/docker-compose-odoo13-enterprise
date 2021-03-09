odoo.define('stock_barcode.picking_quality_client_action', function (require) {
'use strict';

var core = require('web.core');
var PickingClientAction = require('stock_barcode.picking_client_action');

var _t = core._t;

var PickingQualityClientAction = PickingClientAction.include({
    custom_events: _.extend({}, PickingClientAction.prototype.custom_events, {
        'picking_check_quality': '_onCheckQuality',
    }),

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _checkQuality: function () {
        var self = this;
        this.mutex.exec(function () {
            return self._save().then(function () {
                return self._rpc({
                    'model': 'stock.picking',
                    'method': 'check_quality',
                    'args': [[self.actionParams.pickingId]],
                }).then(function(res) {
                    var exitCallback = function () {
                        self.trigger_up('reload');
                    };
                    if (_.isObject(res)) {
                        var options = {
                            on_close: exitCallback,
                        };
                        return self.do_action(res, options)
                    } else {
                        self.do_notify(_t("No more quality checks"), _t("All the quality checks have been done."));
                    }
                });
            });
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onCheckQuality: function (ev) {
        ev.stopPropagation();
        this._checkQuality();
    },

});
return PickingQualityClientAction;

});
