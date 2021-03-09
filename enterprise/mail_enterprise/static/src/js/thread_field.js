odoo.define('mail_enterprise.ThreadField', function (require) {
"use strict";

var ThreadField = require('mail.ThreadField');

ThreadField.include({

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
    * Override the thread rendering to warn the FormRenderer about attachments.
    * This is used by the FormRenderer to display an attachment preview.
    *
    * @override
    * @private
    */
    _fetchAndRenderThread: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self.trigger_up('preview_attachment', {
                attachments: self._threadWidget.attachments,
            });
        });
    },
});

var Chatter = require('mail.Chatter');

Chatter.include({
    custom_events: _.extend({}, Chatter.prototype.custom_events, {
        preview_attachment: '_onAttachmentPreview',
    }),

    /**
     * @private
     * @param {OdooEvent} ev
     */
    _onAttachmentPreview: function (ev) {
        var newInterceptedAttachmentIDs = _.difference(
            _.pluck(ev.data.attachments, 'id'),
            _.pluck(this.attachments, 'id')
        );
        if (newInterceptedAttachmentIDs.length > 0) {
            this._areAttachmentsLoaded = false;
        }
        if (this._areAttachmentsLoaded) {
            if (this.record.data.message_main_attachment_id !== undefined) {
                var mainID = (this.record.data.message_main_attachment_id || {}).res_id;
                _.each(this.attachments, function (attachment) {
                    attachment.is_main = attachment.id == mainID;
                });
            }
            ev.data.attachments = this.attachments;
        } else {
            ev.stopPropagation();
            return this._fetchAttachments().then(this.trigger_up.bind(this, 'preview_attachment'));
        }
    },
    /**
     * @override
     * @private
     */
    _onReloadAttachmentBox: function () {
        this._super.apply(this, arguments);
        this.trigger_up('preview_attachment');
    },
});
});
