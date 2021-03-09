odoo.define('voip.WebClient', function (require) {
"use strict";

const DialingPanel = require('voip.DialingPanel');

const config = require('web.config');
const WebClient = require('web.WebClient');

// As voip is not supported on mobile devices,
// we want to keep the standard phone widget
if (config.device.isMobile) {
    return;
}

WebClient.include({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    async show_application() {
        await this._super(...arguments);
        this._dialingPanel = new DialingPanel(this);
        await this._dialingPanel.appendTo(this.$el);
        this.on('voip_call', this, this.proxy('_onVoipCall'));
        this.on('voip_activity_call', this, this.proxy('_onVoipActivityCall'));
        this.on('get_pbx_configuration', this, this.proxy('_onGetPbxConfiguration'));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @param {OdooEvent} ev
     * @param {function} ev.data.callback
     */
    _onGetPbxConfiguration(ev) {
        ev.data.callback({
            pbxConfiguration: this._dialingPanel.getPbxConfiguration(),
        });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {string} ev.data.number
     * @param {integer} ev.data.activityId
     */
    _onVoipActivityCall(ev) {
        return this._dialingPanel.callFromActivityWidget(ev.data);
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {string} ev.data.number
     * @param {string} ev.data.resModel
     * @param {integer} ev.data.resId
     */
    _onVoipCall(ev) {
        return this._dialingPanel.callFromPhoneWidget(ev.data);
    },
});

});
