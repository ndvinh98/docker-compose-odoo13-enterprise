odoo.define('social.form_field_emoji', function (require) {
"use strict";

var basicFields = require('web.basic_fields');
var core = require('web.core');
var emojis = require('mail.emojis');
var registry = require('web.field_registry');
var SocialEmojisMixin = require('social.emoji_mixin');
var _onEmojiClickMixin = SocialEmojisMixin._onEmojiClick;
var QWeb = core.qweb;

/**
 * Extension of the FieldText that will add:
 * - Emojis support
 * - Trigger 'change' on keydown to update various post preview
 */
var FieldTextEmojis = basicFields.FieldText.extend(SocialEmojisMixin, {
    /**
     * @override
     * @private
     */
    init: function () {
        this._super.apply(this, arguments);
        this._updatePreview =_.throttle(this._updatePreview, 1000, {leading: false});
        this.emojis = emojis;
    },

    /**
     * This will add an emoji button that shows the emojis selection dropdown.
     *
     * We use 'on_attach_callback' because we need the element to be attached to the form first.
     * That's because the $emojisIcon element needs to be rendered outside of this $el
     * (which is an textarea, that can't 'contain' any other elements).
     *
     * @override
     */
    on_attach_callback: function () {
        var self = this;

        if (!this.$emojisIcon) {
            this.$emojisIcon = $(QWeb.render(
                'social.EmojisDropdown', {
                    widget: this,
                    emojisDropdownId: 'emojis_dropdown'
                }
            ));
            this.$emojisIcon.find('.o_mail_emoji').on('click', function (ev) {
                self._onEmojiClick(ev);
                self._isDirty = true;
            });
            this.$el.after(this.$emojisIcon);
        }

        if (this.mode === 'edit') {
            this.$emojisIcon.show();
        } else {
            this.$emojisIcon.hide();
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _render: function () {
        this._super.apply(this, arguments);

        if (this.mode !== 'edit') {
            this.$el.html(this._formatText(this.$el.text()));
        }
    },

    /**
     * Overridden because we need to add the Emoji to the input AND trigger
     * the 'change' event to refresh the various post previews.
     *
     * @override
     * @private
     */
    _onEmojiClick: function () {
        _onEmojiClickMixin.apply(this, arguments);
        this.$input.trigger('change');
    },

    /**
     *
     * By default, the 'change' event is only triggered when the textarea is blurred.
     *
     * We override this method because we want to update the various post previews while
     * the user is typing his message (and not only on blur).
     *
     * @override
     * @private
     */
    _onKeydown: function () {
        this._super.apply(this, arguments);
        this._updatePreview();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Used by SocialEmojisMixin, check its document for more info.
     *
     * @param {$.Element} $emoji
     * @private
     */
    _getTargetTextArea($emoji) {
        return $emoji.closest('td').find('textarea');
    },

    /**
     * Triggers the 'change' event to refresh the various post previews.
     * This method is throttled to run at most once every second.
     * (to avoid spamming the server while the user is typing his message)
     *
     * @private
     */
    _updatePreview: function () {
        this.$input.trigger('change');
    }
});

registry.add('social_text_emojis', FieldTextEmojis);

return FieldTextEmojis;

});
