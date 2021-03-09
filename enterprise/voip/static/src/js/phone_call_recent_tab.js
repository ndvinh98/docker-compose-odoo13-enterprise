odoo.define('voip.PhoneCallRecentTab', function (require) {
"use strict";

const PhoneCallTab = require('voip.PhoneCallTab');

const PhoneCallRecentTab = PhoneCallTab.extend({

    /**
     * @override
     */
    init() {
        this._super(...arguments);
        this._searchExpr = undefined;
    },

    /**
     * @override
     */
    start() {
        this._bindScroll();
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Creates a new phonecall in the db and in the tab list based on a number.
     *
     * @param {string} number
     * @return {Promise<voip.PhoneCall>} resolved with phoneCall
     */
    async callFromNumber(number) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_number',
            args: [number],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        await this._selectPhoneCall(phoneCallId);
        return this._getCurrentPhoneCall();
    },
    /**
     * Function called when widget phone is clicked.
     *
     * @param {Object} param0
     * @param {string} param0.number
     * @param {integer} param0.resId
     * @param {string} param0.resModel
     * @return {Promise}
     */
    async callFromPhoneWidget({ number, resId, resModel }) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_phone_widget',
            args: [resModel, resId, number],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        return this._selectPhoneCall(phoneCallId);
    },
    /**
     * @override
     *
     * @param {voip.PhoneCall} [phoneCall] if given the function doesn't have
     *   to create a new phonecall
     * @return {Promise}
     */
    async initPhoneCall(phoneCall) {
        const _super = this._super.bind(this, ...arguments); // limitation of class.js
        if (!phoneCall) {
            const phoneCallData = await this._rpc({
                model: 'voip.phonecall',
                method: 'create_from_recent',
                args: [this._currentPhoneCallId],
            });
            const phoneCallId = await this._displayInQueue(phoneCallData);
            this._currentPhoneCallId = phoneCallId;
            await this._selectPhoneCall(phoneCallId);
        }
        return _super();
    },
    /**
     * @override
     * @return {Promise}
     */
    async refreshPhonecallsStatus() {
        this._isLazyLoadFinished = false;
        const phoneCallsData = await this._rpc({
            model: 'voip.phonecall',
            method: 'get_recent_list',
            args: [false, 0, 10],
        });
        this._parsePhoneCalls(phoneCallsData);
    },
    /**
     * @override
     * @return {Promise}
     */
    async searchPhoneCall(search) {
        if (search) {
            this._searchExpr = search;
            this._offset = 0;
            this._isLazyLoadFinished = false;
            const phoneCallsData = await this._rpc({
                model: 'voip.phonecall',
                method: 'get_recent_list',
                args: [search, this._offset, this._limit],
            });
            return this._parsePhoneCalls(phoneCallsData);
        } else {
            this._searchExpr = false;
            return this.refreshPhonecallsStatus();
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Gets the next phonecalls to display with the current offset
     *
     * @private
     * @return {Promise}
     */
    async _lazyLoadPhonecalls() {
        this._isLazyLoading = true;
        const search = this._searchExpr ? this._searchExpr : false;
        const phoneCallsData = await this._rpc({
            model: 'voip.phonecall',
            method: 'get_recent_list',
            args: [search, this._offset, this._limit],
        });
        if (!phoneCallsData.length) {
            this._isLazyLoadFinished = true;
        }
        const promises = phoneCallsData.map(phoneCallData =>
            this._displayInQueue(phoneCallData));
        await Promise.all(promises);
        this._computeScrollLimit();
        this._isLazyLoading = false;
    },
    /**
     * @override
     * @private
     * @param {Object[]} phoneCallsData
     */
    _parsePhoneCalls(phoneCallsData) {
        for (const phoneCallData of phoneCallsData) {
            phoneCallData.isRecent = true;
        }
        this._super(...arguments);
        this._computeScrollLimit();
    },
});

return PhoneCallRecentTab;

});
