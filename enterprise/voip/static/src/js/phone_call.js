odoo.define('voip.PhoneCall', function (require) {
"use strict";

const Widget = require('web.Widget');

const PhoneCall = Widget.extend({
    template: 'voip.PhoneCall',
    events: {
        'click': '_onClick',
        'click .o_dial_remove_phonecall': '_onClickRemovePhoneCall',
    },
    /**
     * @override
     * @param {voip.PhoneCallTab} parent
     * @param {Object} param1
     * @param {integer} param1.activity_id
     * @param {string} param1.activity_model_name
     * @param {integer} param1.activity_res_id
     * @param {string} param1.activity_res_model
     * @param {string} param1.activity_summary
     * @param {integer} [param1.callTries=0]
     * @param {string} param1.call_date
     * @param {integer} param1.duration
     * @param {integer} param1.id
     * @param {boolean} param1.isContact
     * @param {boolean} param1.isRecent
     * @param {string} param1.mobile
     * @param {string} param1.name
     * @param {string} param1.partner_email
     * @param {integer} param1.partner_id
     * @param {string} param1.partner_image_128
     * @param {string} [param1.partner_name]
     * @param {string} param1.phone
     * @param {string} param1.state ['cancel', 'done', 'open', 'pending']
     */
    init(parent, {
        activity_id,
        activity_model_name,
        activity_res_id,
        activity_res_model,
        activity_summary,
        callTries=0,
        call_date,
        duration,
        id,
        isContact,
        isRecent,
        mobile,
        name,
        partner_email,
        partner_id,
        partner_image_128,
        partner_name,
        phone,
        state,
    }) {
        this._super(...arguments);

        this.activityId = activity_id;
        this.activityModelName = activity_model_name;
        this.activityResId = activity_res_id;
        this.activityResModel = activity_res_model;
        this.callTries = callTries;
        this.date = call_date;
        this.email = partner_email;
        this.id = id;
        this.imageSmall = partner_image_128;
        this.isContact = isContact;
        this.isRecent = isRecent;
        this.minutes = Math.floor(duration).toString();
        this.mobileNumber = mobile;
        this.name = name;
        this.partnerId = partner_id;
        this.partnerName = partner_name ? partner_name : name;
        this.phoneNumber = phone;
        this.seconds = (duration % 1 * 60).toFixed();
        this.state = state;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Makes rpc to log the hangup call.
     *
     * @param {Object} param0 contains the duration of the call and if the call
     *   is finished
     * @param {integer} param0.durationSeconds
     * @param {boolean} param0.isDone
     * @return {Promise}
     */
    async hangUp({
        durationSeconds,
        isDone,
    }) {
        if (this.id === undefined) {
            console.warn('phonecall has no id!');
        } else {
            await this._rpc({
                model: 'voip.phonecall',
                method: 'hangup_call',
                args: [this.id],
                kwargs: {
                    done: isDone,
                    duration_seconds: durationSeconds,
                },
            });
        }
        this.call('mail_service', 'getMailBus').trigger('voip_reload_chatter');
    },
    /**
     * Makes rpc to set the call as canceled.
     *
     * @return {Promise}
     */
    async markPhonecallAsCanceled() {
        if (this.id === undefined) {
            console.warn('phonecall has no id!');
            return;
        }
        return this._rpc({
            model: 'voip.phonecall',
            method: 'canceled_call',
            args: [this.id],
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    _onClick() {
        this.trigger_up('selectCall', {
            phoneCallId: this.id,
        });
    },
    /**
     * @private
     *
     * @param {MouseEvent} ev
     */
    _onClickRemovePhoneCall(ev) {
        ev.stopPropagation();
        ev.preventDefault();
        this.trigger_up('removePhoneCall', {
            phoneCallId: this.id,
        });
    },
});

return PhoneCall;

});
