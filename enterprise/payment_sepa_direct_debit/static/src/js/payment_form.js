odoo.define('payment_sepa_direct_debit.payment_form', function(require) {
"use strict";

var core = require('web.core');
var _t = core._t;
var PaymentForm = require('payment.payment_form');
var SepaSignatureForm = require('payment_sepa_direct_debit.signature_form');

require('web.dom_ready');

PaymentForm.include({
    events: _.extend({}, PaymentForm.prototype.events, {
        "click .o_sepa_send_sms": "_sendSms",
    }),
    _resetSepa: function() {
        this.mandate_id = undefined;
        if (this.sign_widget) {
            this.sign_widget.destroy();
        }
    },
    _setupSignature: function() {
        var checked_radio = this.$('input[type="radio"]:checked')[0];
        var acquirer_id = this.getAcquirerIdFromRadio(checked_radio);
        var $sign = this.$('#o_payment_add_token_acq_' + acquirer_id).find('.o_sepa_signature_form');
        this.sign_widget = new SepaSignatureForm(this, {
            mode: 'draw',
            nameAndSignatureOptions: $sign.data()
        });
        this.sign_widget.insertAfter($sign);
    },
    _sendSms: function(e) {
        e.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');
        var acquirer_id = this.getAcquirerIdFromRadio($checkedRadio[0]);
        var self = this;
        var $send_sms = $(e.target).closest('.o_sepa_send_sms');
        var $sepa_form = $(e.target).closest('#sepa_onboarding_form_' + acquirer_id);
        var sepa_data = this.getFormData($sepa_form.find('input'));
        $send_sms.attr('disabled', true);
        return this._rpc({
            route: "/payment/sepa_direct_debit/send_sms",
            params: {
                iban: sepa_data.iban,
                phone: sepa_data.phone,
                acquirer_id: acquirer_id,
                partner_id: this.options.partnerId,
                mandate_id: self.mandate_id || false,
            }
        }).then(function (result) {
            self.mandate_id = result.mandate_id;
            if (result.error)
                return Promise.reject(result.error);
            self.hideError();
            var $codeInput = $sepa_form.find('input[name="validation_code"]').removeAttr('readonly');
            $send_sms.html("<span><i class='fa fa-check'/> "+_t("SMS Sent")+"</span>");
            setTimeout(function() {
                $send_sms.removeAttr('disabled');
                $send_sms.text(_t('Re-send SMS'));
            }, 15000);
        }).guardedCatch(function (error) {
            $send_sms.removeAttr('disabled');
            self.displayError(_t("Unable to send SMS"), error || _t("Please check your IBAN and phone number."));
        });
    },
    _prepareSepaValues: function($checkedRadio) {
        var acquirer_id = this.getAcquirerIdFromRadio($checkedRadio[0]);
        var $sepa_form = this.$('#sepa_onboarding_form_' + acquirer_id);
        // check sms input is at least there
        if ($sepa_form.data('sms-enabled') && !$sepa_form.find('input[name="validation_code"]').val()) {
            this.displayError(_t('Missing Validation Code'), _t('Please enter the SMS validation code.'));
            return false;
        }
        var sign_enabled = $sepa_form.data('sign-enabled');
        if (sign_enabled) {
            // check and dump signature in form
            if (this.sign_widget.nameAndSignature.isSignatureEmpty()) {
                this.displayError(_t('Missing Signature'), _t('Please enter your signature.'));
                return false;
            }
            var signValues = this.sign_widget._getValues();
            // we need to insert the image signature as an input in the form, will be handled in the controller
            $sepa_form.append($('<input type="hidden" name="signature"></input>').val(signValues.signature));
        }
        if (this.mandate_id) {
            $sepa_form.append($('<input type="hidden" name="mandate_id"></input>').val(this.mandate_id));
        }
        return true;
    },
    /**
     * @override
     */
    payEvent: function (ev) {
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');

        // if the user has selected a sepa mandata as payment method
        if ($checkedRadio.length === 1 && $checkedRadio.data('provider') === 'sepa_direct_debit') {
            if  (!this._prepareSepaValues($checkedRadio)) {
                return Promise.reject();
            }
        }
        return this._super.apply(this, arguments);
    },
    addPmEvent: function (ev) {
        ev.preventDefault();
        var $checkedRadio = this.$('input[type="radio"]:checked');

        // if the user is creating a new SEPA payment
        if ($checkedRadio.length === 1 && $checkedRadio.data('provider') === 'sepa_direct_debit') {
            if  (!this._prepareSepaValues($checkedRadio)) {
                return Promise.reject();
            }
        }
        return this._super.apply(this, arguments);
    },
    /**
     * @override
     *
     * start the signature widget for the sepa form manually
     * we want to keep a reference to it to get its values manually
     * in the submission flow of the payment token information
     */
    updateNewPaymentDisplayStatus: function () {
        var checked_radio = this.$('input[type="radio"]:checked')[0];
        var acquirer_id = this.getAcquirerIdFromRadio(checked_radio);
        var $sepa_form = this.$('#sepa_onboarding_form_' + acquirer_id);
        this._resetSepa();
        var res = this._super();
        if (this.isNewPaymentRadio(checked_radio) && $(checked_radio).data('provider') === 'sepa_direct_debit' && $sepa_form.data('sign-enabled')) {
            this._setupSignature();
        }
        return res;
    },
});
});
