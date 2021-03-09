odoo.define('mail_enterprise.form_renderer', function (require) {
"use strict";

var config = require('web.config');
var dom = require('web.dom');
var pyUtils = require('web.py_utils');
var FormRenderer = require('web.FormRenderer');
var AttachmentViewer = require('mail_enterprise.AttachmentViewer');

/**
 * Display attachment preview on side of form view for large screen devices.
 *
 * To use this simply add div with class o_attachment_preview in format
 *     <div class="o_attachment_preview"/>
 *
 * Some options can be passed to change its behavior:
 *     types: ['image', 'pdf']
 *     order: 'asc' or 'desc'
 *
 * For example, if you want to display only pdf type attachment and the latest
 * one then use:
 *     <div class="o_attachment_preview" options="{'types': ['pdf'], 'order': 'desc'}"/>
**/

FormRenderer.include({
    custom_events: _.extend({}, FormRenderer.prototype.custom_events, {
        preview_attachment: '_onAttachmentPreview'
    }),

    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);

        this.$attachmentPreview = undefined;
        this.attachmentPreviewResID = undefined;
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Interchange the position of the chatter and the attachment preview.
     *
     * @private
     * @param {boolean} enablePreview
     */
    _interchangeChatter: function (enablePreview) {
        if (config.device.size_class < config.device.SIZES.XXL) {
            return;
        }
        if (!this.$attachmentPreview) {
            return;
        }
        var $sheet = this.$('.o_form_sheet_bg');

        if (enablePreview) {
            this.$attachmentPreview.insertAfter($sheet);
            dom.append($sheet, this.chatter.$el, {
                callbacks: [{ widget: this.chatter }],
                in_DOM: this._isInDom,
            });
        } else {
            this.chatter.$el.insertAfter($sheet);
            dom.append($sheet, this.$attachmentPreview, {
                callbacks: [],
                in_DOM: this._isInDom,
            });
        }
    },
    /**
     * Overrides the function that renders the nodes to return the preview's $el
     * for the `o_attachment_preview` div node.
     *
     * @private
     * @override
     */
    _renderNode: function (node) {
        if (node.tag === 'div' && node.attrs.class === 'o_attachment_preview') {
            if (this.attachmentViewer) {
                if (this.attachmentPreviewResID !== this.state.res_id) {
                    this.attachmentViewer.destroy();
                    this.attachmentViewer = undefined;
                }
            } else {
                this.$attachmentPreview = $('<div>', {class: 'o_attachment_preview'});
            }
            this._handleAttributes(this.$attachmentPreview, node);
            this._registerModifiers(node, this.state, this.$attachmentPreview);
            if (node.attrs.options) {
                this.$attachmentPreview.data(pyUtils.py_eval(node.attrs.options));
            }
            if (this.attachmentPreviewWidth) {
                this.$attachmentPreview.css('width', this.attachmentPreviewWidth);
            }
            return this.$attachmentPreview;
        } else {
            return this._super.apply(this, arguments);
        }
    },
    /**
     * Overrides the function to interchange the chatter and the preview once
     * the chatter is in the dom.
     *
     * @private
     * @override
     */
    _renderView: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            // for cached messages, `preview_attachment` will be triggered
            // before the view rendering where the chatter is replaced ; in this
            // case, we need to interchange its position if needed
            var enablePreview = self.attachmentPreviewResID &&
                self.attachmentPreviewResID === self.state.res_id &&
                self.$attachmentPreview &&
                !self.$attachmentPreview.hasClass('o_invisible_modifier');
            self._interchangeChatter(enablePreview);
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Triggered from the mail chatter, send attachments data for preview
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onAttachmentPreview: function (ev) {
        if (config.device.size_class < config.device.SIZES.XXL) {
            return;
        }
        if (!this.$attachmentPreview) {
            return;
        }
        var self = this;
        var options = _.defaults(this.$attachmentPreview.data(), {
            types: ['pdf', 'image'],
            order: 'asc'
        });
        var attachments = $.extend(true, {}, ev.data.attachments);  // clone array
        attachments = _.filter(attachments, function (attachment) {
            var match = attachment.mimetype.match(options.types.join('|'));
            attachment.type = match ? match[0] : false;
            return match;
        });
        if (options.order === 'desc') {
            attachments.reverse();
        }
        if (attachments.length || this.attachmentViewer) {
            if (this.attachmentViewer) {
                if (this.attachmentViewer.attachments.length !== attachments.length) {
                    if (!attachments.length) {
                        this.attachmentViewer.destroy();
                        this.attachmentViewer = undefined;
                        this.attachmentPreviewResID = undefined;
                        this._interchangeChatter(false);
                    }
                    else {
                        this.attachmentViewer.updateContents(attachments, options.order);
                    }
                }
                this.trigger_up('preview_attachment_validation');
            } else {
                this.attachmentPreviewResID = this.state.res_id;
                this.attachmentViewer = new AttachmentViewer(this, attachments);
                this.attachmentViewer.appendTo(this.$attachmentPreview).then(function() {
                    self.trigger_up('preview_attachment_validation');
                    self.$attachmentPreview.resizable({
                        handles: 'w',
                        minWidth: 400,
                        maxWidth: 900,
                        resize: function (event, ui) {
                            self.attachmentPreviewWidth = ui.size.width;
                        },
                    });
                    self._interchangeChatter(!self.$attachmentPreview.hasClass('o_invisible_modifier'));
                });
            }
        }
    },

});

});
