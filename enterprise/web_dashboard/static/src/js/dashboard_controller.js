odoo.define('web_dashboard.DashboardController', function (require) {
"use strict";

var AbstractController = require('web.AbstractController');
var BasicController = require('web.BasicController');
var core = require('web.core');
var Domain = require('web.Domain');

var _t = core._t;

var DashboardController = AbstractController.extend({
	custom_events: _.extend({}, BasicController.prototype.custom_events, {
        open_view: '_onOpenView',
    }),

    /**
     * @override
     */
    init: function (parent, model, renderer, params) {
        this._super.apply(this, arguments);
        // the dashboard view can trigger domain changes (when fields with a
        // domain attribute are clicked) ; this array registers the current -
        // clicked field specific - filters, so that they can be removed if
        // another field is clicked.
        this.actionDomain = params.actionDomain;
        this.currentFilterIDs = [];
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    getOwnedQueryParams: function () {
        return {context: this.renderer.getsubControllersContext()};
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Opens the requested view in an other action, so that it is displayed in
     * full screen.
     *
     * @private
     * @param {OdooEvent} ev
     * @param {string[]} [ev.data.additionalMeasures] view options to specify
     *  additional fields to consider for measures.
     * @param {Object} ev.data.context
     * @param {string} ev.data.viewType
     */
    _onOpenView: function (ev) {
        ev.stopPropagation();
        var data = ev.data;
        var action = {
            domain: this.actionDomain,
            context: _.omit(data.context, 'timeRangeMenuData'),
            name: _.str.sprintf(_t('%s Analysis'), _.str.capitalize(data.viewType)),
            res_model: this.modelName,
            type: 'ir.actions.act_window',
            views: [[false, data.viewType]],
        };
        if (!_.isEmpty(ev.data.additionalMeasures)) {
            action.flags = {
                additionalMeasures: ev.data.additionalMeasures
            };
        }
        this.do_action(action, {
            controllerState: this.exportState(),
        });
    },
    /**
     * Handles a reload request (it occurs when a field is clicked). If this
     * field as a domain attribute, a new filter for this domain is added to the
     * search view. If another field with a domain attribute has been clicked
     * previously, the corresponding filter is removed from the search view.
     * Finally, triggers a reload of the dashboard with the new combined domain.
     *
     * @override
     * @private
     * @param {OdooEvent} ev
     * @param {Array[]} ev.data.domain
     * @param {string} ev.data.domainLabel
     */
    _onReload: function (ev) {
        ev.stopPropagation();

        /*
        * If we do not have a control panel, this method
        * will not work. e.g. user dashboard
        */
        if (!this._controlPanel) {
            return this.do_warn(
                _t("Incorrect Operation"),
                _t("You cannot apply a filter from this view.")
            );
        }

        var newFilters = [];
        if (ev.data.domain && ev.data.domain.length) {
            newFilters.push({
                type: 'filter',
                domain: Domain.prototype.arrayToString(ev.data.domain),
                description: ev.data.domainLabel
            });
        }
        var filtersToRemove = this.currentFilterIDs || [];
        this.currentFilterIDs = this._controlPanel.updateFilters(newFilters, filtersToRemove);
    },
});

return DashboardController;

});
