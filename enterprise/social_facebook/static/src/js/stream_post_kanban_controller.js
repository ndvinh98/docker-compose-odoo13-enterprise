odoo.define('social_facebook.social_stream_post_kanban_controller', function (require) {
"use strict";

var StreamPostKanbanController = require('social.social_stream_post_kanban_controller');
var StreamPostFacebookComments = require('social.social_facebook_post_kanban_comments');

StreamPostKanbanController.include({
    events: _.extend({}, StreamPostKanbanController.prototype.events, {
        'click .o_social_facebook_comments': '_onFacebookCommentsClick',
        'click .o_social_facebook_likes': '_onFacebookPostLike',
        'click .o_social_stream_post_kanban_global:not(a,i)': '_onClickFacebookRecord'
    }),

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onFacebookCommentsClick: function (ev) {
        var self = this;
        var $target = $(ev.currentTarget);

        var postId = $target.data('postId');
        this._rpc({
            model: 'social.stream.post',
            method: 'get_facebook_comments',
            args: [[postId]]
        }).then(function (result) {
            new StreamPostFacebookComments(
                self,
                {
                    postId: postId,
                    accountId: $target.data('facebookPageId'),
                    originalPost: $target.data(),
                    comments: result.comments,
                    summary: result.summary,
                    nextRecordsToken: result.nextRecordsToken
                }
            ).open();
        });
    },

    _onFacebookPostLike: function (ev) {
        ev.preventDefault();

        var $target = $(ev.currentTarget);
        var userLikes = $target.data('userLikes');
        this._rpc({
            model: 'social.stream.post',
            method: 'like_facebook_post',
            args: [[$target.data('postId')], !userLikes]
        });

        this._updateLikesCount($target);
        $target.toggleClass('o_social_facebook_user_likes');
    },

    /**
     * We want to open the "comments modal" when clicking on the record.
     * Unless we clicked on a link, a button or an image (that opens the carousel).
     *
     * @param {MouseEvent} ev
     */
    _onClickFacebookRecord: function (ev) {
        var $target = $(ev.target);
        if ($target.closest('a,.o_social_subtle_btn,img').length !== 0) {
            return;
        }

        ev.preventDefault();

        $(ev.currentTarget)
            .find('.o_social_comments')
            .click();
    }
});

return StreamPostKanbanController;

});
