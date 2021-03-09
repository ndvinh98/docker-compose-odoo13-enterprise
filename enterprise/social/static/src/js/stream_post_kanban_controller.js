odoo.define('social.social_stream_post_kanban_controller', function (require) {
"use strict";

var AddStreamModal = require('social.social_post_kanban_add_stream_modal');
var core = require('web.core');
var dialogs = require('web.view_dialogs');
var KanbanController = require('web.KanbanController');
var PostKanbanImagesCarousel = require('social.social_post_kanban_images_carousel');

var _t = core._t;
var QWeb = core.qweb;

var StreamPostKanbanController = KanbanController.extend({
    events: _.extend({}, KanbanController.prototype.events, {
        'click .o_social_stream_post_image_more, .o_social_stream_post_image_click': '_onClickMoreImages',
        'click .o_social_js_add_stream': '_onNewStream',
        'click .o_social_account_link_disconnected': '_onRelinkAccount',
    }),
    custom_events: _.extend({}, KanbanController.prototype.custom_events, {
        'new_stream_account_clicked': '_onNewSteamAccountClicked',
        'new_stream_media_clicked': '_onNewSteamMediaClicked',
        'new_content_clicked': '_onClickNewContent',
    }),

    /**
     * We need to know if there are accounts configured to know which buttons to show
     * (see 'renderButtons').
     *
     * @override
     */
    willStart: function () {
        var self = this;
        var superPromise = this._super.apply(this, arguments);

        var isSocialManagerPromise = this.getSession()
            .user_has_group('social.group_social_manager').then(function (hasGroup){
                self.isSocialManager = hasGroup;
        });

        var hasAccountsPromise = this._rpc({
            model: 'social.account',
            method: 'search_count',
            args: [[]]
        }).then(function (accountsCount) {
            self.hasAccounts = accountsCount > 0;
            return Promise.resolve();
        });

        return Promise.all([superPromise, isSocialManagerPromise, hasAccountsPromise]);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     * @param {jQueryElement} $node
     */
    renderButtons: function ($node) {
        this.$buttons = $(QWeb.render('StreamPostKanbanView.buttons', {
            hasAccounts: this.hasAccounts
        }));
        this.$buttons.appendTo($node);
        this.$buttons.on('click', '.o_stream_post_kanban_new_post', this._onNewPost.bind(this));
        this.$buttons.on('click', '.o_stream_post_kanban_new_stream', this._onNewStream.bind(this));
        this.$buttons.on('click', '.o_stream_post_kanban_refresh_now', this._onRefreshNow.bind(this));
        this._updateButtons();
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Triggers when the user clicks on an image or on the '+' if there are too many images.
     * We open a 'carousel' in a popup window so that the user can browse all the images.
     *
     * @param {MouseEvent} ev
     * @private
     */
    _onClickMoreImages: function (ev) {
        var $target = $(ev.currentTarget);

        new PostKanbanImagesCarousel(
            this, {
                'activeIndex': $target.data('currentIndex'),
                'images': $target.closest('.o_social_stream_post_image').data('images')
            }
        ).open();
    },

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onNewPost: function (ev) {
        ev.preventDefault();

        this.do_action({
            name: _t('New Post'),
            type: 'ir.actions.act_window',
            res_model: 'social.post',
            views: [[false, 'form']]
        });
    },

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onNewStream: function (ev) {
        ev.preventDefault();

        if (this.renderer.state.socialAccountsStats.length > 0 || this.isSocialManager) {
            this._addNewStream();
        } else {
            this.do_warn(
                _t("Not allowed"),
                _t("No social accounts currently configured, please contact your administrator.")
            );
        }
    },

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onRelinkAccount: function (ev) {
        ev.preventDefault();

        var mediaId = $(ev.currentTarget).data('mediaId');
        if (this.isSocialManager) {
            this._rpc({
                model: 'social.media',
                method: 'action_add_account',
                args: [[mediaId]]
            }).then(function (action) {
                document.location = action.url;
            });
        } else {
            this.do_warn(
                _t("Not allowed"),
                _t("Sorry, you're not allowed to re-link this account, please contact your administrator.")
            );
        }
    },

    /**
     * @private
     */
    _onClickNewContent: function () {
        this.reload();
    },

    /**
     * @private
     * @param {OdooEvent} event
     */
    _onNewSteamAccountClicked: function (event) {
        // Do NOT replace with do_action as we need the modal to close after save.
        new dialogs.FormViewDialog(this, {
            title: _t('Add a stream'),
            res_model: 'social.stream',
            context: {
                default_media_id: event.data.mediaId,
                default_account_id: event.data.accountId
            },
            disable_multiple_selection: true,
            on_saved: this.reload.bind(this, {}),
        }).open();
    },

    /**
     * Redirects to account addition link retrieved by the 'action_add_account' method on
     * the selected media.
     *
     * @param {OdooEvent} event
     * @private
     */
    _onNewSteamMediaClicked: function (event) {
        this._rpc({
            model: 'social.media',
            method: 'action_add_account',
            args: [[event.data.mediaId]]
        }).then(function (action) {
            document.location = action.url;
        });
    },

    /**
     * Will refresh all streams content as well as social.accounts statistics.
     *
     * @private
     */
    _onRefreshNow: function () {
        var self = this;

        this.$buttons.find('.o_stream_post_kanban_refresh_now').addClass('disabled');
        this.$buttons.find('.o_stream_post_kanban_refresh_now .fa-spinner').removeClass('d-none');
        Promise.all([
            this.model._refreshStreams(),
            this.model._refreshAccountsStats()
        ]).then(function (results) {
            var streamsNeedRefresh = results[0];
            var socialAccountsStats = results[1];
            if (streamsNeedRefresh) {
                self.renderer._refreshStreamsRequired();
            }

            if (socialAccountsStats) {
                self.renderer._refreshStats(socialAccountsStats);
            }

            self.$buttons.find('.o_stream_post_kanban_refresh_now').removeClass('disabled');
            self.$buttons.find('.o_stream_post_kanban_refresh_now .fa-spinner').addClass('d-none');
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Updates the $target text based on the fact that the user has already liked
     * (subtract one) or not (add one). The information lies in the userLikes data.
     *
     * Exceptions:
     * - We don't display '0', we hide the text instead
     * - If the count is 0 and we subtract 1 (it can happen with Facebook's 'reactions'), keep 0
     *
     * @param {$.Element} $target
     * @private
     */
    _updateLikesCount: function ($target) {
        var userLikes = $target.data('userLikes');
        $target.data('userLikes', !userLikes);
        var likesCount = $target.find('.o_social_kanban_likes_count').text();
        likesCount = likesCount === '' ? 0 : parseInt(likesCount);

        if (userLikes) {
            if (likesCount > 0) {
                likesCount--;
            }
        } else {
            likesCount++;
        }

        if (likesCount === 0){
            likesCount = '';
        }
        $target.find('.o_social_kanban_likes_count').text(likesCount);
    },

    /**
     * Shows custom stream addition modal.
     *
     * @private
     */
    _addNewStream: function () {
        var self = this;
        this._fetchSocialMedia().then(function (socialMedia) {
            new AddStreamModal(self, {
                isSocialManager: self.isSocialManager,
                socialMedia: socialMedia,
                socialAccounts: self.renderer.state.socialAccountsStats
            }).open();
        });
    },

    /**
     * Fetches media on which you can add remote accounts and streams.
     * We check the fact that they handle streams.
     *
     * @private
     */
    _fetchSocialMedia: function () {
        if (this.socialMedia) {
            return Promise.resolve(this.socialMedia);
        } else {
            var self = this;
            return new Promise(function (resolve) {
                self._rpc({
                    model: 'social.media',
                    method: 'search_read',
                    domain: [['has_streams', '=', 'True']],
                    fields: [
                        'id',
                        'name',
                    ],
                }).then(function (result) {
                    self.socialMedia = result;
                    resolve(self.socialMedia);
                });
            });
        }
    }
});

return StreamPostKanbanController;

});
