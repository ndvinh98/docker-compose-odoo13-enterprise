odoo.define('web_mobile.CrashManager', function (require) {
"use strict";

var CrashManager = require('web.CrashManager').CrashManager;

var mobile = require('web_mobile.rpc');

CrashManager.include({
    /**
     * @override
     */
    rpc_error: function (error) {
        if (mobile.methods.crashManager) {
            mobile.methods.crashManager(error);
        }
        return this._super.apply(this, arguments);
    },
});

});
