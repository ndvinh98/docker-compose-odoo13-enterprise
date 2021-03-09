odoo.define('account_yodlee.acc_config_widget', function(require) {
"use strict";

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');

var QWeb = core.qweb;


var YodleeAccountConfigurationWidget = AbstractAction.extend({
    template: 'YodleeTemplate',

    init: function(parent, context) {
        this._super(parent, context);
        this.userToken = context.userToken;
        this.fastlinkUrl = context.fastlinkUrl;
        this.accessTokens = context.accessTokens;
        this.beta = context.beta;
        this.state = context.state;
        this.callbackUrl = context.paramsUrl +
            document.location.protocol + '//' + document.location.host + context.callbackUrl;
    },

    renderButtons: function($node) {
        var self = this;
        if (this.userToken !== undefined) {
            this.$buttons = $(QWeb.render("YodleeTemplateFooter", {'widget': this}));
            this.$buttons.find('.js_yodlee_continue').click(function (e) {
                self.$('#yodleeForm').submit();
            });
            this.$buttons.appendTo($node);
        }
    },

});

var YodleeCallbackWidget = AbstractAction.extend({
    init: function(parent, context) {
        this._super(parent, context);
    },

    willStart: function() {
        var self = this;
        var paramsUrl = $.bbq.getState();
        self.method = paramsUrl.state;
        var def = this._rpc({
            model: 'account.online.provider',
            method: 'callback_institution',
            args: [[], paramsUrl.provider_identifier, paramsUrl.state, paramsUrl.journal_id]
        }).then(function (result) {
            self.do_action(result);
            // self.result = result;
        });
        return Promise.all([this._super.apply(this, arguments), def]);
    },

});

core.action_registry.add('yodlee_online_sync_widget', YodleeAccountConfigurationWidget);
core.action_registry.add('yodlee_callback_widget', YodleeCallbackWidget);

});
