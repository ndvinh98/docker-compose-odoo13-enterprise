odoo.define('voip.CallCenterField', function (require) {
"use strict";

const AbstractField = require('web.AbstractField');
const core = require('web.core');
const fieldRegistry = require('web.field_registry');

const _t = core._t;

const CallCenterField = AbstractField.extend({
    template: 'voip.CallCenterField',
    events: Object.assign({}, AbstractField.prototype.events, {
        'click': '_onClick',
    }),

    /**
     * @override
     */
    init() {
        this._super(...arguments);
        core.bus.on('voip_widget_refresh', this, this._onVoipRefresh);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Returns the helper
     *
     * @return {string}
     */
    getHelper() {
        return this.isInCallQueue() ?
            _t("Remove from Call Queue") :
            _t("Add to Call Queue");
    },
    /**
     * Returns if record has call in queue
     *
     * @return {boolean}
     */
    isInCallQueue() {
        return this.value;
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    async _onClick() {
        await this._rpc({
            model: this.model,
            method: this.isInCallQueue()
                ? 'delete_call_in_queue'
                : 'create_call_in_queue',
            args: [this.res_id],
        });
        this.trigger_up('reload');
    },
    /**
     * @private
     * @param {integer} resID
     */
    _onVoipRefresh(resID) {
        if (resID !== this.res_id) {
            return;
        }
        this.trigger_up('reload');
    },
});

fieldRegistry.add('call_center', CallCenterField);

});
