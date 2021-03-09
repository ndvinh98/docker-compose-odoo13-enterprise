odoo.define('voip.PhoneCallContactsTab', function (require) {
"use strict";

const PhoneCallTab = require('voip.PhoneCallTab');

const PhoneCallContactsTab = PhoneCallTab.extend({

    /**
     * @constructor
     */
    init() {
        this._super(...arguments);
        this._limit = 9;
        this._searchDomain = undefined;
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
     * @override
     * @return {Promise}
     */
    async initPhoneCall() {
        const _super = this._super.bind(this, ...arguments); // limitation of class.js
        const currentPhoneCall = this._getCurrentPhoneCall();
        // if a state exists, a call was previously made so we use log it as created from a recent call
        let phoneCallData;
        if (currentPhoneCall.state) {
            phoneCallData = await this._rpc({
                model: 'voip.phonecall',
                method: 'create_from_recent',
                args: [currentPhoneCall.id],
            });
        } else {
            phoneCallData = await this._rpc({
                model: 'voip.phonecall',
                method: 'create_from_contact',
                args: [currentPhoneCall.partnerId],
            });
        }
        this._currentPhoneCallId = await this._displayInQueue(phoneCallData);
        await this._selectPhoneCall(this._currentPhoneCallId);
        return _super();
    },
    /**
     * @override
     */
    async refreshPhonecallsStatus() {
        this._offset = 0;
        this._isLazyLoadFinished = false;
        const contactsData = await this._rpc({
            model: 'res.partner',
            method: 'search_read',
            fields: [
                'display_name',
                'email',
                'id',
                'image_128',
                'mobile',
                'phone'
            ],
            limit: this._limit,
        });
        return this._parseContactsData(contactsData);
    },
    /**
     * @override
     * @param {string} search
     * @return {Promise}
     */
    async searchPhoneCall(search) {
        if (search) {
            this._searchDomain = [
                '|',
                ['display_name', 'ilike', search],
                ['email', 'ilike', search]
            ];
            this._offset = 0;
            this._isLazyLoadFinished = false;
            const contactsData = await this._rpc({
                domain: this._searchDomain,
                fields: [
                    'email',
                    'display_name',
                    'id',
                    'image_128',
                    'mobile',
                    'phone',
                ],
                limit: this._limit,
                method: 'search_read',
                model: 'res.partner',
                offset: this._offset,
            });
            return this._parseContactsData(contactsData);
        } else {
            this._searchDomain = false;
            await this.refreshPhonecallsStatus();
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
        const contactsData = await this._rpc({
            model: 'res.partner',
            method: 'search_read',
            domain: this._searchDomain ? this._searchDomain : false,
            fields: [
                'display_name',
                'email',
                'id',
                'image_128',
                'mobile',
                'phone',
            ],
            limit: this._limit,
            offset: this._offset
        });
        if (!contactsData.length) {
            this._isLazyLoadFinished = true;
        }
        const phoneCallsData = this._makePhoneCallsDataFromContactsData(contactsData);
        const promises = phoneCallsData.map(phoneCallData =>
            this._displayInQueue(phoneCallData));
        await Promise.all(promises);
        this._computeScrollLimit();
        this._isLazyLoading = false;
    },
    /**
     * Since the contact tab is based on res_partner and not voip_phonecall,
     * this method make the convertion between the models.
     *
     * @private
     * @param {Object[]} contactsData
     * @return {Object[]}
     */
    _makePhoneCallsDataFromContactsData(contactsData) {
        return contactsData.map(contactData => {
            return {
                id: _.uniqueId(`virtual_phone_call_id_${contactData.id}_`),
                isContact: true,
                mobile: contactData.mobile,
                partner_email: contactData.email,
                partner_id: contactData.id,
                partner_image_128: contactData.image_128,
                partner_name: contactData.display_name,
                phone: contactData.phone,
            };
        });
    },
    /**
     * Parses the contacts to convert them and then calls the _parsePhoneCalls.
     *
     * @private
     * @param {Object[]} contactsData
     * @return {Promise}
     */
    async _parseContactsData(contactsData) {
        this._computeScrollLimit();
        return this._parsePhoneCalls(
            this._makePhoneCallsDataFromContactsData(contactsData));
    },
});

return PhoneCallContactsTab;

});
