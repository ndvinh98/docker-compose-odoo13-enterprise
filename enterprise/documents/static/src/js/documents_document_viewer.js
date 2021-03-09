odoo.define('documents.DocumentViewer', function (require) {
"use strict";

var DocumentViewer = require('mail.DocumentViewer');

/**
 * This file defines the DocumentViewer for the Documents Kanban view.
 */
var DocumentsDocumentViewer = DocumentViewer.extend({
    template: "DocumentsDocumentViewer",
    events: _.extend({}, DocumentViewer.prototype.events, {
        'click .o_documents_split_btn': '_onSplitPDF',
    }),

    /**
     * @override
     * This override changes the value of modelName used as a parameter
     * for download routes (web/image, web/content,...)
     *
     */
    init: function (parent, attachments, activeAttachmentID) {
        this._super.apply(this, arguments);
        this.modelName = 'documents.document';
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} e
     */
    _onSplitPDF: function (e) {
        e.stopPropagation();
        var self = this;
        var indices = this.$(".o_documents_page_number_input").val();
        var remainder = this.$(".o_documents_remainder_input").is(":checked");
        var always = function () {
            self.trigger_up('document_viewer_attachment_changed');
            self.destroy();
        };
        this._rpc({
            model: 'documents.document',
            method: 'split_pdf',
            args: [this.activeAttachment.id, indices, remainder],
        }).then(always).guardedCatch(always);
    },

});

return DocumentsDocumentViewer;

});
