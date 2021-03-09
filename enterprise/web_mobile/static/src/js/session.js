odoo.define('web_mobile.session', function (require) {
"use strict";

var core = require('web.core');
var session = require('web.Session');

var mobile = require('web_mobile.rpc');

/*
    Android webview not supporting post download and odoo is using post method to download
    so here override get_file of session and passed all data to native mobile downloader
    ISSUE: https://code.google.com/p/android/issues/detail?id=1780
*/

session.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    get_file: function (options) {
        if (mobile.methods.downloadFile) {
            if (core.csrf_token) {
                options.csrf_token = core.csrf_token;
            }
            mobile.methods.downloadFile(options);
            // There is no need to wait downloadFile because we delegate this to
            // Download Manager Service where error handling will be handled correclty.
            // On our side, we do not want to block the UI and consider the request
            // as success.
            if (options.success) { options.success(); }
            if (options.complete) { options.complete(); }
            return true;
        } else {
            return this._super.apply(this, arguments);
        }
    },
});

});
