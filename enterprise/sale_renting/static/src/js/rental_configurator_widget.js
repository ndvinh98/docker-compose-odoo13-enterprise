odoo.define('sale_renting.rental_configurator', function (require) {
var core = require('web.core');
var ProductConfiguratorWidget = require('sale.product_configurator');

var _t = core._t;

/**
 * Extension of the ProductConfiguratorWidget to support rental product configuration.
 * It opens when a rentable product_product is set.
 *
 * The product customization information includes :
 * - is_rental
 * - pickup_date
 * - return_date
 * - reserved_lot_ids (if sale_stock_renting installed)
 *
 */
ProductConfiguratorWidget.include({
    /**
     * Show edit button (in Edit Mode) with a calendar icon
     * after the product/product_template
     *
     * @override
     * @private
     */
    _addConfigurationEditButton: function () {
        if (this.recordData.is_rental) {
            var $inputDropdown = this.$('.o_input_dropdown');
            if ($inputDropdown.length !== 0 && this.$('.o_edit_product_configuration').length === 0) {
                var $editConfigurationButton = $('<button>', {
                    type: 'button',
                    class: 'fa fa-calendar btn btn-secondary o_edit_product_configuration',
                    tabindex: '-1',
                    draggable: false,
                    'aria-label': _t('Edit dates'),
                    title: _t('Edit dates')
                });

                $inputDropdown.after($editConfigurationButton);
            }
        } else {
            this._super.apply(this, arguments);
        }
    },
    /**
     * Override of sale.product_configurator Hook
     *
     * @override
    */
    _isConfigurableLine: function () {
        return this.recordData.is_rental || this._super.apply(this, arguments);
    },


    _onProductChange: function (productId, dataPointID) {
        var self = this;
        return this._super.apply(this, arguments).then(function (stopPropagation) {
            if (stopPropagation) {
                return Promise.resolve(true);
            } else {
                return self._checkIfRentable(productId, dataPointID);
            }
        });
    },

    /**
     * This method will check if the productId needs configuration or not:
     *
     * @param {integer} productId
     * @param {string} dataPointID
     */
    _checkIfRentable: function (productId, dataPointID) {
        var self = this;
        if (productId && this.nodeOptions.rent) {
            return this._rpc({
                model: 'product.product',
                method: 'read',
                args: [productId, ['rent_ok']],
            }).then(function (r) {
                if (r && r[0].rent_ok) {
                    self._openRentalConfigurator({
                            default_product_id: productId
                        },
                        dataPointID
                    );
                    return Promise.resolve(true);
                }
                return Promise.resolve(false);
            });
        }
        return Promise.resolve(false);
    },

    _defaultRentalData: function (data) {
        data = data || {};
        if (this.recordData.pickup_date) {
            data.default_pickup_date = this.recordData.pickup_date;
        }
        if (this.recordData.return_date) {
            data.default_return_date = this.recordData.return_date;
        }
        if (!data.default_product_id) {
            data.default_product_id = this.recordData.product_id.data.id;
        }
        if (this.recordData.id) {
            // when editing a rental order line, we need its id for some availability computations.
            data.default_rental_order_line_id = this.recordData.id;
        }

        data.default_quantity = this.recordData.product_uom_qty;
        if (this.recordData.product_uom) {
            data.default_uom_id = this.recordData.product_uom.data.id;
        }
        data.default_pricelist_id = this.record.evalContext.parent.pricelist_id;
        data.default_company_id = this.record.evalContext.parent.company_id;

        /** Default pickup/return dates are based on previous lines dates if some exists */

        if (!data.default_pickup_date && !data.default_return_date) {
            var parent = this.getParent();
            var defaultPickupDate, defaultReturnDate;
            if (parent.state.data.length > 1) {
                parent.state.data.forEach(function (item) {
                    if (item.data.is_rental) {
                        defaultPickupDate = item.data.pickup_date;
                        defaultReturnDate = item.data.return_date;
                    }
                });
                if (defaultPickupDate) {
                    data.default_pickup_date = defaultPickupDate;
                }
                if (defaultReturnDate) {
                    data.default_return_date = defaultReturnDate;
                }
            }
        }

        /** Sale_stock_renting defaults (to avoid having a very little bit of js in sale_stock_renting) */

        if (this.recordData.reserved_lot_ids) {
            // NEEDS to have the warehouse_id field visible in parent sale_order form view !
            data.default_warehouse_id = this.record.evalContext.parent.warehouse_id;
            data.default_lot_ids = this._convertFromMany2Many(
                this.recordData.reserved_lot_ids
            );
        }

        return data;
    },

    /**
     * Opens the rental configurator in 'edit' mode.
     *
     * @override
     * @private
     */
    _onEditLineConfiguration: function () {
        if (this.recordData.is_rental) {// and in rental app ? (this.nodeOptions.rent)
            this._openRentalConfigurator({}, this.dataPointID);
        } else {
            this._super.apply(this, arguments);
        }
    },

    _openRentalConfigurator: function (data, dataPointId) {
        var self = this;
        this.do_action('sale_renting.rental_configurator_action', {
            additional_context: self._defaultRentalData(data),
            on_close: function (result) {
                if (result && !result.special) {
                    self.trigger_up('field_changed', {
                        dataPointID: dataPointId,
                        changes: result.rentalConfiguration,
                        onSuccess: function () {
                            // Call post-line init function.
                            self._onLineConfigured();
                        }
                    });
                } else {
                    if (!self.recordData.pickup_date || !self.recordData.return_date) {
                        self.trigger_up('field_changed', {
                            dataPointID: dataPointId,
                            changes: {
                                product_id: false,
                                name: ''
                            },
                        });
                    }
                }
            }
        });
    },
});

return ProductConfiguratorWidget;

});
