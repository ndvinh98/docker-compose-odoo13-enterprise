odoo.define('mail_enterprise.AttachmentViewer', function (require) {
"use strict";

var core = require('web.core');
var Widget = require('web.Widget');

var QWeb = core.qweb;

var AttachmentViewer = Widget.extend({
    className: 'o_attachment_preview_container',
    events: {
        'click .arrow.o_move_next': '_onClickNext',
        'click .arrow.o_move_previous': '_onClickPrevious',
    },
    /**
     * The AttachmentViewer takes an array of objects describing attachments in
     * argument and first attachment of the array is display first.
     *
     * @constructor
     * @override
     * @param {Widget} parent
     * @param {Array<Object>} attachments list of attachments
     */
    init: function (parent, attachments) {
        this._super.apply(this, arguments);
        this.attachments = attachments;
        this._setActive();
    },
    /**
     * Render attachment.
     *
     * @override
     */
    start: function () {
        this._renderAttachment();
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Update attachments list and activeAttachment.
     *
     * @param {Array<Object>} attachments list of attachments
     * @param {string} order
     */
    updateContents: function (attachments, order) {
        this.attachments = attachments;
        this._setActive();
        this._renderAttachment();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Render template
     *
     * @private
     */
    _renderAttachment: function () {
        this.$el.empty();
        this.$el.append(QWeb.render('mail_enterprise.AttachmentPreview', {widget: this}));
    },

    /**
     * @private
     */
    _setActive: function () {
        this.activeAttachment = _.find(this.attachments, function (attachment) {
            return attachment.is_main;
        });
        if (!this.activeAttachment && this.attachments.length) {
            this.activeAttachment = this.attachments[0];
            this._rpc({
                model: 'ir.attachment',
                method: 'register_as_main_attachment',
                args: [[this.activeAttachment.id], this.activeAttachment.is_main === false],
            });
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    /**
    * Sets the attachment at position index as the new main attachment of
    * the related model, and display it.
    **/
    _switch_main_attachment: function (index) {
        var self = this;
        this.activeAttachment = this.attachments[index];
        this._rpc({
            model: 'ir.attachment',
            method: 'register_as_main_attachment',
            args: [[this.activeAttachment['id']]],
        }).then(
            function() {
                self._renderAttachment();
            }
        );
    },

    /**
     * On click move to next attachment.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickNext: function (ev) {
        ev.preventDefault();
        var index = _.findIndex(this.attachments, this.activeAttachment);
        index = index === this.attachments.length -1 ? 0 : index + 1;
        this._switch_main_attachment(index);
    },
    /**
     * On click move to previous attachment.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickPrevious: function (ev) {
        ev.preventDefault();
        var index = _.findIndex(this.attachments, this.activeAttachment);
        index = index === 0 ? this.attachments.length - 1 : index - 1;
        this._switch_main_attachment(index);
    },
});

return AttachmentViewer;
});
