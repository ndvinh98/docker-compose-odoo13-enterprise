odoo.define('sale_stock_renting.RentalConfiguratorFormController', function (require) {
"use strict";

var RentalConfiguratorFormController = require('sale_renting.RentalConfiguratorFormController');

/**
 * This controller is overridden to allow configuring sale_order_lines through a popup
 * window when a product with 'rent_ok' is selected.
 *
 */
RentalConfiguratorFormController.include({

    _getRentalInfo: function (state) {
        var infos = this._super.apply(this, arguments);
        var ids = this._convertFromMany2Many(state.lot_ids.data);
        var lotCommands = [
          {operation: 'DELETE_ALL'},
          {operation: 'ADD_M2M', ids: ids}
        ];

        infos['reserved_lot_ids'] = {
          operation: 'MULTI',
          commands: lotCommands
        };
        return infos;
    },

    /**
     * Will convert the values contained in the recordData parameter to
     * a list of '4' operations that can be passed as a 'default_' parameter.
     *
     * @param {Object} recordData
     *
     * @private
     */
    _convertFromMany2Many: function (recordData) {
        if (recordData) {
            var ids = [];
            _.each(recordData, function (data) {
                ids.push({id: parseInt(data.res_id)});
            });

            return ids;
        }

        return null;
    }
});

return RentalConfiguratorFormController;

});
