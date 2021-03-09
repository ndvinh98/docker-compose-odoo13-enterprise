odoo.define('account_ponto.acc_config_widget', function(require) {
"use strict";

var ajax = require('web.ajax');
var core = require('web.core');
var _t = core._t;
var AbstractAction = require('web.AbstractAction');

var QWeb = core.qweb;

var PontoAccountConfigurationWidget = AbstractAction.extend({
    template: 'PontoTemplate',

    init: function(parent, context) {
        this._super(parent, context);
        this.create = context.context.method === 'add';
        this.context = context.context;
        this.record_id = context.record_id && [context.record_id] || [];
    },

    renderButtons: function($node) {
        var self = this;
        this.$buttons = $(QWeb.render("PontoTemplateFooter", {'widget': this}));
        this.$buttons.find('.js_ponto_continue').click(function (e) {
            var client_id = $('.client_id').val()
            var secret_id = $('.secret_id').val()
            if (client_id && secret_id) {
                var credentials_to_encode = client_id + ':' + secret_id;
                self._rpc({
                    model: 'account.online.provider',
                    method: 'success_callback',
                    args: [self.record_id, credentials_to_encode],
                    context: self.context,
                }).then(function (result) {
                    self.do_action(result);
                });
            }
        });
        this.$buttons.find('.js_cancel').click(function(e) {
            self.do_action({type: 'ir.actions.act_window_close'});
        });
        this.$buttons.appendTo($node);
    },

});

core.action_registry.add('ponto_online_sync_widget', PontoAccountConfigurationWidget);

});
