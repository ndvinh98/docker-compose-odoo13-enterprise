odoo.define('social.users_autocomplete', function (require) {
'use strict';

var basic_fields = require('web.basic_fields');
var core = require('web.core');
var field_registry = require('web.field_registry');

var QWeb = core.qweb;

var FieldChar = basic_fields.FieldChar;

var TwitterUsersAutocomplete = FieldChar.extend({
    className: 'o_field_twitter_users_autocomplete',

    events: _.extend({}, FieldChar.prototype.events, {
        'click .o_twitter_users_autocomplete_suggestion': '_onSuggestionClicked',
    }),

    _renderEdit: function () {
        this._super.apply(this);
        var self = this;

        this.$input.autocomplete({
            classes: {'ui-autocomplete': 'o_social_twitter_users_autocomplete'},
            source: function (request, response) {
                var accountId = self.getParent().state.data.account_id.data.id;

                return self._rpc({
                    model: 'social.account',
                    method: 'twitter_search_users',
                    args: [[accountId], request.term],
                }).then(function (suggestions) {
                    response(suggestions);
                });
            },
            select: function (ev, ui) {
                self.$input.val(ui.item.name);
                self._selectTwitterUser(ui.item);
                ev.preventDefault();
            },
            html: true,
            minLength: 2,
            delay: 500,
        }).data('ui-autocomplete')._renderItem = function (ul, item){
            return $(QWeb.render('social_twitter.users_autocomplete_element', {
                suggestion: item
            })).appendTo(ul);
        };
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Object} twitterUser
     */
    _selectTwitterUser: function (twitterUser) {
        var self = this;

        this._rpc({
            model: 'social.twitter.account',
            method: 'create',
            args: [{
                name: twitterUser.name,
                twitter_id: twitterUser.id_str
            }]
        }).then(function (id) {
            self.trigger_up('field_changed', {
                dataPointID: self.dataPointID,
                changes: {
                    twitter_followed_account_id: { id: id }
                },
            });
        });
    }
});

field_registry.add('twitter_users_autocomplete', TwitterUsersAutocomplete);

return TwitterUsersAutocomplete;

});
