odoo.define('web_mobile.notification_manager', function (require) {
"use strict";

var NotificationService = require('web.NotificationService');
var mobile = require('web_mobile.rpc');

NotificationService.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    notify: function () {
        if (mobile.methods.vibrate) {
            mobile.methods.vibrate({'duration': 100});
        }
        return this._super.apply(this, arguments);
    },
});

});
