odoo.define('social.social_post_kanban_comments_delete', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var _t = core._t;

/**
 * Simple Dialog extension that will delete the given social post comment if confirmed
 * by the user or close otherwise.
 */
var StreamPostCommentDelete = Dialog.extend({
    template: 'social.StreamPostCommentDeleteModal',

    init: function (parent, options) {
        options = _.defaults(options || {}, {
            title: _t('Delete Comment'),
            buttons: [{
                classes: 'btn-primary',
                text: _t('Ok'),
                click: this._onConfirmCommentDelete.bind(this)
            }, {
                text: _t('Cancel'),
                close: true
            }]
        });

        this.postId = options.postId;
        this.commentId = options.commentId;
        this.commentName = options.commentName;
        this.deleteCommentEndpoint = options.deleteCommentEndpoint;

        this._super.apply(this, arguments);
    },

    /**
     * Since this confirmation modal is displayed on top of the comments modal,
     * we need this small hack the place it properly on the screen.
     */
    willStart: function () {
        var self = this;

        return this._super.apply(this, arguments).then(function () {
            self.$modal.addClass('o_social_comment_delete_modal');
            return Promise.resolve();
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * When the user confirms the deletion, this method will rpc the server to trigger
     * the actual deletion and send a 'comment_deleted' event so that the caller can
     * take the appropriate action (i.e deleting the comment element from the view).
     *
     * @param {MouseEvent} ev
     */
    _onConfirmCommentDelete: function (ev) {
        var self = this;

        this._rpc({
            model: 'social.stream.post',
            method: this.deleteCommentEndpoint,
            args: [[this.postId], this.commentId]
        }).then(function () {
            self.trigger('comment_deleted');
            self.close();
        });
    }
});

return StreamPostCommentDelete;

});
