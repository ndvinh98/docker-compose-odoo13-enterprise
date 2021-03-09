odoo.define('web_studio.IconCreator', function (require) {
"use strict";

var core = require('web.core');
var session = require('web.session');
var Widget = require('web.Widget');

var utils = require('web_studio.utils');

var QWeb = core.qweb;

var IconCreator = Widget.extend({
    template: 'web_studio.IconCreator',
    events: {
        'click .o_web_studio_selector': '_onSelector',
        'click .js_upload': '_onUploadButton',
        'click .js_discard_upload': '_onUploadDiscarded',
    },
    /**
     * @constructor
     * @param {widget} parent
     * @param {Object} [options]
     * @param {string} [options.color]
     * @param {string} [options.background_color]
     * @param {string} [options.icon_class]
     */
    init: function (parent, options) {
        this.COLORS = utils.COLORS;
        this.BG_COLORS = utils.BG_COLORS;
        this.ICONS = utils.ICONS;

        options = options || {};

        this.color = options.color || this.COLORS[4];
        this.background_color = options.background_color ||  this.BG_COLORS[5];
        this.icon_class = options.icon_class || this.ICONS[0];


        this.PALETTE_TEMPLATES = {
            'color':            'web_studio.IconCreator.IconColorPalette',
            'background_color': 'web_studio.IconCreator.BgPalette',
            'icon':             'web_studio.IconCreator.IconPalette',
        };

        // Upload related stuff
        this.uploaded_image = options.webIconData;
        this.uploaded = !!options.webIconData;
        this.uploaded_attachment_id = false;
        this.image_only = true;
        this.user_id = session.uid;
        this.fileupload_id = _.uniqueId('o_fileupload');
        $(window).on(this.fileupload_id, this._onUploadDone.bind(this));

        this.mode = 'edit';
        this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    start: function () {
        this.update(true);
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    destroy: function () {
        $(window).off(this.fileupload_id);
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {Integer|Array} the icon value, which could either be:
     *  - the ir.attachment id of the uploaded image
     *  - if the icon has been created, an array containing
     *      [icon_class, color, background_color]
     */
    getValue: function () {
        if (this.uploaded) {
            return this.uploaded_attachment_id;
        } else {
            return [this.icon_class, this.color, this.background_color];
        }
    },
    /**
     * Render the widget in edit mode.
     */
    enableEdit: function () {
        this.mode = 'edit';
        this.renderElement();
    },
    /**
     * Render the widget in readonly mode.
     */
    disableEdit: function () {
        this.mode = 'readonly';
        this.renderElement();
    },
    /**
     * @param {Boolean} replace_icon
     */
    update: function (replace_icon) {
        var self = this;
        this.$('.o_app_icon').css('background-color', this.background_color)
                             .find('i').css('color', this.color);

        if (replace_icon) {
            this.$('.o_app_icon i').fadeOut(50, function () {
                $(this).attr('class', self.icon_class).fadeIn(800);
            });
        }

        this.$('.o_web_studio_selector[data-type="icon"] i').attr(
            'class', self.icon_class
        );
        this.$('.o_web_studio_selector[data-type="background_color"]').css(
            'background-color', this.background_color
        );
        this.$('.o_web_studio_selector[data-type="color"]').css(
            'background-color', this.color
        );
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    _onSelector: function (ev) {
        var self = this;
        var $el = $(ev.currentTarget);
        var selector_type = $el.data('type');

        if (!selector_type) { return; }
        if (this.$palette) { this.$palette.remove(); }

        this.$palette = $(QWeb.render(this.PALETTE_TEMPLATES[selector_type], {
            widget: this,
        }));
        $el
            .find('.o_web_studio_selector_pointer')
            .before(this.$palette);
        this.$palette.on('mouseleave', function () {
            $(this).remove();
        });
        this.$palette.find('.o_web_studio_selector').click(function (ev) {
            $el = $(ev.currentTarget);
            if (selector_type === 'background_color') {
                self.background_color = $el.data('color');
                self.update();
            } else if (selector_type === 'color') {
                self.color = $el.data('color');
                self.update();
            } else {
                self.icon_class = $el.children('i').attr('class');
                self.update(true);
            }
        });
    },
    /**
     * @private
     * @param {Event} event
     */
    _onUploadButton: function (event) {
        event.preventDefault();

        var self = this;
        this.$('input.o_input_file').on('change', function () {
            self.$('form.o_form_binary_form').submit();
        });
        this.$('input.o_input_file').click();

    },
    /**
     * @private
     * @param {Event} event
     * @param {Object} result
     */
    _onUploadDone: function (event, result) {
        event.preventDefault();

        this.uploaded = true;
        this.uploaded_attachment_id = result.id;

        var self = this;
        this._rpc({
                model: 'ir.attachment',
                method: 'read',
                args: [[this.uploaded_attachment_id], ['datas']],
            })
            .then(function (res) {
                var base64 = res[0].datas.replace(/\s/g, '');
                self.uploaded_image = 'data:image/png;base64,' + base64;
                self.renderElement();
            });
    },
    /**
     * @private
     * @param {Event} event
     */
    _onUploadDiscarded: function (event) {
        event.preventDefault();

        this.uploaded = false;
        this.uploaded_attachment_id = false;
        this.renderElement();
        this.update(true);
    },
});

return IconCreator;

});
