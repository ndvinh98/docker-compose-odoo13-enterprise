odoo.define('social.kanban_field_stream_post', function (require) {
"use strict";

var FieldRegistry = require('web.field_registry');
var FieldText = require('web.basic_fields').FieldText;
var SocialEmojisMixin = require('social.emoji_mixin');
var SocialStreamPostFormatterMixin = require('social.stream_post_formatter_mixin');

var SocialKanbanMessageWrapper = FieldText.extend(SocialEmojisMixin, SocialStreamPostFormatterMixin, {
    /**
     * Overridden to wrap emojis and apply special stream post formatting
     *
     * @override
     */
    _render: function () {
        if (this.value) {
            var formattedValue = this.value;
            formattedValue = this._formatText(formattedValue);
            formattedValue = this._formatStreamPost(formattedValue);
            this.$el.html(formattedValue);
        }
    },
});

FieldRegistry.add('social_kanban_field_stream_post', SocialKanbanMessageWrapper);

return SocialKanbanMessageWrapper;

});
