odoo.define('social.social_stream_post_kanban_model', function (require) {
"use strict";

var KanbanModel = require('web.KanbanModel');

var StreamPostKanbanModel = KanbanModel.extend({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Method responsible for refreshing the configured streams.
     * It will be called on view loading as well as when the user clicks on the 'Refresh' button.
     *
     * @private
     */
    _refreshStreams: function () {
        return this._rpc({
            model: 'social.stream',
            method: 'refresh_all'
        }, {
            shadow: true
        });
    },

    /**
     * Method responsible for refreshing the 'dashboard' view of social.accounts.
     * It will be called on view loading as well as when the user clicks on the 'Refresh' button.
     *
     * Also refreshes live.post statistics (for 'engagement' field).
     *
     * @private
     */
    _refreshAccountsStats: function () {
        this._rpc({
            model: 'social.live.post',
            method: 'refresh_statistics'
        }, {
            shadow: true
        });

        return this._rpc({
            model: 'social.account',
            method: 'refresh_statistics'
        }, {
            shadow: true
        });
    },

    /**
     * Will load the social.account statistics that are used to populate the dashboard on
     * top of the 'Feed' (social.stream.post grouped by 'stream_id') kanban view.
     *
     * @private
     */
    _loadAccountsStats: function () {
        return this._rpc({
            model: 'social.account',
            method: 'search_read',
            domain: [['has_account_stats', '=', true]],
            fields: [
                'id',
                'name',
                'is_media_disconnected',
                'audience',
                'audience_trend',
                'engagement',
                'engagement_trend',
                'stories',
                'stories_trend',
                'has_trends',
                'media_id',
                'stats_link'
            ],
        });
    },
});

return StreamPostKanbanModel;

});
