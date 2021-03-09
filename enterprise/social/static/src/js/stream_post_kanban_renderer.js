odoo.define('social.social_stream_post_kanban_renderer', function (require) {
"use strict";

var core = require('web.core');
var KanbanColumn = require('web.KanbanColumn');
var KanbanRenderer = require('web.KanbanRenderer');
var QWeb = core.qweb;

/**
 * Simple override in order to provide a slightly modified template that shows the
 * social.media icon before the social.stream name (if grouped by stream_id).
 */
var StreamPostKanbanColumn = KanbanColumn.extend({
    template: 'social.KanbanView.Group'
});

var StreamPostKanbanRenderer = KanbanRenderer.extend({
    config: _.extend({}, KanbanRenderer.prototype.config, {
        KanbanColumn: StreamPostKanbanColumn
    }),

    /**
     * We use a little trick here.
     * We add an element BEFORE this $el because the kanban view has a special type of content
     * disposition (flex with 'row' flex-direction) that makes it impossible to add element
     * on top of it that takes the full width of the screen.
     *
     * Indeed, if we do that, it makes it so that when the columns exceeds the width of the screen,
     * they will be pushed under the others instead of extending the width by adding a scrollbar.
     *
     * In other words:
     *
     * Screen size:
     *
     * <------------------>
     *
     * We want this:
     *
     * --------------------
     *     dashboard
     * --------------------
     * Stream: 1  Stream: 2  Stream: 3
     * Post 1     Post 1     Post 1
     * Post 2     Post 2     Post 2
     * <------- (scrollbar) --------->
     *
     *
     * If we add the dashboard without putting it before this.$el, we get this:
     *
     * --------------------
     *     dashboard
     * --------------------
     * Stream: 1  Stream: 2
     * Post 1     Post 1
     * Post 2     Post 2
     *
     * Stream: 3
     * Post 1
     * Post 2
     * <- (no scrollbar) ->
     *
     * In addition, we add a special class to 'o_content' to get the right background color
     * for the dashboard when the user scrolls right.
     */
    start: function () {
        var self = this;
        this.$before = this._createBeforeSectionElement();
        return this._super.apply(this, arguments).then(function () {
            self.$el.before(self.$before);
            self.$el.closest('.o_content').addClass('o_social_stream_post_kanban_view_wrapper bg-100');
            self._prependNewContentElement();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * This method will prepend to the Kanban a "New Content" link that is shown whenever we detect
     * new content available for the streams.
     * When clicked, it triggers a 'new_content_clicked' event caught by the controller.
     */
    _prependNewContentElement: function () {
        var self = this;
        this.$el.closest('.o_content').prepend($('<a>', {
            class: 'o_social_stream_post_kanban_new_content alert alert-info mb-0 text-center border-bottom' + (this.refreshRequired ? '' : ' d-none'),
            href: '#',
            text: _('New content available.')
        }).append($('<i>', {
            class: 'fa fa-refresh ml-2 mr-1'
        })).append($('<b>', {
            text: _('Click to refresh.')
        })).on('click', function (ev) {
            ev.preventDefault();
            $(ev.currentTarget).addClass('d-none');
            self.refreshRequired = false;
            self.trigger_up('new_content_clicked');
        }));
    },

    /**
     * Our socialAccountsStats cache variable need to be kept between state updates
     *
     * @override
     */
    _setState: function () {
        var socialAccountsStats = this.state.socialAccountsStats;
        this._super.apply(this, arguments);
        this.state.socialAccountsStats = socialAccountsStats;
    },

    /**
     * Overridden to display a custom dashboard on top of the kanban.
     *
     * @override
     * @private
     * @returns {Promise}
     */
    _render: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            if (!self.refreshRequired) {
                self.$el
                    .closest('.o_content')
                    .find('.o_social_stream_post_kanban_new_content')
                    .addClass('d-none');
            }
            self._renderAccountStats();
        });
    },

    /**
     * Renders the custom account stats dashboard on top of the kanban and handles popovers.
     *
     * @private
     */
    _renderAccountStats: function () {
        this.$before.empty();
        if (this.state.socialAccountsStats && this.state.socialAccountsStats.length !== 0) {
            var $socialAccountsStats = QWeb.render(
                'social.AccountsStats',
                {socialAccounts: this.state.socialAccountsStats}
            );

            if (this.$before.find('.o_social_stream_stat_box').length > 0) {
                var $newElement = this._createBeforeSectionElement();
                $newElement.append($socialAccountsStats);
                // We use replaceWith to avoid as much flickering as possible.
                this.$before.replaceWith($newElement);
            } else {
                this.$before.append($socialAccountsStats);
            }

            // This DOM element is periodically refreshed (removed/re-rendered) by the kanban view (when refreshing statistics).
            // If the element is removed while its popover is open, the popover will not be closed automatically anymore.
            // That's why we need to listen to the "remove" event and dispose the popover accordingly.
            var $popoverElement = this.$before.find('[data-toggle="popover"]');
            $popoverElement.on("remove", () => {
                $popoverElement.popover('dispose');
            });
            $popoverElement.popover({
                trigger: 'hover'
            });
        }
    },

    /**
     * @private
     */
    _createBeforeSectionElement: function () {
        return $('<section/>', {
            class: 'o_social_stream_post_kanban_before d-flex flex-nowrap border-bottom'
        });
    },

    /**
     * Overridden because we want to show it even when 'this.state.isGroupedByM2ONoColumn' is true
     * This will be the default state when the user lands on the kanban view for this first time.
     * (Since it's grouped by stream by default.)
     *
     * @private
     * @override
     */
    _toggleNoContentHelper: function (remove) {
        var displayNoContentHelper =
            !remove &&
            !this._hasContent() &&
            !!this.noContentHelp &&
            !(this.quickCreate && !this.quickCreate.folded);

        var $noContentHelper = this.$('.o_view_nocontent');

        if (displayNoContentHelper && !$noContentHelper.length) {
            this.$el.append(this._renderNoContentHelper());
        }
        if (!displayNoContentHelper && $noContentHelper.length) {
            $noContentHelper.remove();
        }
    },

    /**
     * Marks the renderer as 'Refresh Required', meaning we detected new content for the streams.
     *
     * We do it this way to avoid blocking the interface while the streams are refreshing because we
     * depend on external service calls that can take a long time to answer.
     *
     * To summarize the flow:
     * 1. We display what we already have in database
     * 2. IF we detect new content, we display a link to the user to reload the kanban
     *
     * @private
     */
    _refreshStreamsRequired: function () {
        this.refreshRequired = true;
        if (this.$el) {
            this.$el
                .closest('.o_content')
                .find('.o_social_stream_post_kanban_new_content')
                .removeClass('d-none');
        }
    },

    /**
     * 2 use cases here:
     * - We already have a "$el" element, meaning the rendering part is done and we need to
     * refresh the statistics container by re-rendering it.
     * - We don't have an "$el" element yet, meaning the rendering will use the refreshed stats
     * from the state and we don't need to render anything.
     *
     * @param {Array} socialAccountsStats social.account statistics
     * @private
     */
    _refreshStats: function (socialAccountsStats) {
        this.state.socialAccountsStats = socialAccountsStats;
        if (this.$el) {
            this._renderAccountStats();
        }
    }
});

return StreamPostKanbanRenderer;

});
