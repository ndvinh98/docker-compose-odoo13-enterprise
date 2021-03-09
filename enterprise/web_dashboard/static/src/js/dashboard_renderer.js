odoo.define('web_dashboard.DashboardRenderer', function (require) {
"use strict";

var config = require('web.config');
var core = require('web.core');
var dataComparisonUtils = require('web.dataComparisonUtils');
var Domain = require('web.Domain');
var fieldUtils = require('web.field_utils');
var FormRenderer = require('web.FormRenderer');
var pyUtils = require('web.py_utils');
var viewRegistry = require('web.view_registry');

var renderComparison = dataComparisonUtils.renderComparison;
var renderVariation = dataComparisonUtils.renderVariation;

var QWeb = core.qweb;

var DashboardRenderer = FormRenderer.extend({
    className: "o_dashboard_view",
    events: {
        'click .o_aggregate.o_clickable': '_onAggregateClicked',
    },
    // override the defaul col attribute for groups as in the dashbard view,
    // labels and fields are displayed vertically, thus allowing to display
    // more fields on the same line
    OUTER_GROUP_COL: 6,

    /**
     * @override
     */
    init: function (parent, state, params) {
        this._super.apply(this, arguments);
        this.mode = 'readonly';
        this.subFieldsViews = params.subFieldsViews;
        this.additionalMeasures = params.additionalMeasures;
        this.subControllers = {};
        this.subControllersContext = _.pick(state.context || {}, 'pivot', 'graph', 'cohort');
        this.subcontrollersNextMeasures = {pivot: {}, graph: {}, cohort: {}};
        var session = this.getSession();
        var currency_id = session.company_currency_id;
        if (session.companies_currency_id && session.user_context.allowed_company_ids) {
            currency_id = session.companies_currency_id[session.user_context.allowed_company_ids[0]];
        }
        this.formatOptions = {
            // in the dashboard view, all monetary values are displayed in the
            // currency of the current company of the user
            currency_id: currency_id,
            // allow to decide if utils.human_number should be used
            humanReadable: function (value) {
                return Math.abs(value) >= 1000;
            },
            // with the choices below, 1236 is represented by 1.24k
            minDigits: 1,
            decimals: 2,
            // avoid comma separators for thousands in numbers when human_number is used
            formatterCallback: function (str) {
                return str;
            }
        };
    },
    /**
     * @override
     */
    on_attach_callback: function () {
        this._super.apply(this, arguments);
        this.isInDOM = true;
        _.invoke(this.subControllers, 'on_attach_callback');
        _.invoke(this.widgets, 'on_attach_callback');
    },
    /**
     * @override
     */
    on_detach_callback: function () {
        this._super.apply(this, arguments);
        this.isInDOM = false;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Returns a dict containing the context of sub views.
     *
     * @returns {Object}
     */
    getsubControllersContext: function () {
        return _.mapObject(this.subControllers, function (controller) {
            // for now the views embedded in a dashboard can be of type
            // cohort, graph, pivot. The getOwnedQueryParams method of their controller
            // does not export anything but a context.
            return controller.getOwnedQueryParams().context;
        });
    },
    /**
     * Overrides to update the context of sub controllers.
     *
     * @override
     */
    updateState: function (state, params) {
        var viewType;
        for (viewType in this.subControllers) {
            this.subControllersContext[viewType] = this.subControllers[viewType].getOwnedQueryParams().context;
        }
        var subControllersContext = _.pick(params.context || {}, 'pivot', 'graph', 'cohort');
        _.extend(this.subControllersContext, subControllersContext);
        for (viewType in this.subControllers) {
            _.extend(this.subControllersContext[viewType], this.subcontrollersNextMeasures[viewType]);
            this.subcontrollersNextMeasures[viewType] = {};
        }
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Add a tooltip on a $node.
     * The message can be customize using the tooltip attribute
     *
     * @param {FieldWidget} widget
     * @param {$node} $node
     */
    _addStatisticTooltip: function ($el, node) {
        $el.tooltip({
            delay: { show: 1000, hide: 0 },
            title: function () {
                return QWeb.render('web_dashboard.StatisticTooltip', {
                    debug: config.isDebug(),
                    node: node,
                });
            }
        });
    },

    /**
     * Renders an aggregate (or formula)'s label.
     *
     * @private
     * @param {Object} node
     * @returns {jQueryElement}
     */
    _renderLabel: function (node) {
        var text = node.attrs.name;
        if ('string' in node.attrs) { // allow empty string
            text = node.attrs.string;
        }
        var $result = $('<label>', {text: text});
        return $result;
    },
    /**
     * Renders a statistic (from an aggregate or a formula) with its label.
     * If a widget attribute is specified, and if there is no corresponding
     * formatter, instanciates a widget to render the value. Otherwise, simply
     * uses the corresponding formatter (with a fallback on the field's type).
     *
     * @private
     * @param {Object} node
     * @returns {jQueryElement}
     */
    _renderStatistic: function (node) {
        var self = this;
        var $label = this._renderLabel(node);

        var $el = $('<div>')
            .attr('name', node.attrs.name)
            .append($label);
        var $value;
        var statisticName = node.attrs.name;
        var variation;
        var formatter;
        var statistic = self.state.fieldsInfo.dashboard[statisticName];
        var valueLabel =  statistic.value_label ? (' ' + statistic.value_label) : '';
        if (!node.attrs.widget || (node.attrs.widget in fieldUtils.format)) {
            // use a formatter to render the value if there exists one for the
            // specified widget attribute, or there is no widget attribute
            var fieldValue = self.state.data[statisticName];
            fieldValue = _.contains(['date', 'datetime'], statistic.type) ? (fieldValue === 0 ? NaN : moment(fieldValue)) : fieldValue;
            var formatType = node.attrs.widget || statistic.type;
            formatter = fieldUtils.format[formatType];
            if (this.state.compare) {
                var comparisonValue = this.state.comparisonData[statisticName];
                comparisonValue = _.contains(['date', 'datetime'], statistic.type) ? (comparisonValue === 0 ? NaN : moment(comparisonValue)) : comparisonValue;
                variation = this.state.variationData[statisticName];
                renderComparison($el, fieldValue, comparisonValue, variation, formatter, statistic, this.formatOptions);
                $('.o_comparison', $el).append(valueLabel);

            } else {
                fieldValue = isNaN(fieldValue) ? '-' : formatter(fieldValue, statistic, this.formatOptions);
                $value = $('<div>', {class: 'o_value'}).html(fieldValue + valueLabel);
                $el.append($value);
            }
        } else {
            if (this.state.compare) {
                // use fakeState here too (to change domain)?
                var $originalValue = this._renderFieldWidget(node, this.state);
                var fakeState = _.clone(this.state);
                fakeState.data = fakeState.comparisonData;
                var $comparisonValue = this._renderFieldWidget(node, fakeState);
                variation = this.state.variationData[statisticName];
                fakeState.data[statisticName] = variation;

                $el
                .append(renderVariation(variation, statistic))
                .append($('<div>', {class: 'o_comparison'}).append(
                    $originalValue,
                    $('<span>').html(" vs "),
                    $comparisonValue
                ));
            } else {
                // instantiate a widget to render the value if there is no formatter
                $value = this._renderFieldWidget(node, this.state).addClass('o_value');
                $el.append($value);
            }
        }

        // customize border left
        if (variation) {
            if (variation > 0) {
                $el.addClass('border-success');
            } else if (variation < 0) {
                $el.addClass('border-danger');
            }
        }

        this._registerModifiers(node, this.state, $el);
        if (config.isDebug() || node.attrs.help) {
            this._addStatisticTooltip($el, node);
        }
        return $el;
    },
    /**
     * Renders the buttons of a given sub view, with an additional button to
     * open the view in full screen.
     *
     * @private
     */
    _renderSubViewButtons: function ($el, controller) {
        var $buttons = $('<div>', {class: 'o_' + controller.viewType + '_buttons o_dashboard_subview_buttons'});

        // render the view's buttons
        controller.renderButtons($buttons);

        // we create a button's group, get the primary button(s)
        // and put it/them into this group
        var $buttonGroup = $('<div class="btn-group">');
        $buttonGroup.append($buttons.find('[aria-label="Main actions"]'));
        $buttonGroup.append($buttons.find('.o_dropdown:has(.o_group_by_menu)'));
        $buttonGroup.prependTo($buttons);

        // render the button to open the view in full screen
        $('<button>')
            .addClass("btn btn-outline-secondary fa fa-arrows-alt float-right o_button_switch")
            .attr({title: 'Full Screen View', viewType: controller.viewType})
            .tooltip()
            .on('click', this._onViewSwitcherClicked.bind(this))
            .appendTo($buttons);

        // select primary and interval buttons and alter their style
        $buttons.find('.btn-primary,.btn-secondary')
            .removeClass('btn-primary btn-secondary o_dropdown_toggler_btn')
            .addClass("btn-outline-secondary");
        $buttons.find('[class*=interval_button]').addClass('text-muted text-capitalize');
        // remove bars icon on "Group by" button
        $buttons.find('.fa.fa-bars').removeClass('fa fa-bars');

        $buttons.prependTo($el);
    },
    /**
     * @private
     * @param {Object} node
     * @returns {jQueryElement}
     */
    _renderTagAggregate: function (node) {
        var $aggregate = this._renderStatistic(node).addClass('o_aggregate');
        var isClickable = node.attrs.clickable === undefined || pyUtils.py_eval(node.attrs.clickable);
        $aggregate.toggleClass('o_clickable', isClickable);

        var $result = $('<div>').addClass('o_aggregate_col').append($aggregate);
        this._registerModifiers(node, this.state, $result);
        return $result;
    },
    /**
     * @private
     * @param {Object} node
     * @returns {jQueryElement}
     */
    _renderTagFormula: function (node) {
        return this._renderStatistic(node).addClass('o_formula');
    },
    /**
     * In the dashboard, both inner and outer groups are rendered the same way:
     * with a div (no table), i.e. like the outer group of the form view.
     *
     * @override
     * @private
     */
    _renderTagGroup: function (node) {
        var $group = this._renderOuterGroup(node);
        if (node.children.length && node.children[0].tag === 'widget') {
            $group.addClass('o_has_widget');
        }
        return $group;
    },
    /**
     * Handles nodes with tagname 'view': instanciates the requested view,
     * renders its buttons and returns a jQuery element containing the buttons
     * and the controller's $el.
     *
     * @private
     * @param {Object} node
     * @returns {jQueryElement}
     */
    _renderTagView: function (node) {
        var self = this;
        var viewType = node.attrs.type;
        var controllerContext = this.subControllersContext[viewType];
        var searchQuery = {
            context: _.extend({}, this.state.context, controllerContext),
            domain: this.state.domain,
            groupBy: [],
        };
        var subViewParams = {
            modelName: this.state.model,
            withControlPanel: false,
            hasSwitchButton: true,
            isEmbedded: true,
            additionalMeasures: this.additionalMeasures,
            searchQuery: searchQuery,
        };
        var SubView = viewRegistry.get(viewType);
        var subView = new SubView(this.subFieldsViews[viewType], subViewParams);
        var $div = $('<div>', {class: 'o_subview', type: viewType});
        var def = subView.getController(this).then(function (controller) {
            return controller.appendTo($div).then(function () {
                self._renderSubViewButtons($div, controller);
                self.subControllers[viewType] = controller;
            });
        });
        this.defs.push(def);
        return $div;
    },
    /**
     * Overrides to destroy potentially previously instantiates sub views, and
     * to call 'on_attach_callback' on the new sub views and the widgets if the
     * dashboard is already in the DOM when being rendered.
     *
     * @override
     * @private
     */
    _renderView: function () {
        var self = this;
        var oldControllers = _.values(this.subControllers);
        var r = this._super.apply(this, arguments);
        return r.then(function () {
            _.invoke(oldControllers, 'destroy');
            if (self.isInDOM) {
                _.invoke(self.subControllers, 'on_attach_callback');
                _.invoke(self.widgets, 'on_attach_callback');
            }
        });
    },
    /**
     * Overrides to get rid of the FormRenderer logic about fields, as there is
     * no field tag in the dashboard view. Simply updates the renderer's $el.
     *
     * @private
     * @override
     */
    _updateView: function ($newContent) {
        this.$el.html($newContent);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the click on a measure (i.e. a real field of the model, not a
     * formula). Activates this measure on subviews, and if there is a domain
     * specified, activates this domain on the whole dashboard.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onAggregateClicked: function (ev) {
        // update the measure(s) of potential graph and pivot subcontrollers
        // (this doesn't trigger a reload, it only updates the internal state
        // of those controllers)
        var aggregate = ev.currentTarget.getAttribute('name');
        var aggregateInfo = this.state.fieldsInfo.dashboard[aggregate];
        var measure = aggregateInfo.measure !== undefined ? aggregateInfo.measure : aggregateInfo.field;
        if (this.subControllers.pivot) {
            this.subcontrollersNextMeasures.pivot.pivot_measures = [measure];
        }
        if (this.subControllers.graph) {
            this.subcontrollersNextMeasures.graph.graph_measure = measure;
        }
        if (this.subControllers.cohort) {
            this.subcontrollersNextMeasures.cohort.cohort_measure = measure;
        }
        // update the domain and trigger a reload
        var domain = new Domain(aggregateInfo.domain);
        // I don't know if it is a good idea to use this.state.fields[measure].string
        var label = aggregateInfo.domain_label || aggregateInfo.string || aggregateInfo.name;
        this.trigger_up('reload', {
            domain: domain.toArray(),
            domainLabel: label,
        });
    },
    /**
     * Sends a request to open the given view in full screen.
     *
     * @todo; take the current domain into account, once it will be correctly
     * propagated to subviews
     * @private
     * @param {MouseEvent} ev
     */
    _onViewSwitcherClicked: function (ev) {
        ev.stopPropagation();
        var viewType = $(ev.currentTarget).attr('viewType');
        var controller = this.subControllers[viewType];
        this.trigger_up('open_view', {
            // for now the views embedded in a dashboard can be of type
            // cohort, graph, pivot. The getOwnedQueryParams method of their controller
            // does not export anything but a context.
            context: _.extend({}, this.state.context, controller.getOwnedQueryParams().context),
            viewType: viewType,
            additionalMeasures: this.additionalMeasures,
        });
    },
});

return DashboardRenderer;

});
