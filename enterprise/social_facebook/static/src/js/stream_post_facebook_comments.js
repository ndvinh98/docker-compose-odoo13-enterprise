odoo.define('social.social_facebook_post_kanban_comments', function (require) {

var core = require('web.core');
var _t = core._t;
var QWeb = core.qweb;

var StreamPostComments = require('social.social_post_kanban_comments');

var StreamPostFacebookComments = StreamPostComments.extend({
    init: function (parent, options) {
        this.options = _.defaults(options || {}, {
            title: _t('Facebook Comments'),
            commentName: _t('comment/reply')
        });

        this.accountId = options.accountId;
        this.totalLoadedComments = options.comments.length;
        this.nextRecordsToken = options.nextRecordsToken;
        this.summary = options.summary;

        this._super.apply(this, arguments);
    },

    willStart: function () {
        var self = this;

        var superDef = this._super.apply(this, arguments);
        var pageInfoDef = this._rpc({
            model: 'social.account',
            method: 'read',
            args: [this.accountId, ['name', 'facebook_account_id']],
        }).then(function (result) {
            self.accountName = result[0].name;
            self.pageFacebookId = result[0].facebook_account_id;

            return Promise.resolve();
        });

        return Promise.all([superDef, pageInfoDef]);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    getAuthorPictureSrc: function (comment) {
        if (comment) {
            if (comment.from && comment.from.picture) {
                return comment.from.picture.data.url;
            } else {
                // unknown author
                return "/web/static/src/img/user_placeholder.jpg";
            }
        } else {
            return _.str.sprintf("https://graph.facebook.com/v3.3/%s/picture?height=48&width=48", this.pageFacebookId);
        }
    },

    getCommentLink: function (comment) {
        return _.str.sprintf("https://www.facebook.com/%s", comment.id);
    },

    getAuthorLink: function (comment) {
        if (comment.from.id) {
            return _.str.sprintf("/social_facebook/redirect_to_profile/%s/%s?name=%s", this.accountId, comment.from.id, encodeURI(comment.from.name));
        } else {
            // unknown author
            return "#";
        }
    },

    isCommentEditable: function (comment) {
        return comment.from.id === this.pageFacebookId;
    },

    getAddCommentEndpoint: function () {
        return '/social_facebook/comment';
    },

    getDeleteCommentEndpoint: function () {
        return 'delete_facebook_comment';
    },

    showMoreComments: function (result) {
        return this.totalLoadedComments < this.summary.total_count;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onLikeComment: function (ev) {
        ev.preventDefault();

        var $target = $(ev.currentTarget);
        var userLikes = $target.data('userLikes');
        this._rpc({
            model: 'social.stream.post',
            method: 'like_facebook_comment',
            args: [[this.postId], $target.data('commentId'), !userLikes]
        });

        $target.toggleClass('o_social_comment_user_likes');
        this._updateLikesCount($target);
    },

    _onLoadMoreComments: function (ev) {
        var self = this;
        ev.preventDefault();

        this._rpc({
            model: 'social.stream.post',
            method: 'get_facebook_comments',
            args: [[this.postId], this.nextRecordsToken]
        }).then(function (result) {
            var $moreComments = $(QWeb.render("social.StreamPostCommentsWrapper", {
                widget: self,
                comments: result.comments
            }));
            self.$('.o_social_comments_messages').append($moreComments);

            self.totalLoadedComments += result.comments.length;
            if (self.totalLoadedComments >= self.summary.total_count) {
                self.$('.o_social_load_more_comments').hide();
            }

            self.nextRecordsToken = result.nextRecordsToken;
        });
    }
});

return StreamPostFacebookComments;

});
