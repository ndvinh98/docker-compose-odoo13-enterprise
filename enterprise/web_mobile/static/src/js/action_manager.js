odoo.define('web_mobile.ActionManager', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');
var mobile = require('web_mobile.rpc');

/*
    We don't want to open website urls in the Odoo apps (iOS and Android).
    The apps detect the redirection and open the url in a seprate browser.

    In Odoo desktop, the redirection occurs in the same tab and the returned
    promise is never resolved.
    This override returns a resolved promise in case of mobile app redirects
    because Odoo is not aware of this and we need to reactivate status button.

    This behavior is the same as the one already done when opening the url in a new window.
*/
ActionManager.include({
    ir_actions_act_url: function (action) {
        var url = action.url;
        var result = this._super.apply(this, arguments);
        if (!_.isEmpty(mobile.methods) && !url.startsWith("/web")) {
            return Promise.resolve();
        }
        return result;
    },
});

});
