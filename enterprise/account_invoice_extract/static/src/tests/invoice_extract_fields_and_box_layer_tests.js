odoo.define('account_invoice_extract.FieldsAndBoxLayerTests', function (require) {
"use strict";

/**
 * This test suite tests the integration of box layers with fields (including
 * field buttons), without relying on a form view.
 */
var InvoiceExtractFields = require('account_invoice_extract.Fields');
var invoiceExtractTestUtils = require('account_invoice_extract.testUtils');

var testUtils = require('web.test_utils');

/**
 * @param {Object} params
 * @param {Object} [params.intercepts={}]
 * @param {Object} params.invoiceExtractWrapper object to pass fields and box
 *   layer by reference. This is due to fields and box layer needing an
 *   instance of the parent object in order to be instantiated.
 * @param {account_invoice_extract.Fields|undefined} params.invoiceExtractWrapper.fields
 *   this is set after the parent is created, but it should be used when this
 *   is set.
 * @param {account_invoice_extract.BoxLayer|undefined} params.invoiceExtractWrapper.boxLayer
 *   this is set after the parent is created, but it should be used when this
 *   is set.
 */
function createParent(params) {
    var invoiceExtractWrapper = params.invoiceExtractWrapper;
    params.intercepts = _.extend({}, params.intercepts, {
        /**
         * Triggered when there is a change of active field
         *
         * @param {OdooEvent} ev
         */
        active_invoice_extract_field: function (ev) {
            ev.stopPropagation();
            var fieldName = invoiceExtractWrapper.fields.getActiveField().getName();
            invoiceExtractWrapper.boxLayer.displayBoxes({ fieldName: fieldName });
        },
        /**
         * Triggered by OCR chosen box
         *
         * @param {OdooEvent} ev
         * @param {account_invoice_extract.Box} ev.data.box
         */
        choice_ocr_invoice_extract_box: function (ev) {
            ev.stopPropagation();
            var box = ev.data.box;
            var field = invoiceExtractWrapper.fields.getField({
                name: box.getFieldName()
            });
            field.setOcrChosenBox(box);
        },
        /**
         * Triggered when clicking on a box
         *
         * @param {OdooEvent} ev
         * @param {account_invoice_extract.Box} ev.data.box
         */
        click_invoice_extract_box: function (ev) {
            ev.stopPropagation();
            var box = ev.data.box;
            var field = invoiceExtractWrapper.fields.getField({
                name: box.getFieldName()
            });
            field.setSelectedBox(box);
        },
        /**
         * Triggered when clicking on a box layer
         *
         * @param {OdooEvent} ev
         */
        click_invoice_extract_box_layer: function (ev) {
            ev.stopPropagation();
            var field = invoiceExtractWrapper.fields.getActiveField();
            var box = field.getSelectedBox();
            if (!box) {
                return;
            }
            field.unselectBox();
        },
        /**
         * Triggered by user selected box
         *
         * @param {OdooEvent} ev
         * @param {account_invoice_extract.Box} ev.data.box
         */
        select_invoice_extract_box: function (ev) {
            ev.stopPropagation();
            var box = ev.data.box;
            var field = invoiceExtractWrapper.fields.getField({
                name: box.getFieldName()
            });
            field.setSelectedBox(box);
        },
    });
    var parent = testUtils.createParent(params);
    return parent;
}

/**
 * @param {Object} [params={}]
 * @param {boolean} [params.debug=false]
 * @returns {Object}
 */
async function createFieldsAndBoxLayer(params) {
    params = params || {};
    var $container = params.debug ? $('body') : $('#qunit-fixture');

    // use wrapper to pass fields and box layer by reference
    // (due to them not already instantiated)
    var wrapper = {};
    var parent = createParent({
        invoiceExtractWrapper: wrapper,
        debug: params.debug || false,
        session: {
            user_has_group: function () {
                return Promise.resolve();
            }
        },
    });

    var fields = wrapper.fields = new InvoiceExtractFields(parent);
    await fields.renderButtons({ $container: $container });
    var res = await invoiceExtractTestUtils.createBoxLayer({ parent: parent });
    var boxLayer = wrapper.boxLayer = res.boxLayer;
    boxLayer.displayBoxes({ fieldName: fields.getActiveField().getName() });

    return {
        boxLayer: boxLayer,
        fields: fields,
        parent: parent,
    };
}

QUnit.module('account_invoice_extract', {}, function () {
QUnit.module('Fields & BoxLayer integration', {
    afterEach: function () {
        $('.page').remove();
    },
}, function () {

    QUnit.test('basic', async function (assert) {
        assert.expect(29);

        var res = await createFieldsAndBoxLayer();
        var fields = res.fields;
        var parent = res.parent;

        assert.strictEqual(fields.getActiveField().getName(), 'VAT_Number',
            "by default, VAT should be the default active field");
        assert.strictEqual($('.o_invoice_extract_button').length, 5,
            "should render all 5 fields buttons");

        // box 1
        assert.strictEqual($('.o_invoice_extract_box[data-id=1]').length, 1,
            "should have box with ID 1");
        assert.strictEqual($('.o_invoice_extract_box[data-id=1]').data('field-name'),
            'VAT_Number',
            "should have correct field name for box with ID 1");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'ocr_chosen',
            "should not set box with ID 1 as OCR chosen");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'selected',
            "should not set box with ID 1 as selected");
        assert.isVisible($('.o_invoice_extract_box[data-id=1]'),
            "should show box with ID 1 by default");
        // box 2
        assert.strictEqual($('.o_invoice_extract_box[data-id=2]').length, 1,
            "should have box with ID 1");
        assert.strictEqual($('.o_invoice_extract_box[data-id=2]').data('field-name'),
            'VAT_Number',
            "should have correct field name for box with ID 2");
        assert.hasClass($('.o_invoice_extract_box[data-id=2]'),'ocr_chosen',
            "should set box with ID 2 as OCR chosen");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "should not set box with ID 2 as selected");
        assert.isVisible($('.o_invoice_extract_box[data-id=2]'),
            "should show box with ID 2 by default");
        // box 3
        assert.strictEqual($('.o_invoice_extract_box[data-id=3]').length, 1,
            "should have box with ID 3");
        assert.strictEqual($('.o_invoice_extract_box[data-id=3]').data('field-name'),
            'VAT_Number',
            "should have correct field name for box with ID 3");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=3]'), 'ocr_chosen',
            "should not set box with ID 3 as OCR chosen");
        assert.hasClass($('.o_invoice_extract_box[data-id=3]'),'selected',
            "should set box with ID 3 as selected");
        assert.isVisible($('.o_invoice_extract_box[data-id=3]'),
            "should show box with ID 3 by default");
        // box 4
        assert.strictEqual($('.o_invoice_extract_box[data-id=4]').length, 1,
            "should have box with ID 4");
        assert.strictEqual($('.o_invoice_extract_box[data-id=4]').data('field-name'),
            'invoice_id',
            "should have correct field name for box with ID 4");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'ocr_chosen',
            "should not set box with ID 4 as OCR chosen");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "should not set box with ID 4 as selected");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=4]'),
            "should hide box with ID 4 by default");
        // box 5
        assert.strictEqual($('.o_invoice_extract_box[data-id=5]').length, 1,
            "should have box with ID 5");
        assert.strictEqual($('.o_invoice_extract_box[data-id=5]').data('field-name'),
            'invoice_id',
            "should have correct field name for box with ID 5");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'ocr_chosen',
            "should set box with ID 5 as OCR chosen");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "should set box with ID 5 as selected");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=5]'),
            "should hide box with ID 5 by default");

        var vatField = fields.getField({ name: 'VAT_Number' });
        var InvoiceIdField = fields.getField({ name: 'invoice_id' });

        assert.strictEqual(vatField.getSelectedBox().getID(), 3,
            "should have correctly registered the selected box for 'VAT_Number'");
        assert.strictEqual(InvoiceIdField.getSelectedBox().getID(), 5,
            "should have correctly registered the selected box for 'invoice_id'");

        parent.destroy();
    });

    QUnit.test('click on field button', async function (assert) {
        assert.expect(11);

        var res = await createFieldsAndBoxLayer();
        var fields = res.fields;
        var parent = res.parent;

        assert.strictEqual(fields.getActiveField().getName(), 'VAT_Number',
            "by default, VAT should be the default active field");

        assert.isVisible($('.o_invoice_extract_box[data-id=1]'),
            "should show box with ID 1 by default");
        assert.isVisible($('.o_invoice_extract_box[data-id=2]'),
            "should show box with ID 2 by default");
        assert.isVisible($('.o_invoice_extract_box[data-id=3]'),
            "should show box with ID 3 by default");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=4]'),
            "should hide box with ID 4 by default");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=5]'),
            "should hide box with ID 5 by default");

        await testUtils.dom.click($('.o_invoice_extract_button[data-field-name="invoice_id"]'));

        assert.isNotVisible($('.o_invoice_extract_box[data-id=1]'),
            "box with ID 1 should become hidden");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=2]'),
            "box with ID 2 should become hidden");
        assert.isNotVisible($('.o_invoice_extract_box[data-id=3]'),
            "box with ID 3 should become hidden");
        assert.isVisible($('.o_invoice_extract_box[data-id=4]'),
            "box with ID 4 should become visible");
        assert.isVisible($('.o_invoice_extract_box[data-id=5]'),
            "box with ID 5 should become visible");

        parent.destroy();
    });

    QUnit.test('select another box', async function (assert) {
        assert.expect(16);

        var res = await createFieldsAndBoxLayer();
        var fields = res.fields;
        var parent = res.parent;

        assert.strictEqual(fields.getActiveField().getName(), 'VAT_Number',
            "by default, VAT should be the default active field");

        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'selected',
            "box with ID 1 should not be selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should not be selected");
        assert.hasClass($('.o_invoice_extract_box[data-id=3]'),'selected',
            "box with ID 3 should be selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should not be selected");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should be selected");

        await testUtils.dom.click($('.o_invoice_extract_box[data-id=1]'));

        assert.hasClass($('.o_invoice_extract_box[data-id=1]'),'selected',
            "box with ID 1 should become selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should stay unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=3]'), 'selected',
            "box with ID 3 should become unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should stay unselected");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should stay selected");

        await testUtils.dom.click($('.o_invoice_extract_button[data-field-name="invoice_id"]'));
        await testUtils.dom.click($('.o_invoice_extract_box[data-id=4]'));

        assert.hasClass($('.o_invoice_extract_box[data-id=1]'),'selected',
            "box with ID 1 should stay selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should stay unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=3]'), 'selected',
            "box with ID 3 should stay unselected");
        assert.hasClass($('.o_invoice_extract_box[data-id=4]'),'selected',
            "box with ID 4 should become selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=5]'), 'selected',
            "box with ID 5 should become unselected");

        parent.destroy();
    });

    QUnit.test('click on box layer', async function (assert) {
        assert.expect(16);

        var res = await createFieldsAndBoxLayer();
        var fields = res.fields;
        var parent = res.parent;

        assert.strictEqual(fields.getActiveField().getName(), 'VAT_Number',
            "by default, VAT should be the default active field");

        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'selected',
            "box with ID 1 should not be selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should not be selected");
        assert.hasClass($('.o_invoice_extract_box[data-id=3]'),'selected',
            "box with ID 3 should be selected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should not be selected");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should be selected");

        await testUtils.dom.click($('.boxLayer'));

        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'selected',
            "box with ID 1 should stay unselected");
        assert.hasClass($('.o_invoice_extract_box[data-id=2]'),'selected',
            "box with ID 2 should become selected (fallback on OCR chosen)");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=3]'), 'selected',
            "box with ID 3 should become unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should stay unselected");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should stay selected");

        await testUtils.dom.click($('.boxLayer'));

        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=1]'), 'selected',
            "box with ID 1 should not stay unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=2]'), 'selected',
            "box with ID 2 should become unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=3]'), 'selected',
            "box with ID 3 should stay unselected");
        assert.doesNotHaveClass($('.o_invoice_extract_box[data-id=4]'), 'selected',
            "box with ID 4 should stay unselected");
        assert.hasClass($('.o_invoice_extract_box[data-id=5]'),'selected',
            "box with ID 5 should stay selected");

        parent.destroy();
    });

});
});
});
