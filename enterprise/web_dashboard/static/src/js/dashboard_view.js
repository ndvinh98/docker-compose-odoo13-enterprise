odoo.define('web_dashboard.DashboardView', function (require) {
"use strict";

/**
 * This file defines the Dashboard view and adds it to the view registry. This
 * is a reporting that can embed graph and/or pivot views, and displays
 * aggregate values (obtained from read_group RPCs). It is based on the FormView
 * (extensions of FormRenderer, BasicView and BasicModel).
 */

var BasicView = require('web.BasicView');
var core = require('web.core');
var viewRegistry = require('web.view_registry');

var DashboardController = require('web_dashboard.DashboardController');
var DashboardModel = require('web_dashboard.DashboardModel');
var DashboardRenderer = require('web_dashboard.DashboardRenderer');

var _lt = core._lt;

var DashboardView = BasicView.extend({
    config: _.extend({}, BasicView.prototype.config, {
        Model: DashboardModel,
        Controller: DashboardController,
        Renderer: DashboardRenderer,
    }),
    display_name: _lt('Dashboard'),
    searchMenuTypes: ['filter', 'timeRange', 'favorite'],
    icon: 'fa-tachometer',
    viewType: 'dashboard',

    /**
     * @override
     */
	init: function (viewInfo, params) {
        this._super.apply(this, arguments);
        this.modelName = params.modelName;

        this.controllerParams.actionDomain = (params.action && params.action.domain) || [];

        this.rendererParams.subFieldsViews = {};

        // pass all measurable fields to subviews
        var fields = this.fieldsInfo.dashboard;
        var additionalMeasures = _.pluck(_.filter(fields, {realType: 'many2one'}), 'field');
        this.rendererParams.additionalMeasures = additionalMeasures;

        this.loadParams.aggregates = this.fieldsView.aggregates;
        this.loadParams.formulas = this.fieldsView.formulas;

	},

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Overrides to fetch the fieldsView of subviews.
     *
     * @override
     * @private
     */
    _loadData: function (model) {
        var self = this;

        var subViewsDef;
        if (this.fieldsView.subViews.length) {
            subViewsDef = model
                .loadViews(this.modelName, this.loadParams.context, this.fieldsView.subViews)
                .then(function (fieldsViews) {
                    for (var viewType in fieldsViews) {
                        self.rendererParams.subFieldsViews[viewType] = fieldsViews[viewType];
                    }
                });
        }

        var superDef = this._super.apply(this, arguments);
        return Promise.all([superDef, subViewsDef]).then(function (results) {
            // the parent expects a promise resolved with a dataPoint id, but
            // with this override, it becomes a promise resolved with an Array,
            // whose first element is the dataPoint id
            var dataPointID = results[0];
            return dataPointID;
        });
    },
    /**
     * Processes nodes with tagName 'aggregate'. Same API as _processNode.
     *
     * @private
     * @param {Object} node
     * @param {Object} fv
     * @returns {boolean}
     */
    _processAggregateNode: function (node, fv) {
        var aggregateID = node.attrs.name;
        var field = fv.viewFields[node.attrs.field];

        var aggregate = _.defaults({}, node.attrs, {
            domain: '[]',
            group_operator: field.group_operator,
        });
        aggregate.Widget = this._getFieldWidgetClass('dashboard', field, aggregate);

        // in the dashboard views, many2one fields are fetched with the
        // group_operator 'count_distinct', which means that the values
        // manipulated client side for these fields are integers
        if (field.type === 'many2one') {
            field.type = 'integer';
            field.realType = 'many2one';
            aggregate.realType = 'many2one';
            aggregate.group_operator = 'count_distinct';
        }
        aggregate.type = field.type;

        fv.fieldsInfo.dashboard[aggregateID] = aggregate;
        fv.viewFields[node.attrs.name] = _.extend({}, field, {
            name: node.attrs.name,
        });
        fv.aggregates.push(aggregateID);
        return false;
    },
    /**
     * In the dashboard view, additional tagnames are allowed: 'view', 'formula'
     * and 'aggregate'. We override the processing of the arch to gather
     * information about the occurrences of these tagnames in the arch.
     *
     * @override
     * @private
     */
    _processArch: function (arch, fv) {
        fv.aggregates = [];
        fv.formulas = {};
        fv.subViews = [];
        // there are no field nodes in the dashboard arch, so viewFields is
        // basically a shallow copy of fields, which is the dict shared between
        // all views, and which is thus (deeply) frozen ; we here deeply clone
        // it so that we can change (in place) the type of many2one fields into
        // integer.
        fv.viewFields = $.extend(true, {}, fv.viewFields);
        this._super.apply(this, arguments);
    },
    /**
     * Processes nodes with tagName 'formula'. Same API as _processNode.
     *
     * @private
     * @param {Object} node
     * @param {Object} fv
     * @returns {boolean}
     */
    _processFormulaNode: function (node, fv) {
        var formulaID = node.attrs.name || _.uniqueId('formula_');
        node.attrs.name = formulaID;

        var formula = _.extend({}, node.attrs, {type: 'float'});
        var fakeField = {name: formulaID, type: 'float'};
        formula.Widget = this._getFieldWidgetClass('dashboard', fakeField, formula);

        fv.fieldsInfo.dashboard[formulaID] = formula;
        fv.viewFields[formulaID] = fakeField;
        fv.formulas[formulaID] = _.pick(node.attrs, 'string', 'value');
        return false;
    },
    /**
     * Overrides to handle nodes with tagname 'aggregate', 'formula' and 'view'.
     *
     * @override
     * @private
     */
    _processNode: function (node, fv) {
        var res = this._super.apply(this, arguments);

        if (node.tag === 'aggregate') {
            res = this._processAggregateNode(node, fv);
        }
        if (node.tag === 'formula') {
            res = this._processFormulaNode(node, fv);
        }
        if (node.tag === 'view') {
            fv.subViews.push([node.attrs.ref, node.attrs.type]);
            res = false;
        }

        return res;
    },
    _updateMVCParams: function () {
        var self = this;
        this._super.apply(this, arguments);
        // add '*_view_ref' keys in context, to fetch the adequate view
        _.each(this.fieldsView.subViews, function (subView) {
            if (subView[0]) {
                self.loadParams.context[subView[1] + '_view_ref'] = subView[0];
            }
        });
        // replaces the xmlids by false in the views description
        this.fieldsView.subViews = _.map(this.fieldsView.subViews, function (subView) {
            return [false, subView[1]]; // e.g. [false, 'graph']
        });
    }
});

viewRegistry.add('dashboard', DashboardView);

return DashboardView;

});
