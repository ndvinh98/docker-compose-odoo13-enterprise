odoo.define('helpdesk.dashboard', function (require) {
"use strict";

/**
 * This file defines the Helpdesk Dashboard view (alongside its renderer, model
 * and controller), extending the Kanban view.
 * The Helpdesk Dashboard view is registered to the view registry.
 * A large part of this code should be extracted in an AbstractDashboard
 * widget in web, to avoid code duplication (see SalesTeamDashboard).
 */

var core = require('web.core');
var KanbanController = require('web.KanbanController');
var KanbanModel = require('web.KanbanModel');
var KanbanRenderer = require('web.KanbanRenderer');
var KanbanView = require('web.KanbanView');
var session = require('web.session');
var view_registry = require('web.view_registry');

var QWeb = core.qweb;

var _t = core._t;
var _lt = core._lt;

var HelpdeskDashboardRenderer = KanbanRenderer.extend({
    events: _.extend({}, KanbanRenderer.prototype.events, {
        'click .o_dashboard_action': '_onDashboardActionClicked',
        'click .o_target_to_set': '_onDashboardTargetClicked',
    }),

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Notifies the controller that the target has changed.
     *
     * @private
     * @param {string} target_name the name of the changed target
     * @param {string} value the new value
     */
    _notifyTargetChange: function (target_name, value) {
        this.trigger_up('dashboard_edit_target', {
            target_name: target_name,
            target_value: value,
        });
    },

    /**
     * @override
     * @private
     * @returns {Promise}
     */
    _render: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            var values = self.state.dashboardValues;
            var helpdesk_dashboard = QWeb.render('helpdesk.HelpdeskDashboard', {
                widget: self,
                show_demo: values.show_demo,
                rating_enable: values.rating_enable,
                success_rate_enable: values.success_rate_enable,
                values: values,
            });
            self.$el.prepend(helpdesk_dashboard);
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent}
     */
    _onDashboardActionClicked: function (e) {
        e.preventDefault();
        var $action = $(e.currentTarget);
        this.trigger_up('dashboard_open_action', {
            action_name: $action.attr('name'),
        });
    },
    /**
     * @private
     * @param {MouseEvent}
     */
    _onDashboardTargetClicked: function (e) {
        var self = this;
        var $target = $(e.currentTarget);
        var target_name = $target.attr('name');
        var target_value = $target.attr('value');

        var $input = $('<input/>', {type: "text", name: target_name});
        if (target_value) {
            $input.attr('value', target_value);
        }
        $input.on('keyup input', function (e) {
            if (e.which === $.ui.keyCode.ENTER) {
                self._notifyTargetChange(target_name, $input.val());
            }
        });
        $input.on('blur', function () {
            self._notifyTargetChange(target_name, $input.val());
        });
        $input.replaceAll($target)
              .focus()
              .select();
    },
});

var HelpdeskDashboardModel = KanbanModel.extend({
    /**
     * @override
     */
    init: function () {
        this.dashboardValues = {};
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    get: function (localID) {
        var result = this._super.apply(this, arguments);
        if (_.isObject(result)) {
            result.dashboardValues = this.dashboardValues[localID];
        }
        return result;
    },
    /**
     * @œverride
     * @returns {Promise}
     */
    load: function () {
        return this._loadDashboard(this._super.apply(this, arguments));
    },
    /**
     * @œverride
     * @returns {Promise}
     */
    reload: function () {
        return this._loadDashboard(this._super.apply(this, arguments));
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Promise} super_def a promise that resolves with a dataPoint id
     * @returns {Promise -> string} resolves to the dataPoint id
     */
    _loadDashboard: function (super_def) {
        var self = this;
        var dashboard_def = this._rpc({
            model: 'helpdesk.team',
            method: 'retrieve_dashboard',
        });
        return Promise.all([super_def, dashboard_def]).then(function(results) {
            var id = results[0];
            var dashboardValues = results[1];
            self.dashboardValues[id] = dashboardValues;
            return id;
        });
    },
});

var HelpdeskDashboardController = KanbanController.extend({
    custom_events: _.extend({}, KanbanController.prototype.custom_events, {
        dashboard_open_action: '_onDashboardOpenAction',
        dashboard_edit_target: '_onDashboardEditTarget',
    }),

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {OdooEvent} e
     */
    _onDashboardEditTarget: function (e) {
        var target_name = e.data.target_name;
        var target_value = e.data.target_value;
        if (isNaN(target_value)) {
            this.do_warn(_t("Wrong value entered!"), _t("Only Integer Value should be valid."));
        } else {
            var values = {};
            values[target_name] = parseInt(target_value);
            this._rpc({
                    model: 'res.users',
                    method: 'write',
                    args: [[session.uid], values],
                })
                .then(this.reload.bind(this));
        }
    },
    /**
     * @private
     * @param {OdooEvent} e
     */
    _onDashboardOpenAction: function (e) {
        var self = this;
        var action_name = e.data.action_name;
        if (_.contains(['action_view_rating_today', 'action_view_rating_7days'], action_name)) {
            return this._rpc({model: this.modelName, method: action_name})
                .then(function (data) {
                    if (data) {
                    return self.do_action(data);
                    }
                });
        }
        return this.do_action(action_name);
    },
});

var HelpdeskDashboardView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Model: HelpdeskDashboardModel,
        Renderer: HelpdeskDashboardRenderer,
        Controller: HelpdeskDashboardController,
    }),
    display_name: _lt('Dashboard'),
    icon: 'fa-dashboard',
    searchview_hidden: true,
});

view_registry.add('helpdesk_dashboard', HelpdeskDashboardView);

return {
    Model: HelpdeskDashboardModel,
    Renderer: HelpdeskDashboardRenderer,
    Controller: HelpdeskDashboardController,
};

});
