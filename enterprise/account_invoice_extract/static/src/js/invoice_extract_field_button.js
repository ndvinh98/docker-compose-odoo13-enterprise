odoo.define('account_invoice_extract.FieldButton', function (require) {
"use strict";

var Widget = require('web.Widget');

/**
 * This widget represents a field button on top of the attachment preview,
 * which is used to filter boxes which the selected field.
 */
var InvoiceExtractFieldButton = Widget.extend({
    events: {
        'click': '_onClick',
    },
    template: 'account_invoice_extract.Button',
    /**
     * @override
     * @param {Class} parent a class with EventDispatcherMixin
     * @param {Object} params
     * @param {string} params.fieldName
     * @param {boolean} [params.isActive=false]
     * @param {string} params.text
     */
    init: function (parent, params) {
        this._super.apply(this, arguments);

        this._fieldName = params.fieldName;
        this._isActive = params.isActive || false;
        this._text = params.text;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Get the field name of the field button
     *
     * @returns {string}
     */
    getFieldName: function () {
        return this._fieldName;
    },
    /**
     * Get the text representation of the field button
     *
     * @returns {string}
     */
    getText: function () {
        return this._text;
    },
    /**
     * Tell whether this field button is active or not
     *
     * @returns {boolean}
     */
    isActive: function () {
        return this._isActive;
    },
    /**
     * Set this field button as active
     */
    setActive: function () {
        this._isActive = true;
        if (this.$el) {
            this.$el.addClass('active');
        }
    },
    /**
     * Set this field button as inactive
     */
    setInactive: function () {
        this._isActive = false;
        if (this.$el) {
            this.$el.removeClass('active');
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent} ev
     */
    _onClick: function (ev) {
        ev.stopPropagation();
        this.trigger_up('click_invoice_extract_field_button');
    },
});

return InvoiceExtractFieldButton;

});
