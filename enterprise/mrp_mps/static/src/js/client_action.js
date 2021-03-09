odoo.define('mrp_mps.ClientAction', function (require) {
'use strict';

var concurrency = require('web.concurrency');
var core = require('web.core');
var Pager = require('web.Pager');
var AbstractAction = require('web.AbstractAction');
var Dialog = require('web.Dialog');
var field_utils = require('web.field_utils');
var session = require('web.session');

var QWeb = core.qweb;
var _t = core._t;

const defaultPagerSize = 20;

var ClientAction = AbstractAction.extend({
    contentTemplate: 'mrp_mps',
    hasControlPanel: true,
    loadControlPanel: true,
    withSearchBar: true,
    events: {
        'change .o_mrp_mps_input_forcast_qty': '_onChangeForecast',
        'change .o_mrp_mps_input_replenish_qty': '_onChangeToReplenish',
        'click .o_mrp_mps_automatic_mode': '_onClickAutomaticMode',
        'click .o_mrp_mps_create': '_onClickCreate',
        'click .o_mrp_mps_edit': '_onClickEdit',
        'click .o_mrp_mps_open_details': '_onClickOpenDetails',
        'click .o_mrp_mps_procurement': '_onClickReplenish',
        'click .o_mrp_mps_record_url': '_onClickRecordLink',
        'click .o_mrp_mps_unlink': '_onClickUnlink',
        'focus .o_mrp_mps_input_forcast_qty': '_onFocusForecast',
        'focus .o_mrp_mps_input_replenish_qty': '_onFocusToReplenish',
        'mouseover .o_mrp_mps_procurement': '_onMouseOverReplenish',
        'mouseout .o_mrp_mps_procurement': '_onMouseOutReplenish',
    },
    custom_events: {
        search: '_onSearch',
    },

    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.actionManager = parent;
        this.action = action;
        this.context = action.context;
        this.domain = [];

        this.companyId = false;
        this.groups = false;
        this.date_range = [];
        this.formatFloat = field_utils.format.float;
        this.manufacturingPeriod = false;
        this.manufacturingPeriods = [];
        this.state = false;

        this.active_ids = [];
        this.recordsPager = false;
        this.mutex = new concurrency.Mutex();

        this.controlPanelParams.modelName = 'mrp.production.schedule';
    },

    willStart: function () {
        var self = this;
        var _super = this._super.bind(this);
        var args = arguments;

        var def_control_panel = this._rpc({
            model: 'ir.model.data',
            method: 'get_object_reference',
            args: ['mrp_mps', 'mrp_mps_search_view'],
            kwargs: {context: session.user_context},
        })
        .then(function (viewId) {
            self.controlPanelParams.viewId = viewId[1];
        });

        var def_content = this._getRecordIds();

        return Promise.all([def_content, def_control_panel]).then(function () {
            return self._getState().then(function () {
                return _super.apply(self, args);
            });
        });
    },

    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.update_cp();
            self.renderPager();
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    
    /**
     */
     renderPager: function () {
         var self = this;
         this.pager = new Pager(this, this.recordsPager.length, 1, defaultPagerSize);
         this.pager.on('pager_changed', this, function (newState) {
            var current_min = newState.current_min - 1;
            this.active_ids = self.recordsPager.slice(current_min, current_min + newState.limit).map(i => i.id);
            this._reloadContent();
         });
         this.$pager = $('<div>', {
             class: 'o_mrp_mps_pager float-right',
         });
         this.pager.appendTo(this.$pager).then(function () {
             self.pager.enable();
         });
         this.$pager.appendTo(this._controlPanel.$el.find('.o_cp_right'));
     },

    /**
     * Update the control panel in order to add the 'replenish' button and a
     * custom menu with checkbox buttons in order to hide/display the different
     * rows.
     */
    update_cp: function () {
        var self = this;
        this.$buttons = $(QWeb.render('mrp_mps_control_panel_buttons'));
        this._update_cp_buttons();
        var $replenishButton = this.$buttons.find('.o_mrp_mps_replenish');
        $replenishButton.on('click', self._onClickReplenish.bind(self));
        $replenishButton.on('mouseover', self._onMouseOverReplenish.bind(self));
        $replenishButton.on('mouseout', self._onMouseOutReplenish.bind(self));
        this.$buttons.find('.o_mrp_mps_create').on('click', self._onClickCreate.bind(self));
        this.$searchview_buttons = $(QWeb.render('mrp_mps_control_panel_option_buttons', {groups: self.groups}));
        this.$searchview_buttons.find('.o_mps_mps_show_line').on('click', self._onChangeCompany.bind(self));
        this.updateControlPanel({
            title: _t('Master Production Schedule'),
            cp_content: {
                $buttons: this.$buttons,
                $searchview_buttons: this.$searchview_buttons
            },
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _actionOpenDetails: function (procurementId, action, dateStr, dateStart, dateStop) {
        var self = this;
        this.mutex.exec(function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: action,
                args: [procurementId, dateStr, dateStart, dateStop]
            }).then(function (action){
                return self.do_action(action);
            });
        });
    },

    /**
     * Make an rpc to replenish the different schedules passed as arguments.
     * If the procurementIds list is empty, it replenish all the schedules under
     * the current domain. Reload the content after the replenish in order to
     * display the new forecast cells to run.
     *
     * @private
     * @param {Array} [productionScheduleId] mrp.production.schedule id to
     * replenish or False if it needs to replenish all schedules in state.
     * @return {Promise}
     */
    _actionReplenish: function (productionScheduleId) {
        var self = this;
        var ids;
        var basedOnLeadTime;
        if (productionScheduleId.length) {
            ids = productionScheduleId;
            basedOnLeadTime = false;
        }
        else {
            ids = self.active_ids;
            basedOnLeadTime = true;
        }
        this.mutex.exec(function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'action_replenish',
                args: [ids, basedOnLeadTime]
            }).then(function (){
                return self._reloadContent();
            });
        });
    },

    _backToState: function (productionScheduleId) {
        var state = _.where(_.flatten(_.values(this.state)), {id: productionScheduleId});
        return this._renderState(state);
    },

    /**
     * Open the mrp.production.schedule form view in order to create the record.
     * Once the record is created get its state and render it.
     *
     * @private
     * @return {Promise}
     */
    _createProduct: function () {
        var self = this;
        var exitCallback = function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'search_read',
                args: [[], ['id']],
                limit: 1,
                orderBy: [{name: 'id', asc: false}]
            }).then(function (result) {
                if (result.length) {
                    return self._renderProductionSchedule(result[0].id);
                }
            });
        };
        this.mutex.exec(function () {
            return self.do_action('mrp_mps.action_mrp_mps_form_view', {
                on_close: exitCallback,
            });
        });
    },

    /**
     * Open the mrp.production.schedule form view in order to edit the record.
     * Once the record is edited get its state and render it.
     *
     * @private
     * @return {Promise}
     */
    _editProduct: function (productionScheduleId) {
        var self = this;
        var exitCallback = function () {
            return self._renderProductionSchedule(productionScheduleId);
        };
        this.mutex.exec(function () {
            return self.do_action({
                name: 'Edit Production Schedule',
                type: 'ir.actions.act_window',
                res_model: 'mrp.production.schedule',
                views: [[false, 'form']],
                target: 'new',
                res_id: productionScheduleId,
            }, {
                on_close: exitCallback,
            });
        });
    },

    _focusNextInput: function (productionScheduleId, dateIndex, inputName) {
        var tableSelector = '.table-responsive[data-id=' + productionScheduleId + ']';
        var rowSelector = 'tr[name=' + inputName + ']';
        var inputSelector = 'input[data-date_index=' + (dateIndex + 1) + ']';
        return $([tableSelector, rowSelector, inputSelector].join(' ')).select();
    },

    _getRecordIds: function () {
        var self = this;
        return this._rpc({
            model: 'mrp.production.schedule',
            method: 'search_read',
            domain: this.domain,
            fields: ['id'],
        }).then(function (ids) {
            self.recordsPager = ids;
            self.active_ids = ids.slice(0, defaultPagerSize).map(i => i.id);
        });
    },

    /**
     * Make an rpc to get the state and afterwards set the company, the
     * manufacturing period, the groups in order to display/hide the differents
     * rows and the state that contains all the informations
     * about production schedules and their forecast for each period.
     *
     * @private
     * @return {Promise}
     */
    _getState: function () {
        var self = this;
        var domain = this.domain.concat([['id', 'in', this.active_ids]]);
        return this._rpc({
            model: 'mrp.production.schedule',
            method: 'get_mps_view_state',
            args: [domain],
        }).then(function (state) {
            self.companyId = state.company_id;
            self.manufacturingPeriods = state.dates;
            self.state = state.production_schedule_ids;
            self.manufacturingPeriod = state.manufacturing_period;
            self.groups = state.groups[0];
            return state;
        });
    },

    _getProductionScheduleState: function (productionScheduleId) {
        var self = this;
        return self._rpc({
            model: 'mrp.production.schedule',
            method: 'get_impacted_schedule',
            args: [productionScheduleId, self.domain],
        }).then(function (productionScheduleIds) {
            productionScheduleIds.push(productionScheduleId);
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'get_production_schedule_view_state',
                args: [productionScheduleIds],
            }).then(function (states) {
                for (var i = 0; i < states.length; i++) {
                    var state = states[i];
                    var index =  _.findIndex(self.state, {id: state.id});
                    if (index >= 0) {
                        self.state[index] = state;
                    }
                    else {
                        self.state.push(state);
                    }
                }
                return states;
            });
        });
    },

    /**
     * reload all the production schedules inside content. Make an rpc to the
     * server in order to get the updated state and render it.
     *
     * @private
     * @return {Promise}
     */
    _reloadContent: function () {
        var self = this;
        return this._getState().then(function () {
            var $content = $(QWeb.render('mrp_mps', {
                widget: {
                    manufacturingPeriods: self.manufacturingPeriods,
                    state: self.state,
                    groups: self.groups,
                    formatFloat: self.formatFloat,
                }
            }));
            $('.o_mrp_mps').replaceWith($content);
            self._update_cp_buttons();
        });
    },

    _removeQtyToReplenish: function (dateIndex, productionScheduleId) {
        var self = this;
        this.mutex.exec(function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'remove_replenish_qty',
                args: [productionScheduleId, dateIndex],
            }).then(function () {
                return self._renderProductionSchedule(productionScheduleId);
            });
        });
    },

    /**
     * Get the state with an rpc and render it with qweb. If the production
     * schedule is already present in the view replace it. Else append it at the
     * end of the table.
     *
     * @private
     * @param {Array} [productionScheduleIds] mrp.production.schedule ids to render
     * @return {Promise}
     */
    _renderProductionSchedule: function (productionScheduleId) {
        var self = this;
        return this._getProductionScheduleState(productionScheduleId).then(function (states) {
            return self._renderState(states);
        });
    },

    _renderState: function (states) {
        for (var i = 0; i < states.length; i++) {
            var state = states[i];

            var $table = $(QWeb.render('mrp_mps_production_schedule', {
                manufacturingPeriods: this.manufacturingPeriods,
                productionSchedule: state,
                groups: this.groups,
                formatFloat: this.formatFloat,
            }));
            var $tableId = $('.table-responsive[data-id='+ state.id +']');
            if ($tableId.length) {
                $tableId.replaceWith($table);
            } else {
                var $warehouse = false;
                if ('warehouse_id' in state) {
                    $warehouse = $('.table-responsive[data-warehouse_id='+ state.warehouse_id[0] +']');
                }
                if ($warehouse.length) {
                    $warehouse.last().append($table);
                } else {
                    $('.o_mrp_mps').append($table);
                }
            }
        }
        this._update_cp_buttons();
        return Promise.resolve();
    },

    /**
     * Save the company settings and hide or display the rows. It will not
     * reload the whole page but just add/remove the o_hidden class.
     *
     * @private
     * @param {Object} [values] {field_name: field_value}
     * @return {Promise}
     */
    _saveCompanySettings: function (values) {
        var self = this;
        this.mutex.exec(function () {
            return self._rpc({
                model: 'res.company',
                method: 'write',
                args: [[self.companyId], values],
            }).then(function () {
                self._reloadContent();
            });
        });
    },

    /**
     * Save the forecasted quantity and reload the current schedule in order
     * to update its To Replenish quantity and its safety stock (current and
     * future period). Also update the other schedules linked by BoM in order
     * to update them depending the indirect demand.
     *
     * @private
     * @param {Object} [productionScheduleId] mrp.production.schedule Id.
     * @param {Integer} [dateIndex] period to save (column number)
     * @param {Float} [forecastQty] The new forecasted quantity
     * @return {Promise}
     */
    _saveForecast: function (productionScheduleId, dateIndex, forecastQty) {
        var self = this;
        this.mutex.exec(function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'set_forecast_qty',
                args: [productionScheduleId, dateIndex, forecastQty],
            }).then(function () {
                return self._renderProductionSchedule(productionScheduleId).then(function () {
                    return self._focusNextInput(productionScheduleId, dateIndex, 'demand_forecast');
                });
            });
        });
    },

    /**
     * Save the quantity To Replenish and reload the current schedule in order
     * to update it's safety stock and quantity in future period. Also mark
     * the cell with a blue background in order to show that it was manually
     * updated.
     *
     * @private
     * @param {Object} [productionScheduleId] mrp.production.schedule Id.
     * @param {Integer} [dateIndex] period to save (column number)
     * @param {Float} [replenishQty] The new quantity To Replenish
     * @return {Promise}
     */
    _saveToReplenish: function (productionScheduleId, dateIndex, replenishQty) {
        var self = this;
        this.mutex.exec(function () {
            return self._rpc({
                model: 'mrp.production.schedule',
                method: 'set_replenish_qty',
                args: [productionScheduleId, dateIndex, replenishQty],
            }).then(function () {
                return self._renderProductionSchedule(productionScheduleId).then(function () {
                    return self._focusNextInput(productionScheduleId, dateIndex, 'to_replenish');
                });
            }, function () {
                // Get the state with productionScheduleId as id
                return self._backToState(productionScheduleId);
            });
        });
    },

    /**
     * Unlink the production schedule and remove it from the DOM. Use a
     * confirmation dialog in order to avoid a mistake from the user.
     *
     * @private
     * @param {Object} [productionScheduleId] mrp.production.schedule Id.
     * @return {Promise}
     */
    _unlinkProduct: function (productionScheduleId) {
        var self = this;
        function doIt() {
            self.mutex.exec(function () {
                return self._rpc({
                    model: 'mrp.production.schedule',
                    method: 'unlink',
                    args: [productionScheduleId],
                }).then(function () {
                    self._reloadContent();
                });
            });
        }
        Dialog.confirm(this, _t("Are you sure you want to delete this record ?"), {
            confirm_callback: doIt,
        });
    },

    _update_cp_buttons: function () {
        var recodsLen = Object.keys(this.state).length;
        var $addProductButton = this.$buttons.find('.o_mrp_mps_create');
        if (recodsLen) {
            $addProductButton.addClass('btn-secondary');
            $addProductButton.removeClass('btn-primary');
        } else {
            $addProductButton.addClass('btn-primary');
            $addProductButton.removeClass('btn-secondary');
        }
        var toReplenish = _.filter(_.flatten(_.values(this.state)), function (mps) {
            if (_.where(mps.forecast_ids, {'to_replenish': true}).length) {
                return true;
            } else {
                return false;
            }
        });
        var $replenishButton = this.$buttons.find('.o_mrp_mps_replenish');
        if (toReplenish.length) {
            $replenishButton.removeClass('o_hidden');
        } else {
            $replenishButton.addClass('o_hidden');
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the click on company option under search bar. It will write it on
     * the field and hide/display the related rows.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onChangeCompany: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.target);
        var values = {};
        values[$target.data('value')] = $target.prop('checked');
        this._saveCompanySettings(values);
    },

    /**
     * Handles the change on a forecast cell.
     *
     * @private
     * @param {jQuery.Event} ev
     */
    _onChangeForecast: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.target);
        var dateIndex = $target.data('date_index');
        var productionScheduleId = $target.closest('.table-responsive').data('id');
        var forecastQty = parseFloat($target.val());
        if (isNaN(forecastQty)){
            this._backToState(productionScheduleId);
        } else {
            this._saveForecast(productionScheduleId, dateIndex, forecastQty);
        }
    },

    /**
     * Handles the quantity To Replenish change on a forecast cell.
     *
     * @private
     * @param {jQuery.Event} ev
     */
    _onChangeToReplenish: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.target);
        var dateIndex = $target.data('date_index');
        var productionScheduleId= $target.closest('.table-responsive').data('id');
        var replenishQty = parseFloat($target.val());
        if (isNaN(replenishQty)){
            this._backToState(productionScheduleId);
        } else {
            this._saveToReplenish(productionScheduleId, dateIndex, replenishQty);
        }
    },

    _onClickAutomaticMode: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.target);
        var dateIndex = $target.data('date_index');
        var productionScheduleId = $target.closest('.table-responsive').data('id');
        this._removeQtyToReplenish(dateIndex, productionScheduleId);
    },


    /**
     * Handles the click on `add product` Event. It will display a form view in
     * order to create a production schedule and add it to the template.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickCreate: function (ev) {
        ev.stopPropagation();
        this._createProduct();
    },

    /**
     * Handles the click on `min..max` or 'targeted stock' Event. It will open
     * a form view in order to edit a production schedule and update the
     * template on save.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickEdit: function (ev) {
        ev.stopPropagation();
        var productionScheduleId = $(ev.target).closest('.table-responsive').data('id');
        this._editProduct(productionScheduleId);
    },

    _onClickOpenDetails: function (ev) {
        ev.preventDefault();
        var $target = $(ev.target);
        var dateStart = $target.data('date_start');
        var dateStop = $target.data('date_stop');
        var dateStr = this.manufacturingPeriods[$target.data('date_index')];
        var action = $target.data('action');
        var productionScheduleId = $target.closest('.table-responsive').data('id');
        this._actionOpenDetails(productionScheduleId, action, dateStr, dateStart, dateStop);
    },

    /**
     * Handles the click on product name. It will open the product form view
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickRecordLink: function (ev) {
        ev.preventDefault();
        return this.do_action({
            type: 'ir.actions.act_window',
            res_model: $(ev.currentTarget).data('model'),
            res_id: $(ev.currentTarget).data('res-id'),
            views: [[false, 'form']],
            target: 'current'
        });
    },

    /**
     * Handles the click on replenish button. It will call action_replenish with
     * all the Ids present in the view.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickReplenish: function (ev) {
        ev.stopPropagation();
        var productionScheduleId = [];
        var $table = $(ev.target).closest('.table-responsive');
        if ($table.length) {
            productionScheduleId = [$table.data('id')];
        }
        this._actionReplenish(productionScheduleId);
    },

    /**
     * Handles the click on unlink button. A dialog ask for a confirmation and
     * it will unlink the product.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickUnlink: function (ev) {
        ev.preventDefault();
        var productionScheduleId = $(ev.target).closest('.table-responsive').data('id');
        this._unlinkProduct(productionScheduleId);
    },

    _onFocusForecast: function (ev) {
        ev.preventDefault();
        $(ev.target).select();
    },

    _onFocusToReplenish: function (ev) {
        ev.preventDefault();
        $(ev.target).select();
    },

    _onMouseOverReplenish: function (ev) {
        ev.stopPropagation();
        var table = $(ev.target).closest('tbody');
        var replenishClass = '.o_mrp_mps_forced_replenish';
        if (! table.length) {
            table = $('tr');
            replenishClass = '.o_mrp_mps_to_replenish';
        }
        table.find(replenishClass).addClass('o_mrp_mps_hover');
    },

    _onMouseOutReplenish: function (ev) {
        ev.stopPropagation();
        var table = $(ev.target).closest('tbody');
        if (! table.length) {
            table = $('tr');
        }
        table.find('.o_mrp_mps_hover').removeClass('o_mrp_mps_hover');
    },

    /**
     * Handles the change on the search bar. Save the domain and reload the
     * content with the new domain.
     *
     * @private
     * @param {jQuery.Event} ev
     */
    _onSearch: function (event) {
        event.stopPropagation();
        var self = this;
        this.domain = event.data.domain;
        this.$pager.remove();
        this.pager.destroy();
        this._getRecordIds().then(function () {
            self.renderPager();
            self._reloadContent();
        });
    },
});

core.action_registry.add('mrp_mps_client_action', ClientAction);

return ClientAction;

});
