odoo.define('social_twitter.social_stream_post_kanban_controller', function (require) {
"use strict";

var StreamPostKanbanController = require('social.social_stream_post_kanban_controller');
var StreamPostTwitterComments = require('social.StreamPostTwitterComments');

StreamPostKanbanController.include({
    events: _.extend({}, StreamPostKanbanController.prototype.events, {
        'click .o_social_twitter_comments': '_onTwitterCommentsClick',
        'click .o_social_twitter_likes': '_onTwitterTweetLike'
    }),

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onTwitterCommentsClick: function (ev) {
        var self = this;
        var $target = $(ev.currentTarget);

        var postId = $target.data('postId');
        this._rpc({
            model: 'social.stream.post',
            method: 'get_twitter_comments',
            args: [[postId]]
        }).then(function (result) {
            new StreamPostTwitterComments(
                self,
                {
                    postId: postId,
                    originalPost: $target.data(),
                    streamId: $target.data('streamId'),
                    accountId: $target.data('twitterAccountId'),
                    allComments: result.comments
                }
            ).open();
        });
    },

    _onTwitterTweetLike: function (ev) {
        ev.preventDefault();

        var $target = $(ev.currentTarget);
        var userLikes = $target.data('userLikes');
        this._rpc({
            route: _.str.sprintf('social_twitter/%s/like_tweet', $target.data('streamId')),
            params: {
                tweet_id: $target.data('twitterTweetId'),
                like: !userLikes
            }
        });

        this._updateLikesCount($target);
        $target.toggleClass('o_social_twitter_user_likes');
    }
});

return StreamPostKanbanController;

});
