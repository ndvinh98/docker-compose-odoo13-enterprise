odoo.define('voip.PhoneCallTab', function (require) {
"use strict";

const PhoneCall = require('voip.PhoneCall');
const PhoneCallDetails = require('voip.PhoneCallDetails');

const core = require('web.core');
const fieldUtils = require('web.field_utils');
const Widget = require('web.Widget');

const PhoneCallTab = Widget.extend({
    template: 'voip.PhoneCallTab',
    custom_events: {
        cancelActivity: '_onCancelActivity',
        clickedOnNumber: '_onClickedOnNumber',
        closePhonecallDetails: '_onClosePhonecallDetails',
        markActivityDone: '_onMarkActivityDone',
        removePhoneCall: '_onRemovePhoneCall',
        selectCall: '_onSelectCall',
    },
    /**
     * @constructor
     */
    init() {
        this._super(...arguments);
        this._currentPhoneCallId = null;
        this._isLazyLoadFinished = false;
        this._isLazyLoading = false;
        this._limit = 10;
        this._maxScrollHeight = undefined;
        this._offset = 0;
        this._phoneCalls = [];
        this._phoneCallDetails = undefined;
        this._scrollLimit = undefined;
        this._selectedPhoneCallId = null;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * When the user clicks on the call button and the details are displayed,
     * the first number is called.
     */
    async callFirstNumber() {
        const selectedPhoneCall = await this._getPhoneCall(this._selectedPhoneCallId);
        const number = selectedPhoneCall.phoneNumber || selectedPhoneCall.mobileNumber;
        if (number) {
            this._currentPhoneCallId = this._selectedPhoneCallId;
            this.trigger_up('callNumber', { number });
        }
    },
    /**
     * When the user clicks on the call button when on a tab, without details open
     * Forces a switch to the keypad in the parent panel.
     *
     * @return {Promise}
     */
    async callFromTab() {
        this.trigger_up('switch_keypad');
    },
    /**
     * change message in widget to ringing
     */
    changeRinging() {
        this._phoneCallDetails.setStatusRinging();
    },
    /**
     * Triggers the hangup process then refreshes the tab.
     *
     * @param {boolean} isDone
     * @return {Promise}
     */
    async hangupPhonecall(isDone) {
        const currentPhoneCall = this._getCurrentPhoneCall();
        await currentPhoneCall.hangUp({
            durationSeconds: this._phoneCallDetails.durationSeconds,
            isDone,
        });
        await this.refreshPhonecallsStatus();
        this._phoneCallDetails.hideCallDisplay();
    },
    /**
     * Function overriden by each tab. Called when a phonecall starts.
     *
     * @return {Promise}
     */
    async initPhoneCall() {
        this._phoneCallDetails.showCallDisplay();
        this.trigger_up('showHangupButton');
    },
    /**
     * Called when the call is answered and then no more ringing.
     */
    onCallAccepted() {
        this._phoneCallDetails.activateInCallButtons();
        this._phoneCallDetails.startTimer();
    },
    /**
     * called when canceling an outgoing call
     *
     * @return {Promise}
     */
    async onCancelOutgoingCall() {
        if (!this._currentPhoneCallId) {
            return;
        }
        const currentPhoneCall = this._getCurrentPhoneCall();
        await currentPhoneCall.markPhonecallAsCanceled();
        await this.refreshPhonecallsStatus();
        this._phoneCallDetails.hideCallDisplay();
    },
    /**
     * Called when the user receives a call.
     *
     * @param {Object} param0
     * @param {string} param0.number
     * @param {integer} param0.partnerId
     * @return {Promise}
     */
    async onIncomingCall({ number, partnerId }) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_incoming_call',
            args: [number, partnerId],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        await this._selectPhoneCall(phoneCallId);
        this._phoneCallDetails.showCallDisplay();
        this._phoneCallDetails.receivingCall();
    },
    /**
     * Called when the user accepts an incoming call.
     *
     * @param {Object} param0
     * @param {string} param0.number
     * @param {integer} param0.partnerId
     * @return {Promise}
     */
    async onIncomingCallAccepted({ number, partnerId }) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_incoming_call_accepted',
            args: [[this._currentPhoneCallId], number, partnerId],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        await this._selectPhoneCall(phoneCallId);
        this._phoneCallDetails.showCallDisplay();
        this._phoneCallDetails.startTimer();
        this._phoneCallDetails.activateInCallButtons();
    },
    /**
     * Called when the user misses an incoming call.
     *
     * @param {Object} param0
     * @param {string} param0.number
     * @param {integer} param0.partnerId
     * @return {Promise}
     */
    async onMissedCall({ number, partnerId }) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_missed_call',
            args: [[this._currentPhoneCallId], number, partnerId],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        await this._selectPhoneCall(phoneCallId);
        this._phoneCallDetails.hideCallDisplay();
    },
    /**
     * Called when the user rejects an incoming call.
     *
     * @param {Object} param0
     * @param {string} param0.number
     * @param {int} param0.partnerId
     * @return {Promise}
     */
    async onRejectedCall({ number, partnerId }) {
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'create_from_rejected_call',
            args: [[this._currentPhoneCallId], number, partnerId],
        });
        const phoneCallId = await this._displayInQueue(phoneCallData);
        this._currentPhoneCallId = phoneCallId;
        await this._selectPhoneCall(phoneCallId);
        this._phoneCallDetails.hideCallDisplay();
    },
    /**
     * Performs a rpc to get the phonecalls then call the parsing method.
     *
     * @return {Promise}
     */
    async refreshPhonecallsStatus() {
        const phoneCallsData = await this._rpc({
            model: 'voip.phonecall',
            method: 'get_next_activities_list'
        });
        this._parsePhoneCalls(phoneCallsData);
    },
    /**
     * Hides the phonecall that doesn't match the search. Overriden in each tab.
     *
     * @param {string} search
     * @return {Promise}
     */
    async searchPhoneCall(search) {},

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Binds the scroll event to the tab.
     *
     * @private
     */
    _bindScroll() {
        this._offset = 0;
        this._$container = this.$el.closest('.tab-content');
        this._isLazyLoadFinished = false;
        this._isLazyLoading = false;

        this._$container.scroll(ev => this._onScrollTabContent(ev));
    },
    /**
     * @private
     */
    async _closePhoneDetails() {
        await this.replace(this._phoneCallDetails.$el);
        this._selectedPhoneCallId = false;
        this.trigger_up('showPanelHeader');
        this.refreshPhonecallsStatus();
    },
    /**
     * Computes the scroll limit before triggering the lazy loading of the
     * phonecalls.
     *
     * @private
     */
    _computeScrollLimit() {
        const height = this.$el.outerHeight();
        const tabHeight = this._$container.height();
        this._maxScrollHeight = height - tabHeight;
        if (this._maxScrollHeight > 0) {
            this._scrollLimit = this._maxScrollHeight / 3;
        }
    },
    /**
     * Creates a phonecall widget
     *
     * @private
     * @param {Object} phoneCallData
     * @return {voip.PhoneCall}
     */
    _createPhoneCall(phoneCallData) {
        if (phoneCallData.call_date) {
            const utcTime = fieldUtils.parse.datetime(
                phoneCallData.call_date,
                false,
                { isUTC: true });
                phoneCallData.call_date = utcTime.local().format('YYYY-MM-DD HH:mm:ss');
        }
        const phoneCall = new PhoneCall(this, phoneCallData);
        return phoneCall;
    },
    /**
     * Diplays the phonecall in the tab list.
     *
     * @private
     * @param {Object} phoneCallData
     * @return {Promise<integer>} resolved with phone call Id
     */
    async _displayInQueue(phoneCallData) {
        const phoneCall = this._createPhoneCall(phoneCallData);
        this._phoneCalls.push(phoneCall);
        await phoneCall.appendTo(this.$('.o_dial_phonecalls'));
        return phoneCall.id;
    },
    /**
     * @private
     * @return {voip.PhoneCall|undefined}
     */
    _getCurrentPhoneCall() {
        return this._phoneCalls.find(phoneCall =>
            phoneCall.id === this._currentPhoneCallId);
    },
    /**
     * Use to retrieve the phone call, fetch the phone call on Odoo if needed
     *
     * @private
     * @param {integer} phoneCallId
     * @return {voip.PhoneCall}
     */
    async _getPhoneCall(phoneCallId) {
        const phoneCall = this._phoneCalls.find(phoneCall => phoneCall.id === phoneCallId);
        if (phoneCall) {
            return phoneCall;
        }
        const phoneCallData = await this._rpc({
            model: 'voip.phonecall',
            method: 'search_read',
            domain: [['id', '=', phoneCallId]],
        });
        const id = await this._displayInQueue(phoneCallData[0]);
        return this._phoneCalls.find(phoneCall => phoneCall.id === id);
    },
    /**
     * @private
     * @return {voip.PhoneCall|undefined}
     */
    _getSelectedPhoneCall() {
        return this._phoneCalls.find(phoneCall =>
            phoneCall.id === this._selectedPhoneCallId);
    },
    /**
     * Goes through the phonecalls sent by the server and creates
     * a phonecall widget for each.
     *
     * @private
     * @param {Array[Object]} phoneCallsData
     * @return {Promise}
     */
    async _parsePhoneCalls(phoneCallsData) {
        const callTries = [];
        for (const phoneCall of this._phoneCalls) {
            callTries[phoneCall.id] = phoneCall.callTries;
            phoneCall.destroy();
        }
        this._phoneCalls = [];
        const proms = phoneCallsData.map(phoneCallData => {
            phoneCallData.callTries = callTries[phoneCallData.id];
            return this._displayInQueue(phoneCallData);
        });
        await Promise.all(proms);
        //Select again the selected phonecall before the refresh
        const previousSelection = this._getSelectedPhoneCall();
        if (previousSelection) {
            await this._selectPhoneCall(previousSelection.id);
        }
    },
    /**
     * Opens the details of a phonecall widget.
     *
     * @private
     * @param {integer} phoneCallId
     * @return {Promise}
     */
    async _selectPhoneCall(phoneCallId) {
        const phoneCall = this._phoneCalls.find(phoneCall =>
            phoneCall.id === phoneCallId);
        let $el = this.$el;
        if (this._selectedPhoneCallId) {
            $el = this._phoneCallDetails.$el;
        }
        this._phoneCallDetails = new PhoneCallDetails(this, phoneCall);
        await this._phoneCallDetails.replace($el);
        this._selectedPhoneCallId = phoneCallId;
        this.trigger_up('hidePanelHeader');
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @return {Promise}
     */
    async _onClosePhonecallDetails() {
        return this._closePhoneDetails();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {string} ev.data.number the number that will be called
     */
    async _onClickedOnNumber(ev) {
        this._currentPhoneCallId = this._selectedPhoneCallId;
        this.trigger_up('callNumber', {
            number: ev.data.number,
            phoneCall: await this._getPhoneCall(this._selectedPhoneCallId),
        });
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {Object} ev.data
     * @param {integer} ev.data.phoneCallId
     */
    async _onRemovePhoneCall(ev) {
        const resId = await this._rpc({
            model: 'voip.phonecall',
            method: 'remove_from_queue',
            args: [ev.data.phoneCallId],
        });
        await this.refreshPhonecallsStatus();
        core.bus.trigger('voip_widget_refresh', resId);
    },
    /**
     * @private
     * @param {ScrollEvent} ev
     */
    _onScrollTabContent(ev) {
        if (this._isLazyLoadFinished) {
            return;
        }
        if (!this._maxScrollHeight) {
            return;
        }
        if (!this._scrollLimit) {
            return;
        }
        if (this._isLazyLoading) {
            return;
        }
        if (this._maxScrollHeight - this._$container.scrollTop() >= this._scrollLimit) {
            return;
        }
        this._offset += this._limit;
        this._lazyLoadPhonecalls();
    },
    /**
     * @private
     * @param {OdooEvent} ev
     * @param {Object} ev.data
     * @param {integer} ev.data.phoneCallId
     * @return {Promise}
     */
    _onSelectCall(ev) {
        return this._selectPhoneCall(ev.data.phoneCallId);
    },
});

return PhoneCallTab;

});
