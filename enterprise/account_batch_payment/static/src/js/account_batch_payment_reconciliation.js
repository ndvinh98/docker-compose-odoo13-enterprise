odoo.define('account_batch_payment.reconciliation', function (require) {
"use strict";

var ReconciliationClientAction = require('account.ReconciliationClientAction');
var ReconciliationModel = require('account.ReconciliationModel');
var ReconciliationRenderer = require('account.ReconciliationRenderer');
var core = require('web.core');

var _t = core._t;
var QWeb = core.qweb;

//--------------------------------------------------------------------------

var Action = {
    custom_events: _.defaults({
        select_batch: '_onAction',
    }, ReconciliationClientAction.StatementAction.prototype.custom_events),
};

ReconciliationClientAction.StatementAction.include(Action);
ReconciliationClientAction.ManualAction.include(Action);

//--------------------------------------------------------------------------

var Model = {
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.batchPayments = [];
        this.modes  = [...this.modes, 'batch'];
        this.filter_batch = "";
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @param {Object} context
     * @param {number[]} context.statement_ids
     * @returns {Promise}
     */
    load: function (context) {
        var self = this;
        return this._super(context).then(function () {
            self.batchPayments = self.statement && self.statement.batch_payments || [];
        });
    },
    /**
     *
     * @param {string} handle
     * @param {number} batchId
     * @returns {Promise}
     */
    selectBatch: function(handle, batchId) {
        return this._rpc({
                model: 'account.reconciliation.widget',
                method: 'get_move_lines_by_batch_payment',
                args: [this.getLine(handle).id, batchId],
            })
            .then(this._addSelectedBatchLines.bind(this, handle, batchId));
    },

    /**
     * @override
     *
     * @param {(string|string[])} handle
     * @returns {Promise<Object>} resolved with an object who contains
     *   'handles' key
     */
    validate: function (handle) {
        var self = this;
        return this._super(handle).then(function (data) {
            if (_.any(data.handles, function (handle) {
                    return !!self.getLine(handle).batch_payment_id;
                })) {
                return self._updateBatchPayments().then(function () {
                    return data;
                });
            }
            return data;
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @private
     * @param {Object}
     * @returns {Promise}
     */
    _computeLine: function (line) {
        if (line.st_line.partner_id) {
            line.relevant_payments = [];
        } else {
            // Batch Payments can only be used when there is no partner selected
            line.relevant_payments = this.batchPayments;
        }
        return this._super.apply(this, arguments);
    },
    /**
     *
     * @private
     * @param {string} handle
     * @param {number} batchId
     * @returns {Promise}
     */
    _addSelectedBatchLines: function (handle, batchId, batchLines) {
        var line = this.getLine(handle);
        // Check if some lines are already selected in another reconciliation
        var selectedIds = [];
        for (var hand in this.lines) {
            if (handle === hand) {
                continue;
            }
            var rec = this.lines[hand].reconciliation_proposition || [];
            for (var k in rec) {
                if (!isNaN(rec[k].id)) {
                    selectedIds.push(rec[k].id);
                }
            }
        }
        selectedIds = _.filter(batchLines, function (batch_line) {
            return selectedIds.indexOf(batch_line.id) !== -1;
        });
        if (selectedIds.length > 0) {
            var message = _t("Some journal items from the selected batch payment are already selected in another reconciliation : ");
            message += _.map(selectedIds, function(l) { return l.name; }).join(', ');
            this.do_warn(_t("Incorrect Operation"), message, true);
            return;
        }

        // remove double
        if (line.reconciliation_proposition) {
            batchLines = _.filter(batchLines, function (batch_line) {
                return !_.any(line.reconciliation_proposition, function (prop) {
                    return prop.id === batch_line.id;
                });
            });
        }

        // add batch lines as proposition
        this._formatLineProposition(line, batchLines);
        for (var k in batchLines) {
            this._addProposition(line, batchLines[k]);
            line['mv_lines_match_rp'] = _.filter(line['mv_lines_match_rp'], l => l['id'] != batchLines[k].id);
        }
        line.batch_payment_id = batchId;
        return Promise.all([this._computeLine(line)]);
    },
    /**
     * load data from
     * - 'account.bank.statement' fetch the batch payments data
     *
     * @param {number[]} statement_ids
     * @returns {Promise}
     */
    _updateBatchPayments: function(statement_ids) {
        var self = this;
        return this._rpc({
                model: 'account.reconciliation.widget',
                method: 'get_batch_payments_data',
                args: [statement_ids],
            })
            .then(function (data) {
                self.batchPayments = data;
            });
    },
    changeFilter: function (handle, filter) {
        var line = this.getLine(handle);
        if (line.mode == 'batch') {
            this.filter_batch = filter;
            return Promise.resolve();
        } else {
            return this._super.apply(this, arguments);
        }
    },
    _getAvailableModes: function(handle) {
        var line = this.getLine(handle);
        var modes = this._super(handle);
        if (line.batchPayments && line.batchPayments.length) {
            modes.push('batch')
        }
        return modes;
    },
};

ReconciliationModel.StatementModel.include(Model);
ReconciliationModel.ManualModel.include(Model);

//--------------------------------------------------------------------------

var Renderer = {
    events: _.defaults({
        "click .batch_payment": "_onBatch",
    }, ReconciliationRenderer.LineRenderer.prototype.events),

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     *
     * @param {object} state - statement line
     */
    update: function (state) {
        this._super(state);
        this.$(".o_notebook .tab-content .batch_payments_selector").html("");
        if (state.relevant_payments.length) {
            this.$(".o_notebook .tab-content .batch_payments_selector").append(QWeb.render("batch.payment.tab", {
                payments: state.relevant_payments.filter(pay => pay.name.toUpperCase().includes(this.model.filter_batch.toUpperCase())
                                                             || pay.date.toUpperCase().includes(this.model.filter_batch.toUpperCase())),
                filter: this.model.filter_batch,
            }));
        }
        this.$(".o_notebook .batch_payments_selector").toggleClass('d-none', state.relevant_payments.length == 0);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     *
     * @param {MouseEvent} event
     */
    _onBatch: function(e) {
        e.preventDefault();
        var batchId = parseInt(e.currentTarget.dataset.batch_payment_id);
        this.trigger_up('select_batch', {'data': batchId});
    },
};

ReconciliationRenderer.LineRenderer.include(Renderer);
ReconciliationRenderer.ManualLineRenderer.include(Renderer);

});
