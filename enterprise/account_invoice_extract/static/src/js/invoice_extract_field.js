odoo.define('account_invoice_extract.Field', function (require) {
"use strict";

var InvoiceExtractFieldButton = require('account_invoice_extract.FieldButton');

var Class = require('web.Class');
var field_utils = require('web.field_utils');
var Mixins = require('web.mixins');

/**
 * This class represents a field for the 'invoice extract' OCR feature. This is
 * useful in order to determine whether this feature is active or not, and also
 * to track some important boxes such as 'ocr chosen' and 'user selected' boxes.
 */
var InvoiceExtractField = Class.extend(Mixins.EventDispatcherMixin, {
    custom_events: {
        click_invoice_extract_field_button: '_onClickInvoiceExtractFieldButton'
    },
    /**
     * @override
     * @param {Class} parent a class with EventDispatcherMixin
     * @param {Object} params
     * @param {string} params.fieldName
     * @param {string} params.text
     */
    init: function (parent, params) {
        Mixins.EventDispatcherMixin.init.call(this, arguments);
        this.setParent(parent);

        this._button = undefined;
        this._isActive = false;
        this._name = params.fieldName;
        this._text = params.text;

        this._ocrChosenBox = undefined;
        this._selectedBox = undefined;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Get the selected box for this field
     *
     * @returns {account_invoice_extract.Box|undefined}
     */
    getSelectedBox: function () {
        return this._selectedBox;
    },
    /**
     * Get the field name
     *
     * @returns {string}
     */
    getName: function () {
        return this._name;
    },
    /**
     * Called to compute changes on a field, usually after selecting a new
     * box. The view should be updated with the new field info.
     *
     * @param {Object} params
     * @param {any} params.fieldChangedInfo
     * @param {Object} params.state state of the form renderer
     * @returns {Object}
     */
    handleFieldChanged: function (params) {
        var fieldChangedInfo = params.fieldChangedInfo;
        var state = params.state;
        var changes = {};
        switch (this._name) {
            case 'date':
                changes = { invoice_date: field_utils.parse.date(fieldChangedInfo.split(' ')[0]) };
                break;
            case 'supplier':
                if (_.isNumber(fieldChangedInfo)) {
                    changes = { partner_id: { id: fieldChangedInfo } };
                }
                break;
            case 'VAT_Number':
                changes = { partner_id: { id: fieldChangedInfo } };
                break;
            case 'due_date':
                changes = { invoice_date_due: field_utils.parse.date(fieldChangedInfo.split(' ')[0]) };
                break;
            case 'invoice_id':
                changes = { ref: fieldChangedInfo };
                break;
            case 'currency':
                changes = { currency_id: { id: fieldChangedInfo } };
                break;
        }
        return changes;
    },
    /**
     * Tell whether this field is active or not.
     *
     * @returns {boolean}
     */
    isActive: function () {
        return this._isActive;
    },
    /**
     * Render the button that is related to this field, so that the user can
     * select this field by clicking on the button.
     *
     * @param {Object} params
     * @param {$.Element} params.$container jQuery element which contains a
     *   single node in the DOM. This node is the container of the buttons.
     * @returns {Promise}
     */
    renderButton: function (params) {
        this._button =  new InvoiceExtractFieldButton(this, {
            fieldName: this._name,
            isActive: this._isActive,
            text: this._text,
        });
        return this._button.appendTo(params.$container);
    },
    /**
     * Set this field as active.
     */
    setActive: function () {
        if (!this._isActive) {
            this._isActive = true;
            if (this._button) {
                this._button.setActive();
            }
        }
    },
    /**
     * Set this field as inactive.
     */
    setInactive: function () {
        if (this._isActive) {
            this._isActive = false;
            if (this._button) {
                this._button.setInactive();
            }
        }
    },
    /**
     * Reset the boxes selected by user and ocr
     */
    resetSelection: function () {
        this._ocrChosenBox = undefined;
        this._selectedBox = undefined;
    },
    /**
     * Set the provided invoice extract 'box' as chosen by the OCR.
     *
     * @param {account_invoice_extract.Box} box
     */
    setOcrChosenBox: function (box) {
        this._ocrChosenBox = box;
        if (!this._selectedBox) {
            this._selectedBox = this._ocrChosenBox;
            this._ocrChosenBox.setSelected();
        }
    },
    /**
     * Set the provided invoice extract 'box' as selected.
     *
     * @param {account_invoice_extract.Box} box
     */
    setSelectedBox: function (box) {
        if (this._selectedBox) {
            this._selectedBox.unsetSelected();
        }
        this._selectedBox = box;
        if (this._ocrChosenBox && this._selectedBox !== this._ocrChosenBox) {
            this._ocrChosenBox.unsetSelected();
        }
        this._selectedBox.setSelected();
    },
    /**
     * Unselect the selected box. If the box to unselect is not the OCR chosen
     * box, make the ocr chosen box as selected. If the selected box is the
     * ocr chosen one, also remove the ocr chosen status of this box.
     */
    unselectBox: function () {
        if (!this._selectedBox) {
            return;
        }
        if (this._ocrChosenBox && this._ocrChosenBox.isSelected()) {
            this._selectedBox = undefined;
            this._ocrChosenBox.unsetSelected();
            this._ocrChosenBox.unsetOcrChosen();
            this._ocrChosenBox = undefined;
        } else if (this._ocrChosenBox) {
            this._selectedBox.unsetSelected();
            this._selectedBox = this._ocrChosenBox;
            this._ocrChosenBox.setSelected();
        } else {
            this._selectedBox.unsetSelected();
            this._selectedBox = undefined;
        }
    },
    /**
     * Remove tracking of this box. This method is called when the
     * corresponding box is destroyed.
     *
     * @param {account_invoice_extract.Box} box
     */
    unsetBox: function (box) {
        if (this._ocrChosenBox === this._selectedBox && this._ocrChosenBox === box) {
            this._ocrChosenBox = this._selectedBox = undefined;
        } else if (this._ocrChosenBox === box) {
            this._ocrChosenBox = undefined;
        } else {
            this._selectedBox = this._ocrSelectedBox;
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when the button corresponding to this field has been clicked.
     *
     * @private
     * @param {OdooEvent} ev
     */
    _onClickInvoiceExtractFieldButton: function (ev) {
        ev.stopPropagation();
        this.trigger_up('active_invoice_extract_field', {
            fieldName: this._name,
        });
    },
});

return InvoiceExtractField;

});
