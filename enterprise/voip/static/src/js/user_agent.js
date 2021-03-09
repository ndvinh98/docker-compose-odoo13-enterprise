odoo.define('voip.UserAgent', function (require) {
"use strict";

const Class = require('web.Class');
const core = require('web.core');
const Dialog = require('web.Dialog');
const mixins = require('web.mixins');
const ServicesMixin = require('web.ServicesMixin');

const _t = core._t;

/**
 * @param {string} number
 * @return {string}
 */
function cleanNumber(number) {
    return number.replace(/[\s-/.\u00AD]/g, '');
}

const CALL_STATE = {
    NO_CALL: 0,
    RINGING_CALL: 1,
    ONGOING_CALL: 2,
    CANCELING_CALL: 3,
    REJECTING_CALL: 4,
};

const UserAgent = Class.extend(mixins.EventDispatcherMixin, ServicesMixin, {
    /**
     * Determine whether audio media can be played or not. This is useful in
     * test, to prevent "NotAllowedError". This may be triggered if no DOM
     * manipulation is detected before playing the media (chrome policy to
     * prevent from autoplaying)
     */
    PLAY_MEDIA: true,
    /**
     * @constructor
     */
    init(parent) {
        mixins.EventDispatcherMixin.init.call(this);
        this.setParent(parent);
        this._audioDialRingtone = undefined;
        this._audioIncomingRingtone = undefined;
        this._audioRingbackTone = undefined;
        this._callState = CALL_STATE.NO_CALL;
        this._currentNumber = undefined;
        this._dialog = undefined;
        this._currentCallParams = false;
        this._currentInviteSession = false;
        this._isOutgoing = false;
        this._mode = undefined;
        this._progressCount = 0;
        this._sipSession = undefined;
        this._timerAcceptedTimeout = undefined;
        this._userAgent = undefined;


        this._rpc({
            model: 'voip.configurator',
            method: 'get_pbx_config',
            args: [],
            kwargs: {},
        }).then(result => this._initUserAgent(result));
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Accept an incoming Call
     */
    acceptIncomingCall() {
        this._answerCall();
    },
    /**
     * Returns PBX Configuration.
     *
     * @return {Object} result user and pbx configuration return by the rpc
     */
    getPbxConfiguration() {
        return this.infoPbxConfiguration;
    },
    /**
     * Hangs up the current call.
     */
    hangup() {
        if (this._mode === 'demo') {
            if (this._callState === CALL_STATE.ONGOING_CALL) {
                this._onBye();
            } else {
                this._callState = CALL_STATE.CANCELING_CALL;
                this._onCancel();
            }
        }
        if (this._callState !== CALL_STATE.NO_CALL) {
            if (this._callState === CALL_STATE.RINGING_CALL) {
                this._callState = CALL_STATE.CANCELING_CALL;
                try {
                    this._sipSession.cancel();
                } catch (err) {
                    console.error(
                        _.str.sprintf(_t("Cancel failed: %s"), err));
                }
            } else {
                this._sipSession.bye();
            }
        }
    },
    /**
     * Instantiates a new sip call.
     *
     * @param {string} number
     */
    makeCall(number) {
        this._progressCount = 0;
        if (this._mode === 'demo') {
            if (this.PLAY_MEDIA) {
                this._audioRingbackTone.play().catch(() => {});
            }
            this._timerAcceptedTimeout = this._demoTimeout(() =>
                this._onAccepted());
            this._isOutgoing = true;
            return;
        }
        this._makeCall(number);
    },
    /**
     * Mutes the current call
     */
    muteCall() {
        if (this._mode === 'demo') {
            return;
        }
        if (this._callState !== CALL_STATE.ONGOING_CALL) {
            return;
        }
        this._setMute(true);
    },
    /**
     * Reject an incoming Call
     */
    rejectIncomingCall() {
        this._callState = CALL_STATE.REJECTING_CALL;
        if (this._mode === 'demo') {
            this.trigger_up('sip_rejected', this._currentCallParams);
        }
        if (!this._isOutgoing) {
            this._currentInviteSession.reject({ statusCode: 603 });
        }
    },
    /**
     * Sends dtmf, when there is a click on keypad number.
     *
     * @param {string} number number clicked
     */
    sendDtmf(number) {
        if (this._mode === 'demo') {
            return;
        }
        if (this._callState !== CALL_STATE.ONGOING_CALL) {
            return;
        }
        this._sipSession.dtmf(number);
    },
    /**
     * Transfers the call to the given number.
     *
     * @param {string} number
     */
    transfer(number) {
        if (this._mode === 'demo') {
            return;
        }
        if (this._callState !== CALL_STATE.ONGOING_CALL) {
            return;
        }
        this._sipSession.refer(number);
    },
    unmuteCall() {
        if (this._mode === 'demo') {
            return;
        }
        if (this._callState !== CALL_STATE.ONGOING_CALL) {
            return;
        }
        this._setMute(false);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------
    /**
     * Answer to a INVITE message and accept the call.
     *
     * @private
     */
    _answerCall() {
        const inviteSession = this._currentInviteSession;
        const incomingCallParams = this._currentCallParams;

        if (this._mode === 'demo') {
            this._callState = CALL_STATE.ONGOING_CALL;
            this.trigger_up('sip_incoming_call', incomingCallParams);
            return;
        }
        if (!inviteSession) {
            return;
        }
        this._audioIncomingRingtone.pause();
        const callOptions = {
            sessionDescriptionHandlerOptions: {
                constraints: {
                    audio: true,
                    video: false
                }
            }
        };
        inviteSession.accept(callOptions);
        this._isOutgoing = false;
        this._sipSession = inviteSession;
        this._configureRemoteAudio();
        this.trigger_up('sip_error', {
            isConnecting: true,
            message: _t("Please accept the use of the microphone."),
        });
        this._sipSession.sessionDescriptionHandler.on('userMedia', () =>
            this._onMicrophoneAccepted(incomingCallParams));
        this._sipSession.sessionDescriptionHandler.on('userMediaFailed', () =>
            this._onMicrophoneRefused());
        this._sipSession.sessionDescriptionHandler.on('addTrack', () =>
            this._configureRemoteAudio());
        this._sipSession.on('bye', () => this._onBye());
    },
    /**
     * If the caller cancels the phonecall, this is called
     *
     * @private
     */
    _canceledIncomingCall() {
        this._callState = CALL_STATE.CANCELING_CALL;
        this._onCancel();
    },
    /**
     * Clean the audio media stream after a call.
     *
     * @private
     */
    _cleanRemoteAudio() {
        this.$remoteAudio.srcObject = null;
        this.$remoteAudio.pause();
    },
    /**
     * Configure the remote audio, the ringtones
     *
     * @private
     */
    _configureDomElements() {
        this.$remoteAudio = document.createElement('audio');
        this.$remoteAudio.autoplay = true;
        $('html').append(this.$remoteAudio);
        this._audioRingbackTone = document.createElement('audio');
        this._audioRingbackTone.loop = 'true';
        this._audioRingbackTone.src = '/voip/static/src/sounds/ringbacktone.mp3';
        $('html').append(this._audioRingbackTone);
        this._audioIncomingRingtone = document.createElement('audio');
        this._audioIncomingRingtone.loop = 'true';
        this._audioIncomingRingtone.src = '/voip/static/src/sounds/incomingcall.mp3';
        $('html').append(this._audioincomingRingtone);
        this._audioDialRingtone = document.createElement('audio');
        this._audioDialRingtone.loop = 'true';
        this._audioDialRingtone.src = '/voip/static/src/sounds/dialtone.mp3';
        $('html').append(this._audioDialRingtone);
    },
    /**
     * Configure the audio media stream, at the begining of a call.
     *
     * @private
     */
    _configureRemoteAudio() {
        const call = this._sipSession;
        const peerConnection = call.sessionDescriptionHandler.peerConnection;
        let remoteStream = undefined;
        if (peerConnection.getReceivers) {
            remoteStream = new window.MediaStream();
            for (const receiver of peerConnection.getReceivers()) {
                const track = receiver.track;
                if (track) {
                    remoteStream.addTrack(track);
                }
            }
        } else {
            remoteStream = peerConnection.getRemoteStream()[0];
        }
        this.$remoteAudio.srcObject = remoteStream;
        if (this.PLAY_MEDIA) {
            this.$remoteAudio.play().catch(() => {});
        }
    },
    /**
     * Returns the ua after initialising it.
     *
     * @private
     * @param {Object} params user and pbx configuration parameters
     * @return {Object} the initialised ua
     */
    _createUserAgent(params) {
        if (!(params.pbx_ip && params.wsServer)) {
            this._triggerError(
                _t("PBX or Websocket address is missing. Please check your settings."));
            return false;
        }
        if (!(params.login && params.password)) {
            this._triggerError(
                _t("Your credentials are not correctly set. Please contact your administrator."));
            return false;
        }
        if (params.debug) {
            params.traceSip = true;
            params.log = {
                level: 3,
                builtinEnabled: true
            };
        } else {
            params.traceSip = false;
            params.log = {
                level: 2,
                builtinEnabled: false
            };
        }
        try {
            return new window.SIP.UA(this._getUaConfig(params));
        } catch (err) {
            this._triggerError(
                _t("The server configuration could be wrong. Please check your configuration."));
            return false;
        }
    },
    /**
     * @private
     * @param {function} func
     */
    _demoTimeout(func) {
        return setTimeout(func, 3000);
    },
    /**
     * Returns the UA configuration required.
     *
     * @private
     * @param {Object} params user and pbx configuration parameters
     * @return {Object} the ua configuration parameters
     */
    _getUaConfig(params) {
        const sessionDescriptionHandlerFactoryOptions = {
            constraints: {
                audio: true,
                video: false
            },
            iceCheckingTimeout: 1000,
        };
        return {
            authorizationUser: params.login,
            hackIpInContact: true,
            log: params.log,
            password: params.password,
            register: true,
            registerExpires: 3600,
            sessionDescriptionHandlerFactoryOptions,
            transportOptions: {
                wsServers: params.wsServer || null,
                traceSip: params.traceSip
            },
            uri: `${params.login}@${params.pbx_ip}`,
        };
    },
    /**
     * Initialises the ua, binds events and appends audio in the dom.
     *
     * @private
     * @param {Object} result user and pbx configuration return by the rpc
     */
    _initUserAgent(result) {
        this.infoPbxConfiguration = result;
        this._mode = result.mode;
        if (this._mode === 'prod') {
            this.trigger_up('sip_error', {
                isConnecting: true,
                message: _t("Connecting..."),
            });
            if (!window.RTCPeerConnection || !window.MediaStream || !navigator.mediaDevices) {
                this._triggerError(
                    _t("Your browser could not support WebRTC. Please check your configuration."));
                return;
            }
            this._userAgent = this._createUserAgent(result);
            if (!this._userAgent) {
                return;
            }
            this._alwaysTransfer = result.always_transfer;
            this._ignoreIncoming = result.ignore_incoming;
            if (result.external_phone) {
                this._externalPhone = cleanNumber(result.external_phone);
            }
            // catch the error if the ws uri is wrong
            this._userAgent.transport.ws.onerror = () => this._triggerError(
                _t("The websocket uri could be wrong. Please check your configuration."));
            this._userAgent.on('registrationFailed', this._onRegistrationFailed.bind(this));
            this._userAgent.on('registered', this._onRegistered.bind(this));
            this._userAgent.on('invite', this._onInvite.bind(this));
        }
        this._configureDomElements();
    },
    /**
     * Triggers the sip invite.
     *
     * @private
     * @param {string} number
     */
    _makeCall(number) {
        if (this._callState !== CALL_STATE.NO_CALL) {
            return;
        }
        try {
            number = cleanNumber(number);
            this._currentCallParams = { number };
            if (this._alwaysTransfer && this._externalPhone) {
                this._sipSession = this._userAgent.invite(this._externalPhone);
                this._currentNumber = number;
            } else {
                this._sipSession = this._userAgent.invite(number);
            }
            this._setupOutCall();
        } catch (err) {
            this._triggerError(
                _.string.sprintf(
                    _t("The connection cannot be made.</br> Please check your configuration.</br> (Reason received: %s)"),
                    err.reason_phrase));
            return;
        }
    },
    /**
     * Reject the inviteSession
     *
     * @private
     * @param {Object} inviteSession
     */
    _rejectInvite(inviteSession) {
        if (!this._isOutgoing) {
            this._audioIncomingRingtone.pause();
            inviteSession.reject({ statusCode: 603 });
        }
    },
    /**
     * TODO when the _sendNotification is moved into utils instead of mail.utils
     * remove this function and use the one in utils
     *
     * @private
     * @param {string} title
     * @param {string} content
     */
    _sendNotification(title, content) {
        if (
            window.Notification &&
            window.Notification.permission === 'granted'
        ) {
            return new window.Notification(title, {
                body: content,
                icon: '/mail/static/src/img/odoo_o.png',
                silent: true,
            });
        }
    },
    /**
     * (Un)set the sound of audio media stream
     *
     * @private
     * @param {boolean} mute
     */
    _setMute(mute) {
        const call = this._sipSession;
        const peerConnection = call.sessionDescriptionHandler.peerConnection;
        if (peerConnection.getSenders) {
            for (const sender of peerConnection.getSenders()) {
                if (sender.track) {
                    sender.track.enabled = !mute;
                }
            }
        } else {
            for (const stream of peerConnection.getLocalStreams()) {
                for (const track of stream.getAudioTracks()) {
                    track.enabled = !mute;
                }
            }
        }
    },
    /**
     * Bind events to outgoing call.
     *
     * @private
     */
    _setupOutCall() {
        this._isOutgoing = true;
        this._callState = CALL_STATE.RINGING_CALL;
        this.trigger_up('sip_error', {
            isConnecting: true,
            message: _t("Please accept the use of the microphone."),
        });
        this._sipSession.on('accepted', () => this._onAccepted());
        this._sipSession.on('cancel', () => this._onCancel());
        this._sipSession.on('rejected', response => this._onRejected(response));
        this._sipSession.on('progress', () => this._onTry());
        this._sipSession.on('SessionDescriptionHandler-created', () =>
            this._onInviteSentHelper());
    },
    /**
     * @private
     */
    _stopRingtones() {
        this._audioRingbackTone.pause();
        this._audioDialRingtone.pause();
    },
    /**
     * Triggers up an error.
     *
     * @private
     * @param {string} message message diplayed
     * @param {Object} [param1={}]
     * @param {boolean} [param1.isTemporary] if the message can be discarded or not
     */
    _triggerError(message, { isTemporary }={}) {
        this.trigger_up('sip_error', {
            isTemporary,
            message,
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Triggered when the call is answered.
     *
     * @private
     */
    async _onAccepted() {
        this._callState = CALL_STATE.ONGOING_CALL;
        const call = this._sipSession;
        this._stopRingtones();
        if (this._mode === 'prod') {
            this._configureRemoteAudio();
            call.sessionDescriptionHandler.on('addTrack', () =>
                this._configureRemoteAudio());
            call.on('bye', () => this._onBye());
            if (this._alwaysTransfer && this._currentNumber) {
                call.refer(this._currentNumber);
            }
        }
        this.trigger_up('sip_accepted');
    },
    /**
     * Handles the sip session ending.
     *
     * @private
     */
    _onBye() {
        this._cleanRemoteAudio();
        this._audioDialRingtone.pause();
        this._sipSession = false;
        this._callState = CALL_STATE.NO_CALL;
        if (this._mode === 'demo') {
            clearTimeout(this._timerAcceptedTimeout);
        }
        this.trigger_up('sip_bye');
    },
    /**
     * Handles the sip session cancel.
     *
     * @private
     */
    _onCancel() {
        if (this._callState !== CALL_STATE.CANCELING_CALL) {
            return;
        }
        if (this._isOutgoing) {
            this.trigger_up('sip_cancel_outgoing');
        } else {
            this.trigger_up('sip_cancel_incoming', this._currentCallParams);
        }
        this._sipSession = false;
        this._callState = CALL_STATE.NO_CALL;
        this._stopRingtones();
        if (this._mode === 'demo') {
            clearTimeout(this._timerAcceptedTimeout);
        }
    },
    /**
     * @private
     * @param {Object} inviteSession
     */
    _onCurrentInviteSessionRejected(inviteSession) {
        if (this._notification) {
            this._notification.removeEventListener('close', this._rejectInvite, inviteSession);
            this._notification.close();
            this._notification = undefined;
            this._audioIncomingRingtone.pause();
        }
        if ((typeof this._dialog !== 'undefined') && (this._dialog.$el.is(":visible"))) {
            this._dialog.close();
            this._audioIncomingRingtone.pause();
        }
        if (this._callState === CALL_STATE.REJECTING_CALL) {
            this.trigger_up('sip_rejected', this._currentCallParams);
            this._callState = CALL_STATE.NO_CALL;
        } else {
            this._canceledIncomingCall();
        }
    },
    /**
     * handle the fact that the user does not give the right to use the mic
     *
     * @private
     */
    _onErrorMicrophone() {
        this._triggerError(
            _t("Please Allow the use of the microphone"),
            { isTemporary: true });
        this.hangup();
    },
    /**
     * Handles the invite event.
     *
     * @private
     * @param {Object} inviteSession
     */
    async _onInvite(inviteSession) {
        if (
            this._ignoreIncoming ||
            this._callState === CALL_STATE.ONGOING_CALL
        ) {
            inviteSession.reject({ statusCode: 603 });
            return;
        }

        function sanitizedPhone(prefix, number) {
            if (number.startsWith("00")){
                return "+" + number.substr(2, number.length);
            }
            else if (number.startsWith("0")) {
                return "+" + prefix + number.substr(1, number.length);
            }
            /* USA exception for domestic numbers : In the US, the convention is 1 (area code)
             * extension, while in Europe it is (0 area code)/extension.
             */
            else if (number.startsWith("1")) {
                return "+" + number;
            }
        }

        let name = inviteSession.remoteIdentity.displayName;
        const number = inviteSession.remoteIdentity.uri.user;
        let numberSanitized = sanitizedPhone(inviteSession.remoteIdentity.uri.type, number);
        this._currentInviteSession = inviteSession;
        let domain;
        if (numberSanitized) {
            domain = [
                '|', '|',
                ['sanitized_phone', 'ilike', number],
                ['sanitized_mobile', 'ilike', number],
                '|',
                ['sanitized_phone', 'ilike', numberSanitized],
                ['sanitized_mobile', 'ilike', numberSanitized],
            ];
        } else {
            domain = [
                '|',
                ['sanitized_phone', 'ilike', number],
                ['sanitized_mobile', 'ilike', number],
            ];
        }
        let contacts = await this._rpc({
            model: 'res.partner',
            method: 'search_read',
            domain: domain,
            fields: ['id', 'display_name'],
            limit: 1,
        });
        /* Fallback if inviteSession.remoteIdentity.uri.type didn't give the correct country prefix
        */
        if (!contacts.length) {
            let lastSixDigitsNumber = number.substr(number.length - 6)
            contacts = await this._rpc({
                model: 'res.partner',
                method: 'search_read',
                domain: [
                    '|',
                    ['sanitized_phone', '=like', '%'+lastSixDigitsNumber],
                    ['sanitized_mobile', '=like', '%'+lastSixDigitsNumber],
                ],
                fields: ['id', 'display_name'],
                limit: 1,
            });
        }
        const incomingCallParams = { number };
        let contact = false;
        if (contacts.length) {
            contact = contacts[0];
            name = contact.display_name;
            incomingCallParams.partnerId = contact.id;
        }
        let content;
        if (name) {
            content = _.str.sprintf(_t("Incoming call from %s (%s)"), name, number);
        } else {
            content = _.str.sprintf(_t("Incoming call from %s"), number);
        }
        this._isOutgoing = false;
        this._callState = CALL_STATE.RINGING_CALL;
        this._audioIncomingRingtone.currentTime = 0;
        if (this.PLAY_MEDIA) {
            this._audioIncomingRingtone.play().catch(() => {});
        }
        this._notification = this._sendNotification('Odoo', content);
        this._currentCallParams = incomingCallParams;
        this.trigger_up('incomingCall', incomingCallParams);

        this._currentInviteSession.on('rejected', () =>
            this._onCurrentInviteSessionRejected(inviteSession));
        if (window.Notification && window.Notification.requestPermission) {
            window.Notification.requestPermission()
                .then(permission => this._onWindowNotificationPermissionRequested({ content, inviteSession, permission }))
                .catch(() => this._onWindowNotificationPermissionRequested({ content, inviteSession }));
        } else {
            this._onWindowNotificationPermissionRequested({ content, inviteSession })
        }
    },
    /**
     * Starts the first ringing tone
     *
     * @private
     */
    _onInviteSent() {
        this.trigger_up('sip_error_resolved');
        if (this.PLAY_MEDIA) {
            this._audioDialRingtone.play().catch(() => {});
        }
    },
    /**
     * This function is needed to ensure that the sessionDescriptionHandler exists
     * Indeed, he is created before the event SessionDescriptionHandler-created
     * Also used to catch the error when there is an error with the mic.
     *
     * @private
     */
    _onInviteSentHelper() {
        this._sipSession.sessionDescriptionHandler.on('userMedia', () =>
            this._onInviteSent());
        this._sipSession.sessionDescriptionHandler.on('userMediaFailed', () =>
            this._onErrorMicrophone());
    },
    /**
     * Once it is confirmed the user gave acces to the mic, we start the call and unblock the widget
     *
     * @private
     * @param {Object} incomingCallParams contains the name and partnerID
     * @param {string} incomingCallParams.number
     * @param {integer} incomingCallParams.partnerId
     */
    _onMicrophoneAccepted(incomingCallParams) {
        this._callState = CALL_STATE.ONGOING_CALL;
        this.trigger_up('sip_incoming_call', incomingCallParams);
    },
    /**
     * User refused the use of the microphone, the call is rejected and a notification is send to the user
     *
     * @private
     */
    _onMicrophoneRefused() {
        this.rejectIncomingCall();
        this._triggerError(
            _t("The call was rejected as access rights to the microphone were not given"),
            { isTemporary: true });
    },
    /**
     * Triggered when the user agent is connected.
     * This function will trigger the event 'sip_error_resolved' to unblock the
     * overlay
     *
     * @private
     */
    _onRegistered() {
        this.trigger_up('sip_error_resolved');
    },
    /**
     * User registration failed. A notification of the error is send in the widget and it stays blocked
     *
     * @private
     */
    _onRegistrationFailed() {
        this._triggerError(
            _t("There was an error with your registration: Please check your configuration."));
    },
    /**
     * Handles the sip session rejection.
     *
     * @private
     * @param {Object} response is emitted by sip.js lib
     * @param {string} response.reasonPhrase
     * @param {integer} response.statusCode used in this function respectively
     *   stand for:
     * - 404 : Not Found
     * - 488 : Not Acceptable Here
     * - 603 : Decline
     */
    _onRejected(response) {
        this._callState = CALL_STATE.REJECTING_CALL;
        this._stopRingtones();
        this._sipSession = false;
        this._callState = CALL_STATE.NO_CALL;
        if (
            response.statusCode === 404 ||
            response.statusCode === 488 ||
            response.statusCode === 603
        ) {
            this._triggerError(
                _.str.sprintf(
                    "The number is incorrect, the user credentials could be wrong or the connection cannot be made. Please check your configuration.</br> (Reason received: %s)",
                    response.reasonPhrase),
                { isTemporary: true });
            this.trigger_up('sip_cancel_outgoing');
        }
    },
    /**
     * Triggered when the call tries to connect.
     * Two tries are received before the phone start ringing
     *
     * @private
     */
    _onTry() {
        if (this._progressCount === 2) {
            this._progressCount = 0;
            this._stopRingtones();
            if (this.PLAY_MEDIA) {
                this._audioRingbackTone.play().catch(() => {});
            }
            this.trigger_up('changeStatus');
        } else {
            this._progressCount++;
        }
    },
    /**
     * @private
     * @param {Object} param0
     * @param {string} param0.content
     * @param {Object} param0.inviteSession
     * @param {string} [param0.permission]
     */
    _onWindowNotificationPermissionRequested({
        content,
        inviteSession,
        permission,
    }) {
        if (permission === 'granted') {
            this._notification = this._sendNotification("Odoo", content);
            if (this._notification) {
                this._notification.onclick = function () {
                    window.focus();
                    this.close();
                };
                this._notification.removeEventListener('close', this._rejectInvite, inviteSession);
            }
        } else {
            this._dialog = Dialog.confirm(this, content, {
                confirm_callback: () => this._answerCall(),
                cancel_callback: () => {
                    try {
                        this.rejectIncomingCall();
                    } catch (err) {
                        console.error(
                            _.str.sprintf(_t("Reject failed: %s"), err));
                    }
                    this._audioIncomingRingtone.pause();
                },
            });
        }
    },
});

return UserAgent;

});
