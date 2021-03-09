odoo.define('social.social_post_kanban_comments', function (require) {

var BasicFields = require('web.basic_fields');
var core = require('web.core');
var Dialog = require('web.Dialog');
var dom = require('web.dom');
var emojis = require('mail.emojis');
var PostKanbanImagesCarousel = require('social.social_post_kanban_images_carousel');
var SocialEmojisMixin = require('social.emoji_mixin');
var SocialStreamPostFormatterMixin = require('social.stream_post_formatter_mixin');
var time = require('web.time');


var _t = core._t;
var FieldBinaryImage = BasicFields.FieldBinaryImage;
var QWeb = core.qweb;

var DATE_TIME_FORMAT = time.getLangDatetimeFormat();


var StreamPostCommentDelete = require('social.social_post_kanban_comments_delete');

/**
 * Base implementation of a comments window for social media implementations.
 *
 * This Dialog is meant to be overridden by actual social media modules implementations
 * (social_facebook, social_twitter, ...).
 *
 * It defines base methods and mechanism that every 'comments' handling needs, such as:
 * - Comments (added / edited / deleted)
 * - Comments image (added / edited / deleted)
 * - Replies to comments (added / edited / deleted)
 * - Like / Dislike comments
 * - Updating the likes count
 * - Emojis support to the comment textarea (through the SocialEmojisMixin)
 * - Loading comment replies
 * - Formatting dates properly
 *
 * It also defines a common Template that is populated through overridden methods, such as:
 * - The comment author picture (getAuthorPictureSrc)
 * - The comment link (getCommentLink)
 * - ...
 */
var StreamPostComments = Dialog.extend(SocialEmojisMixin, SocialStreamPostFormatterMixin, {
    template: 'social.StreamPostComments',
    events: {
        'keydown .o_social_add_comment': '_onAddComment',
        'click .o_social_comment_add_image': '_onAddImage',
        'change .o_input_file': '_onImageChange',
        'click .o_social_write_reply .fa-times': '_onImageRemove',
        'click .o_social_write_reply .o_mail_emoji': '_onEmojiClick',
        'click .o_social_comment_like': '_onLikeComment',
        'click .o_social_edit_comment': '_onEditComment',
        'click .o_social_edit_comment_cancel': '_onEditCommentCancel',
        'click .o_social_delete_comment': '_onDeleteComment',
        'click .o_social_comment_reply': '_onReplyComment',
        'click .o_social_load_more_comments': '_onLoadMoreComments',
        'click .o_social_comment_load_replies': '_onLoadReplies',
        'click .o_social_original_post_image_more, .o_social_original_post_image_click': '_onClickMoreImages',
    },

    init: function (parent, options) {
        options = _.defaults(options || {}, {
            title: options.title || _t('Comments'),
            renderFooter: false,
            size: 'medium',
        });

        this.originalPost = options.originalPost;
        this.emojis = emojis;
        this.postId = options.postId;
        this.comments = options.comments;
        this.commentName = options.commentName;

        this._super.apply(this, arguments);
    },

    /**
     * Used to automatically resize the textarea when the user input exceeds the available space.
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            dom.autoresize(self.$('textarea').first(), {
                parent: self,
                min_height: 60
            });
        });
    },

    //--------------------------------------------------------------------------
    // Methods that should be overridden in Widgets extending this one
    //--------------------------------------------------------------------------

    getAuthorPictureSrc: function (comment) {
        return "";
    },

    getCommentLink: function (comment) {
        return "";
    },

    getAuthorLink: function (comment) {
        return "";
    },

    isCommentEditable: function (comment) {
        return false;
    },

    getLikesClass: function () {
        return "fa-thumbs-up";
    },

    getAddCommentEndpoint: function () {
        return null;
    },

    getDeleteCommentEndpoint: function () {
        return null;
    },

    isCommentDeletable: function () {
        return true;
    },

    showMoreComments: function (result) {
        return false;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Method called when the user presses 'Enter' after writing a comment in the textarea.
     * Replying to a comment will automatically load any existing replies to this comment.
     *
     * @param {MouseEvent} ev
     */
    _onAddComment: function (ev) {
        if (ev.keyCode !== $.ui.keyCode.ENTER ||
            ev.ctrlKey ||
            ev.shiftKey) {
            return;
        }

        ev.preventDefault();
        var $textarea = $(ev.currentTarget);

        if ($textarea.val().trim() === '') {
            return;
        }

        var isCommentReply = $textarea.data('isCommentReply');
        var isCommentEdit = $textarea.data('isCommentEdit');
        var commentId = $textarea.data('commentId');

        this._addComment($textarea, isCommentReply, commentId, isCommentEdit);
        this.$('.o_social_no_comment_message').remove();
    },

    /**
     * Triggers image selection (file system browse).
     *
     * @param {MouseEvent} ev
     */
    _onAddImage: function (ev) {
        ev.preventDefault();

        $(ev.currentTarget)
            .closest('.o_social_write_reply')
            .find('.o_input_file')
            .first()
            .click();
    },

    /**
     * When the user selects a file to attach to the comment, we use the FileReader to display
     * a preview of the image below the comment.
     *
     * This is very similar to what Facebook does when commenting a post.
     *
     * @param {Event} ev
     */
    _onImageChange: function (ev) {
        var $target = $(ev.currentTarget);

        var fileNode = ev.target;
        var fileReader = new FileReader();
        var file = fileNode.files[0];

        if (!file) {
            // the user didn't select a file
            return;
        }

        fileReader.readAsDataURL(file);
        fileReader.onloadend = function (upload) {
            var data = upload.target.result.split(',')[1];

            var $replyEl = $target.closest('.o_social_write_reply');
            var $imagePreview = $replyEl.find('.o_social_comment_image_preview');
            $imagePreview.removeClass('d-none');
            var fileType = FieldBinaryImage.prototype.file_type_magic_word[data[0]] || 'png';
            $imagePreview.find('img').attr('src', 'data:image/' + fileType + ';base64,' + data);

            $replyEl.find('textarea')
                .removeAttr('data-existing-attachment-id')
                .removeData('existingAttachmentId');
        };
    },

    /**
     * Removes the image preview when the user decides to remove it.
     *
     * @param {MouseEvent} ev
     */
    _onImageRemove: function (ev) {
        var $target = $(ev.currentTarget);
        var $replyEl = $target.closest('.o_social_write_reply');
        $replyEl.find('.o_social_comment_image_preview').addClass('d-none');
        $replyEl.find('.o_input_file').val('');
        $replyEl.find('textarea')
            .removeAttr('data-existing-attachment-id')
            .removeData('existingAttachmentId');
    },

    /**
     * Hides the comment element to replace it with a textarea.
     * That textarea is initialized with the comment value.
     *
     * We use the 'originalMessage' data since the displayed one is altered
     * by emoji wrapping.
     *
     * @param {MouseEvent} ev
     */
    _onEditComment: function (ev) {
        ev.preventDefault();

        var $targetComment = $(ev.currentTarget).closest('.o_social_comment');

        var $editComment = $(QWeb.render("social.StreamPostReply", {
            widget: this,
            comment: {
                id: $targetComment.data('commentId')
            },
            isCommentEdit: true,
            initialValue: $targetComment
                .find('.o_social_comment_text')
                .first()
                .data('originalMessage'),
            existingAttachmentId: $targetComment.data('existingAttachmentId'),
            existingAttachmentSrc: $targetComment.data('existingAttachmentSrc'),
        }));

        $targetComment.find('.o_social_comment_wrapper').first().hide();
        $targetComment.find('.o_social_comment_commands').first().hide();
        $targetComment.find('.o_social_comment_attachment').first().hide();
        $targetComment.prepend($editComment);

        dom.autoresize($editComment.find('textarea').first(), {
            parent: this,
            min_height: 60
        });
    },

    /**
     * Removes the textarea associated with the edition and shows the comment element again.
     *
     * @param {MouseEvent} ev
     */
    _onEditCommentCancel: function (ev) {
        ev.preventDefault();

        var $targetComment = $(ev.currentTarget).closest('.o_social_comment');
        $targetComment.find('.o_social_write_reply').first().remove();
        $targetComment.find('.o_social_comment_wrapper').first().show();
        $targetComment.find('.o_social_comment_commands').first().show();
        $targetComment.find('.o_social_comment_attachment').first().show();
    },

    /**
     * Shows a confirmation window that will handle the rpc call to delete the comment.
     * When the window throws a 'comment_deleted' event, we remove the comment element from the view.
     *
     * @param {MouseEvent} ev
     */
    _onDeleteComment: function (ev) {
        ev.preventDefault();
        var postDeleteWindow = new StreamPostCommentDelete(this, {
            postId: this.postId,
            commentName: this.commentName,
            deleteCommentEndpoint: this.getDeleteCommentEndpoint(),
            commentId: $(ev.currentTarget).closest('.o_social_comment').data('commentId')
        }).open();

        postDeleteWindow.on('comment_deleted', null, function () {
            $(ev.currentTarget).closest('.o_social_comment').remove();
        });
    },

    /**
     * Shows a textarea below the root comment.
     * The root comment is always the one that is under the main post.
     *
     * Any reply made to any comment is always linked to a single root comment.
     * In other words, there is only one sub-level of comments.
     *
     * - post
     *     - post comment 1 (considered 'root comment')
     *          - reply 1 to post comment 1
     *          - reply 2 to post comment 1
     *          - reply 3 to reply 1
     *          - reply 4 to reply 3
     *     - post comment 2 (considered 'root comment')
     *          - reply 4 to post comment 2
     *
     * @param {MouseEvent} ev
     */
    _onReplyComment: function (ev) {
        ev.preventDefault();

        var $target = $(ev.currentTarget);
        var $targetComment = $target.closest('.o_social_root_comment');
        var $textarea = $targetComment
            .find('.o_social_write_comment_reply')
            .removeClass('d-none')
            .find('textarea')
            .focus();

        $textarea.focus();

        dom.autoresize($textarea, {
            parent: this,
            min_height: 60
        });
    },

    /**
     * Loads the comment replies under the comment itself.
     *
     * When the user clicks on "Reply" on the root comment or on "Reply" on a reply comment,
     * the reply will actually always be on the root comment.
     *
     * There is only 1 sublevel of replies (see '_onReplyComment').
     *
     * @param {MouseEvent} ev
     */
    _onLoadReplies: function (ev) {
        ev.preventDefault();

        var self = this;
        var $target = $(ev.currentTarget);
        var innerComments = $target.data('innerComments');
        var $commentsRepliesContainer = $target.closest('.o_social_comment')
            .find('.o_social_comment_replies');

        innerComments.forEach(function (innerComment) {
            var $innerComment = $(QWeb.render("social.StreamPostComment", {
                widget: self,
                isSubComment: true,
                comment: innerComment
            }));

            $commentsRepliesContainer.append($innerComment);
        });
        $commentsRepliesContainer.removeClass('d-none');
        $target.remove();
    },

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
                'images': this.originalPost.postImages
            }
        ).open();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Method that is responsible of either adding a comment or edit an existing one.
     *
     * It will both:
     * - send the rpc request to reflect that change on the related social media
     * - visually update the view so that the user sees his action
     *
     * The rpc endpoint will return the added comment (or the new version of the edited one)
     * so that it can be added (or replace the edited one) in the view as a new element
     * using the 'social.StreamPostComment' template.
     *
     * The target $textarea will be disabled while the rpc is running.
     *
     * Edge case: If you're editing a root comment for which you already have loaded replies,
     * they will have to be loaded again after the edit takes place.
     *
     * @param {$.Element} $textarea The target textarea containing the added comment
     * @param {Boolean} isCommentReply Flag indicating is it's a reply to a comment
     *   If not, it's considered as a standard post comment.
     * @param {String} [commentId] The comment id that this comment targets.
     *   This is necessary when replying to a comment or edition a comment reply.
     * @param {Boolean} isEdit Flags that indicates this is editing a existing comment.
     */
    _addComment: function ($textarea, isCommentReply, commentId, isEdit) {
        var self = this;

        var $replyEl = $textarea.closest('.o_social_write_reply');
        var formData = new FormData($replyEl.find('form').first()[0]);

        formData.append('csrf_token', odoo.csrf_token);
        formData.append('post_id', this.postId);
        if (isEdit) {
            formData.append('is_edit', isEdit);
        }
        if (isCommentReply || isEdit) {
            formData.append('comment_id', commentId);
        }
        $textarea.prop('disabled', true);
        var existingAttachmentId = $textarea.data('existingAttachmentId');
        if (existingAttachmentId) {
            formData.append('existing_attachment_id', existingAttachmentId);
        }

        this._ajaxRequest(this.getAddCommentEndpoint(), {
            data: formData,
            processData: false,
            contentType: false,
            type: 'POST'
        }).then(function (comment) {
            comment = JSON.parse(comment);
            var $newMessage = $(QWeb.render("social.StreamPostComment", {
                widget: self,
                comment: comment,
                isSubComment: isCommentReply
            }));

            if (isCommentReply) {
                self._addCommentReply($textarea, $newMessage);
            } else if (isEdit) {
                var $targetComment = $textarea.closest('.o_social_comment');
                $targetComment.after($newMessage);
                $targetComment.remove();
            } else {
                self.$('.o_social_comments_messages').prepend($newMessage);
            }

            $textarea.val('');
            $replyEl.find('.o_social_comment_image_preview').addClass('d-none');
            $replyEl.find('.o_input_file').val('');
            $textarea.prop('disabled', false);
            $textarea.focus();
        });
    },

    /**
     * This exposes $.ajax in order to be easily mocked when testing.
     *
     * @param {String} endpoint
     * @param {Object} params
     */
    _ajaxRequest: function (endpoint, params) {
        return $.ajax(endpoint, params);
    },

    /**
     * Adapted from qweb2.js#html_escape to avoid formatting '&'
     *
     * @param {String} s
     * @private
     */
    _htmlEscape: function (s) {
        if (s == null) {
            return '';
        }
        return String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },

    /**
     * This method adds the new reply under any existing reply.
     * 2 cases:
     *
     * 1. There are existing replies that are not loaded yet:
     * We first need to load those to put our new reply after them
     *
     * 2. This is the first reply or replies are already loaded:
     * We add the reply to the replies container and show it
     *
     * @param {$.Element} $textarea The textarea originating the new reply
     * @param {$.Element} $newMessage The new reply to be appended to existing ones
     */
    _addCommentReply: function ($textarea, $newMessage) {
        var $repliesContainer = $textarea.closest('.o_social_root_comment')
            .find('.o_social_comment_replies');

        var $loadReplies = $textarea.closest('.o_social_root_comment')
            .find('.o_social_comment_load_replies');
        if ($loadReplies.length !== 0){
            $loadReplies.click();
        } else {
            $repliesContainer.removeClass('d-none');
        }

        $repliesContainer.append($newMessage);
    },

    /**
     * Updates the $target text based on the fact that the user has already liked
     * (subtract one) or not (add one). The information lies in the userLikes data.
     *
     * Exceptions:
     * - We don't display '0', we hide the text instead
     * - If the count is 0 and we subtract 1 (it can happen with Facebook's 'reactions'), keep 0
     *
     * @param {$.Element} $target
     */
    _updateLikesCount: function ($target) {
        var userLikes = $target.data('userLikes');
        $target.data('userLikes', !userLikes);

        var $likesTotal = $target
            .closest('.o_social_comment')
            .find('.o_social_comment_likes_total').eq(0);

        var likesCount = $likesTotal.find('.o_social_likes_count').text();
        likesCount = likesCount === '' ? 0 : parseInt(likesCount);

        if (userLikes) {
            if (likesCount > 0) {
                likesCount--;
            }
        } else {
            likesCount++;
        }

        $likesTotal.find('.o_social_likes_count').text(likesCount);

        if (likesCount === 0){
            $likesTotal.addClass('d-none');
        } else {
            $likesTotal.removeClass('d-none');
        }
    },

    _formatDateTime: function (date) {
        return moment(date).format(DATE_TIME_FORMAT);
    },

    /**
     * We want both emojis capabilities of _formatText
     * and various wrapping of _formatStreamPost
     *
     * @param {String} message
     * @private
     */
    _formatCommentStreamPost: function (message) {
        var formattedMessage = message;
        formattedMessage = this._formatText(formattedMessage);
        formattedMessage = this._formatStreamPost(formattedMessage);
        return formattedMessage;
    },

    _getTargetTextArea($emoji) {
        return $emoji.closest('.o_social_write_reply').find('textarea');
    }
});

return StreamPostComments;

});
