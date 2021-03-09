odoo.define('sale_renting.RentalConfiguratorFormController', function (require) {
"use strict";

var FormController = require('web.FormController');

/**
 * This controller is overridden to allow configuring sale_order_lines through a popup
 * window when a product with 'rent_ok' is selected.
 *
 */
var RentalConfiguratorFormController = FormController.extend({

    _getRentalInfo: function (state) {
        return {
            pickup_date: state.pickup_date,
            return_date: state.return_date,
            price_unit: state.unit_price,
            product_uom_qty: state.quantity,
            is_rental: true,
        };
    },

    /**
     * We let the regular process take place to allow the validation of the required fields
     * to happen.
     *
     * Then we can manually close the window, providing rental information to the caller.
     *
     * @override
     */
    saveRecord: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            var state = self.renderer.state.data;
            self.do_action({type: 'ir.actions.act_window_close', infos: {
                rentalConfiguration: self._getRentalInfo(state)
            }});
        });
    },


});

return RentalConfiguratorFormController;

});
