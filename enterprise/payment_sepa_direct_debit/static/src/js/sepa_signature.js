odoo.define('payment_sepa_direct_debit.signature_form', function(require) {
'use strict';

var SignatureForm = require('portal.signature_form').SignatureForm;
var NameAndSignature = require('web.name_and_signature').NameAndSignature;
var publicWidget = require('web.public.widget');

/*
    I just wanted an extended template \o/
*/
var SepaNameAndSignature = NameAndSignature.extend({
    template: 'payment_sepa_direct_debit.sign_name_and_signature',
    xmlDependencies: [
        '/web/static/src/xml/name_and_signature.xml',
        '/payment_sepa_direct_debit/static/src/xml/sepa_signature.xml'
    ],
    /**
     * @override
     * prevent autofocus on the name field, since the signature widget
     * will be included in a more complex form and focusing in the middle
     * of the form is weird
     */
    focusName: function() {
        return;
    },
});

/*
This widget extends the signature form of the portal to allow plugging
it correctly into the SEPA payment form. Indeed, in the case of SEPA,
the flow is rather complex as SMS validation can be included optionnally.
If that is the case, then the sdd.mandate record can exist or not before
the signature is submitted. In addition, it make more sense to include
the signature but not to submit it by itself - instead, it should be submitted
along the other values of the form in which it is included. This is not
easily doable in the default widget.
*/
var SepaSignatureForm = SignatureForm.extend({
    template: 'payment_sepa_direct_debit.signature_form',
    xmlDependencies: [
        '/web/static/src/xml/name_and_signature.xml',
        '/payment_sepa_direct_debit/static/src/xml/sepa_signature.xml'
    ],
    /**
     * 
     * @override: replace the NameAndSignature widget class by the one
     * described above.
     * 
     * @param {Widget} parent
     * @param {Object} options: see @portal.signature_form
     */
    init: function (parent, options) {
        this._super.apply(this, arguments);

        this.csrf_token = odoo.csrf_token;

        this.callUrl = options.callUrl || '';
        this.rpcParams = options.rpcParams || {};

        this.nameAndSignature = new SepaNameAndSignature(this,
            options.nameAndSignatureOptions || {});
    },
    /**
     *  Return the signature fields content to be used outside of the widget
     */
    _getValues: function () {
        if (!this.nameAndSignature.validateSignature()) {
            return;
        }

        return {
            name: this.nameAndSignature.getName(),
            signature: this.nameAndSignature.getSignatureImage()[1]
        };
    },
});

return SepaSignatureForm;
});
