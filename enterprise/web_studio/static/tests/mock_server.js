odoo.define('web_studio.MockServer', function (require) {
'use strict';

var MockServer = require('web.MockServer');

MockServer.include({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     * @returns {Promise}
     */
    _performRpc: function (route) {
        if (route === '/web_studio/get_default_value') {
            return Promise.resolve({});
        }
        if (route === '/web_studio/activity_allowed') {
            return Promise.resolve(false);
        }
        return this._super.apply(this, arguments);
    },
});

});
