odoo.define('voip.PhoneCallDetails', function (require) {
"use strict";

const core = require('web.core');
const session = require('web.session');
const Widget = require('web.Widget');

const QWeb = core.qweb;
const _t = core._t;

const PhoneCallDetails = Widget.extend({
    template: 'voip.PhoneCallDetails',
    events: {
        'click .o_dial_activity_done': '_onClickActivityDone',
        'click .o_dial_call_number': '_onClickCallNumber',
        'click .o_dial_activity_cancel': '_onClickCancel',
        'click .o_phonecall_details_close': '_onClickDetailsClose',
        'click .o_dial_email': '_onClickEmail',
        'click .o_dial_log': '_onClickLog',
        'click .o_dial_mute_button': '_onClickMuteButton',
        'click .o_dial_reschedule_activity': '_onClickRescheduleActivity',
        'click .o_dial_to_partner': '_onClickToPartner',
        'click .o_dial_to_record': '_onClickToRecord',
        'click .o_dial_transfer_button': '_onClickTransferButton',
    },
    /**
     * TODO: reduce coupling between PhoneCallDetails & PhoneCall
     *
     * @override
     * @param {voip.PhoneCallTab} parent
     * @param {voip.PhoneCall} phoneCall
     */
    init(parent, phoneCall) {
        this._super(...arguments);

        this.activityId = phoneCall.activityId;
        this.activityResId = phoneCall.activityResId;
        this.activityModelName = phoneCall.activityModelName;
        this.date = phoneCall.date;
        this.durationSeconds = 0;
        this.email = phoneCall.email;
        this.id = phoneCall.id;
        this.imageSmall = phoneCall.imageSmall;
        this.minutes = phoneCall.minutes;
        this.mobileNumber = phoneCall.mobileNumber;
        this.name = phoneCall.name;
        this.partnerId = phoneCall.partnerId;
        this.partnerName = phoneCall.partnerName
            ? phoneCall.partnerName
            : _t("Unknown");
        this.phoneNumber = phoneCall.phoneNumber;
        this.seconds = phoneCall.seconds;
        this.state = phoneCall.state;

        this._$closeDetails = undefined;
        this._$muteButton = undefined;
        this._$muteIcon = undefined;
        this._$phoneCallActivityButtons = undefined;
        this._$phoneCallDetails = undefined;
        this._$phoneCallInCall = undefined;
        this._$phoneCallInfo = undefined;
        this._$phoneCallReceivingCall = undefined;
        this._activityResModel = phoneCall.activityResModel;
        this._isMuted = false;
    },
    /**
     * @override
     */
    start() {
        this._super(...arguments);

        this._$closeDetails = this.$('.o_phonecall_details_close');
        this._$muteButton = this.$('.o_dial_mute_button');
        this._$muteIcon = this.$('.o_dial_mute_button .fa');
        this._$phoneCallActivityButtons = this.$('.o_phonecall_activity_button');
        this._$phoneCallDetails = this.$('.o_phonecall_details');
        this._$phoneCallInCall = this.$('.o_phonecall_in_call');
        this._$phoneCallInfo = this.$('.o_phonecall_info');
        this._$phoneCallReceivingCall = this.$('.o_dial_incoming_buttons');

        this._$muteButton.attr('disabled', 'disabled');
        this.$('.o_dial_transfer_button').attr('disabled', 'disabled');
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * The call is accepted then we can offer more options to the user.
     */
    activateInCallButtons() {
        this.$('.o_dial_transfer_button').removeAttr('disabled');
        this.$('.o_dial_mute_button').removeAttr('disabled');
    },
    /**
     * Changes the display to show the in call layout.
     */
    hideCallDisplay() {
        this._$phoneCallDetails.removeClass('details_in_call');
        this.$('.o_phonecall_status').hide();
        this._$closeDetails.show();
        this._$phoneCallInfo.show();
        this._$phoneCallInCall.hide();
        this._$phoneCallReceivingCall.hide();
        this.$el.removeClass('in_call');
    },
    /**
     * Changes the display to show the Receiving layout.
     */
    receivingCall() {
        this.$('.o_dial_keypad_button_container').hide();
        this._$phoneCallInCall.hide();

    },
    /**
     * Change message in widget to Ringing
     */
    setStatusRinging() {
        this.$('.o_phonecall_status').html(QWeb.render('voip.PhoneCallStatus', {
             duration: '00:00',
             status: 'ringing',
         }));
     },
    /**
     * Changes the display to show the in call layout.
     */
    showCallDisplay() {
        this.$('.o_phonecall_status').html(QWeb.render('voip.PhoneCallStatus', {
            duration: '00:00',
            status: 'connecting',
        }));
        this._$phoneCallDetails.addClass('details_in_call');
        this._$closeDetails.hide();
        this._$phoneCallInfo.hide();
        this._$phoneCallInCall.show();
        this._$phoneCallActivityButtons.hide();
        this.$el.addClass('in_call');
    },
    /**
     * Starts the timer
     */
    startTimer() {
        this.durationSeconds = 0;

        /**
         * @param {integer} val
         * @return {string}
         */
        function formatTimer(val) {
            return val > 9 ? val : "0" + val;
        }

        setInterval(() => {
            this.durationSeconds++;
            const seconds = formatTimer(this.durationSeconds % 60);
            const minutes = formatTimer(parseInt(this.durationSeconds / 60));
            const duration = _.str.sprintf("%s:%s", minutes, seconds);
            this.$('.o_phonecall_status').html(QWeb.render('voip.PhoneCallStatus', {
                duration,
                status: 'in_call',
            }));
        }, 1000);
    },
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    async _onClickActivityDone(ev) {
        ev.preventDefault();
        await this._rpc({
            model: 'mail.activity',
            method: 'action_done',
            args: [[this.activityId]],
        });
        this.call('mail_service', 'getMailBus').trigger('voip_reload_chatter');
        this._$phoneCallActivityButtons.hide();
        this.trigger_up('markActivityDone');
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickCallNumber(ev) {
        ev.preventDefault();
        this.trigger_up('clickedOnNumber', {
            number: ev.currentTarget.text,
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    async _onClickCancel(ev) {
        ev.preventDefault();
        await this._rpc({
            model: 'mail.activity',
            method: 'unlink',
            args: [[this.activityId]],
        });
        this._$phoneCallActivityButtons.hide();
        this.trigger_up('cancelActivity');
    },
    /**
     * @private
     */
    _onClickDetailsClose() {
        this.trigger_up('closePhonecallDetails');
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickEmail(ev) {
        ev.preventDefault();
        if (this._activityResModel && this.activityResId) {
            this.do_action({
                context: {
                    active_ids: [this.activityResId],
                    default_composition_mode: 'mass_mail',
                    default_model: this._activityResModel,
                    default_partner_ids: this.partnerId ? [this.partnerId] : [],
                    default_use_template: true,
                },
                key2: 'client_action_multi',
                multi: 'True',
                res_model: 'mail.compose.message',
                src_model: 'voip.phonecall',
                target: 'new',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            });
        } else if (this.partnerId) {
            this.do_action({
                context: {
                    active_ids: [this.partnerId],
                    default_composition_mode: 'mass_mail',
                    default_model: 'res.partner',
                    default_partner_ids: [this.partnerId],
                    default_use_template: true,
                },
                key2: 'client_action_multi',
                multi: 'True',
                res_model: 'mail.compose.message',
                src_model: 'voip.phonecall',
                target: 'new',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            });
        }
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickLog(ev) {
        ev.preventDefault();
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'mail.activity',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_res_id: this.activityResId,
                default_res_model: this._activityResModel,
            },
            res_id: this.activityId,
        }, {
            on_close: () => this.call('mail_service', 'getMailBus').trigger('voip_reload_chatter')
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickMuteButton(ev) {
        ev.preventDefault();
        if (!this._isMuted) {
            this.trigger_up('muteCall');
            this._$muteIcon.removeClass('fa-microphone');
            this._$muteIcon.addClass('fa-microphone-slash');
            this._isMuted = true;
        } else {
            this.trigger_up('unmuteCall');
            this._$muteIcon.addClass('fa-microphone');
            this._$muteIcon.removeClass('fa-microphone-slash');
            this._isMuted = false;
        }
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickRescheduleActivity(ev) {
        ev.preventDefault();
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'mail.activity',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {
                default_res_id: this.activityResId,
                default_res_model: this._activityResModel,
            },
            res_id: false,
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     * @return {Promise}
     */
    async _onClickToPartner(ev) {
        ev.preventDefault();
        let resId = this.partnerId;
        if (!this.partnerId) {
            let domain = [];
            if (this.phoneNumber && this.mobileNumber) {
                domain = ['|',
                    ['phone', '=', this.phoneNumber],
                    ['mobile', '=', this.mobileNumber]];
            } else if (this.phoneNumber) {
                domain = ['|',
                    ['phone', '=', this.phoneNumber],
                    ['mobile', '=', this.phoneNumber]];
            } else if (this.mobileNumber) {
                domain = [['mobile', '=', this.mobileNumber]];
            }
            const ids = await this._rpc({
                method: 'search_read',
                model: "res.partner",
                kwargs: {
                    domain,
                    fields: ['id'],
                    limit: 1,
                }
            });
            if (ids.length) {
                resId = ids[0].id;
            }
        }
        if (resId !== undefined) {
            this.do_action({
                res_id: resId,
                res_model: "res.partner",
                target: 'current',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            });
        } else {
            this.do_action({
                context: {
                    default_email: this.email,
                    default_phone: this.phoneNumber,
                    default_mobile: this.mobileNumber,
                },
                res_model: 'res.partner',
                target: 'current',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            });
        }
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    async _onClickToRecord(ev) {
        ev.preventDefault();
        const resModel = this._activityResModel;
        const resId = this.activityResId;
        const viewId = await this._rpc({
            model: resModel,
            method: 'get_formview_id',
            args: [[resId]],
            context: session.user_context,
        });
        this.do_action({
            res_id: resId,
            res_model: resModel,
            type: 'ir.actions.act_window',
            views: [[viewId || false, 'form']],
            view_mode: 'form',
            view_type: 'form',
        });
    },
    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClickTransferButton(ev) {
        ev.preventDefault();
        // Launch the transfer wizard
        this.do_action({
            context: {},
            flags: { headless: true },
            key2: 'client_action_multi',
            multi: 'True',
            res_model: 'voip.phonecall.transfer.wizard',
            src_model: 'voip.phonecall',
            target: 'new',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        });
    },
});

return PhoneCallDetails;

});
