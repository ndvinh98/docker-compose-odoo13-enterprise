odoo.define('social.social_post_kanban_add_stream_modal', function (require) {
"use strict";

var core = require('web.core');
var Dialog = require('web.Dialog');
var _t = core._t;

/**
 * Simple Dialog extension to customize the addition of streams and allow to connect new accounts.
 */
var AddStreamModal = Dialog.extend({
    template: 'social.AddStreamModal',
    events: _.extend({}, Dialog.prototype.events, {
        'click .o_social_account_card': '_onClickSocialAccount',
        'click .o_social_media': '_onClickSocialMedia',
    }),

    /**
     * @override
     */
    init: function (parent, options) {
        options = _.defaults(options || {}, {
            title: _t('Add a Stream'),
            size: 'medium',
            renderFooter: false,
        });

        this.isSocialManager = options.isSocialManager;
        this.socialMedia = options.socialMedia;
        this.socialAccounts = options.socialAccounts;

        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Triggers 'new_stream_account_clicked' to be caught by parent.
     *
     * @param {MouseEvent} ev
     * @private
     */
    _onClickSocialAccount: function (ev) {
        var $target = $(ev.currentTarget);
        this.trigger_up('new_stream_account_clicked', {
            mediaId: $target.data('mediaId'),
            accountId: $target.data('accountId')
        });
        this.close();
    },

    /**
     * Triggers 'new_stream_media_clicked' to be caught by parent.
     *
     * @param {MouseEvent} ev
     * @private
     */
    _onClickSocialMedia: function (ev) {
        var mediaId = $(ev.currentTarget).data('mediaId');
        this.trigger_up('new_stream_media_clicked', {'mediaId': mediaId});
    }
});

return AddStreamModal;

});
