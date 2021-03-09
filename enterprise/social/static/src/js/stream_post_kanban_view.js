odoo.define('social.social_stream_post_kanban_view', function (require) {
"use strict";

var KanbanView = require('web.KanbanView');
var StreamPostKanbanController = require('social.social_stream_post_kanban_controller');
var StreamPostKanbanModel = require('social.social_stream_post_kanban_model');
var StreamPostKanbanRenderer = require('social.social_stream_post_kanban_renderer');
var viewRegistry = require('web.view_registry');

var StreamPostKanbanView = KanbanView.extend({
    icon: 'fa-share-alt',
    config: _.extend({}, KanbanView.prototype.config, {
        Model: StreamPostKanbanModel,
        Renderer: StreamPostKanbanRenderer,
        Controller: StreamPostKanbanController,
    }),

    /**
     * To summarize the flow:
     *
     * - We load the social.stream.post and display what we already have in database ("super" call) ;
     * - We refresh the account statistics and re-render the statistics block ;
     * - We refresh the streams and IF we detect new content, we display a link to the user to
     *   reload the kanban.
     *
     * We only return the "superPromise" to allow the kanban to load normally while we're doing
     * heavy third party API (facebook/Twitter/...) calls.
     *
     * This method allows speeding up the interface (A LOT).
     *
     * @param {Widget} parent
     * @override
     */
    getController: function (parent) {
        var model = this.getModel(parent);
        var superPromise = this._super.apply(this, arguments);

        Promise.all([
            superPromise,
            model._refreshStreams(),
            model._refreshAccountsStats()
        ]).then(function (results) {
            var controller = results[0];
            var streamsNeedRefresh = results[1];
            var socialAccountsStats = results[2];
            if (streamsNeedRefresh) {
                controller.renderer._refreshStreamsRequired();
            }

            if (socialAccountsStats) {
                controller.renderer._refreshStats(socialAccountsStats);
            }
        });

        return superPromise;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * On first load of the kanban view, we also need to load the accounts stats.
     *
     * @override
     * @private
     */
    _loadData: function (model) {
        return Promise.all([
            model._loadAccountsStats(),
            this._super.apply(this, arguments)
        ]).then(function (results) {
            var socialAccountsStats = results[0];
            var state = results[1];
            if (!state.socialAccountsStats) {
                state.socialAccountsStats = socialAccountsStats;
            }

            return state;
        });
    },
});

viewRegistry.add('social_stream_post_kanban_view', StreamPostKanbanView);

return StreamPostKanbanView;

});
