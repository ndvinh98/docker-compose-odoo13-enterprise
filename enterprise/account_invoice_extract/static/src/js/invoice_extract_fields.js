odoo.define('account_invoice_extract.Fields', function (require) {
"use strict";

var InvoiceExtractField = require('account_invoice_extract.Field');

var Class = require('web.Class');
var Mixins = require('web.mixins');
var ServicesMixin = require('web.ServicesMixin');
var session = require('web.session');

/**
 * This class groups the fields that are supported by the OCR. Also, it manages
 * the 'active' status of the fields, so that there is only one active field at
 * any given time.
 */
var InvoiceExtractFields = Class.extend(Mixins.EventDispatcherMixin, ServicesMixin, {
    custom_events: {
        active_invoice_extract_field: '_onActiveInvoiceExtractField',
    },
    /**
     * @override
     * @param {Class} parent a class with EventDispatcherMixin
     */
    init: function (parent, is_customer_invoice=false) {
        var self = this;
        Mixins.EventDispatcherMixin.init.call(this, arguments);
        this.setParent(parent);

        var vendor_text = 'Vendor';
        if (is_customer_invoice) {
            vendor_text = 'Customer';
        }
        this._fields = [
            new InvoiceExtractField(this, { text: 'VAT', fieldName: 'VAT_Number' }),
            new InvoiceExtractField(this, { text: vendor_text, fieldName: 'supplier' }),
            new InvoiceExtractField(this, { text: 'Date', fieldName: 'date' }),
            new InvoiceExtractField(this, { text: 'Due Date', fieldName: 'due_date' }),
            new InvoiceExtractField(this, { text: 'Vendor Reference', fieldName: 'invoice_id' }),
        ];

        this._fields[0].setActive();
        session.user_has_group('base.group_multi_currency').then(function(has_multi_currency) {
            if (has_multi_currency) {
                self._fields.push(new InvoiceExtractField(self, { text: 'Currency', fieldName: 'currency' }));
            }
        });
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Get the current active field.
     *
     * @returns {account_invoice_extract.Field|undefined} returns undefined if
     *   there is no active field.
     */
    getActiveField: function () {
        return _.find(this._fields, function (field) {
            return field.isActive();
        });
    },
    /**
     * Get the field with the given 'name'. If no field name is provided,
     * gets the active field.
     *
     * @param {Object} [params={}]
     * @param {string} [params.name] the field name
     * @returns {account_invoice_extract.Field|undefined} returns undefined if
     *   the provided field name does not exist.
     */
    getField: function (params) {
        params = params || {};
        if (!params.name) {
            return this.getActiveField();
        }
        return _.find(this._fields, function (field) {
            return field.getName() === params.name;
        });
    },
    /**
     * Render the buttons for each fields.
     *
     * @param {Object} params
     * @param {$.Element} params.$container jQuery element with a single node
     *   in the DOM, which is the container of the field buttons.
     * @returns {Promise} resolves when all buttons are rendered
     */
    renderButtons: function (params) {
        var proms = [];
        _.each(this._fields, function (field) {
            proms.push(field.renderButton(params));
        });
        return Promise.all(proms);
    },
    /**
     * Reset the active state of fields, so that the 1st field is active.
     */
    resetActive: function () {
        var oldActiveField = this.getActiveField();
        if (!oldActiveField) {
            return;
        }
        oldActiveField.setInactive();
        this._fields[0].setActive();
    },
    /**
     * Reset the active state of fields, so that the 1st field is active.
     */
    resetFieldsSelections: function () {
        _.each(this._fields, function (field) {
            field.resetSelection();
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when a field is selected (e.g. by clicking on the corresponding
     * button). This field becomes active, and other fields become inactive.
     *
     * @private
     * @param {OdooEvent} ev
     * @param {string} ev.data.fieldName
     */
    _onActiveInvoiceExtractField: function (ev) {
        var oldActiveField = this.getActiveField();
        if (!oldActiveField) {
            return;
        }
        oldActiveField.setInactive();
        var field = this.getField({ name: ev.data.fieldName });
        if (!field) {
            return;
        }
        field.setActive();
    },
});

return InvoiceExtractFields;

});
